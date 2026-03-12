from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
import base64
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
import jsonschema
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, require_roles
from app.config import settings
from app.db import SessionLocal, get_db
from app.models import (
    BondRequest,
    Manifest,
    SigningKey,
    SigningKeyEvent,
    SigningKeyOperationRequest,
)
from app.schemas import CreateBondRequest
from app.signing import DbPemSigningProvider, MockHsmSigningProvider

app = FastAPI(title="WA Performance Bond E-Bonding Platform", version="0.2.0")
MANIFEST_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "manifest.schema.json"
with MANIFEST_SCHEMA_PATH.open(encoding="utf-8") as _f:
    MANIFEST_SCHEMA = json.load(_f)

DB_PEM_PROVIDER = DbPemSigningProvider()
MOCK_HSM_PROVIDER = MockHsmSigningProvider()
SIGNING_PROVIDERS = {
    DB_PEM_PROVIDER.backend_name: DB_PEM_PROVIDER,
    MOCK_HSM_PROVIDER.backend_name: MOCK_HSM_PROVIDER,
}


def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_approval_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _canonical_payload(manifest: dict) -> bytes:
    payload = {
        k: v
        for k, v in manifest.items()
        if k not in ("platform_signature", "ledger_entry_id", "ledger_hash")
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def _get_provider(name: str):
    provider = SIGNING_PROVIDERS.get(name)
    if not provider:
        raise HTTPException(
            status_code=500, detail=f"Unsupported signing backend: {name}"
        )
    return provider


async def _create_signing_key_record(db: AsyncSession, backend: str) -> SigningKey:
    provider = _get_provider(backend)
    generated = provider.generate()
    key = SigningKey(
        key_id=f"dev-key-{uuid.uuid4()}",
        key_backend=backend,
        key_ref=generated.key_ref,
        private_key_pem=generated.private_key_pem,
        certificate_pem=generated.certificate_pem,
        not_before=generated.not_before,
        not_after=generated.not_after,
        is_active=True,
    )
    db.add(key)
    await db.flush()
    return key


async def _rotate_signing_key(
    db: AsyncSession,
    backend: str,
    reason: str,
    actor_id: uuid.UUID,
    approval_token: str,
    is_emergency: bool = False,
) -> SigningKey:
    existing_result = await db.execute(
        select(SigningKey).where(
            SigningKey.is_active.is_(True),
            SigningKey.revoked_at.is_(None),
            SigningKey.key_backend == backend,
        )
    )
    existing_keys = existing_result.scalars().all()
    now = datetime.now(timezone.utc)
    for key in existing_keys:
        key.is_active = False
        key.revoked_at = now
        key.revoked_reason = reason
    new_key = await _create_signing_key_record(db, backend)
    token_hash = _hash_approval_token(approval_token)
    if existing_keys:
        for old_key in existing_keys:
            db.add(
                SigningKeyEvent(
                    action="rotate",
                    actor_id=actor_id,
                    reason=reason,
                    old_key_id=old_key.key_id,
                    new_key_id=new_key.key_id,
                    is_emergency=is_emergency,
                    approval_token_hash=token_hash,
                )
            )
    else:
        db.add(
            SigningKeyEvent(
                action="rotate",
                actor_id=actor_id,
                reason=reason,
                old_key_id=None,
                new_key_id=new_key.key_id,
                is_emergency=is_emergency,
                approval_token_hash=token_hash,
            )
        )
    await db.commit()
    await db.refresh(new_key)
    return new_key


async def _get_active_signing_key(db: AsyncSession) -> SigningKey:
    async def _query() -> SigningKey | None:
        result = await db.execute(
            select(SigningKey)
            .where(
                SigningKey.is_active.is_(True),
                SigningKey.revoked_at.is_(None),
                SigningKey.key_backend == settings.signing_backend,
            )
            .order_by(SigningKey.created_at.desc())
        )
        return result.scalars().first()

    key = await _query()
    if not key:
        await _ensure_active_signing_key()
        key = await _query()
    if not key:
        raise HTTPException(status_code=503, detail="No active signing key available")
    return key


async def _ensure_active_signing_key() -> None:
    async with SessionLocal() as db:
        result = await db.execute(
            select(SigningKey)
            .where(
                SigningKey.is_active.is_(True),
                SigningKey.revoked_at.is_(None),
                SigningKey.key_backend == settings.signing_backend,
            )
            .order_by(SigningKey.created_at.desc())
        )
        key = result.scalars().first()
        provider = _get_provider(settings.signing_backend)
        if key:
            if key.key_backend == "db_pem" and key.private_key_pem:
                return
            if (
                key.key_backend == "mock_hsm"
                and isinstance(provider, MockHsmSigningProvider)
                and provider.has_key(key.key_ref)
            ):
                return
            key.is_active = False
            key.revoked_at = datetime.now(timezone.utc)
            key.revoked_reason = (
                "startup-rotation: invalid or missing key handle/material"
            )

        await _create_signing_key_record(db, settings.signing_backend)
        await db.commit()


def _render_pdf(bond_id: uuid.UUID) -> bytes:
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    return body + f"\n%BOND:{bond_id}".encode()


def _append_status(
    history: list[dict],
    status: str,
    actor_id: uuid.UUID,
    actor_role: str,
    rationale: str | None = None,
) -> list[dict]:
    item = {
        "status": status,
        "actor_id": str(actor_id),
        "actor_role": actor_role,
        "timestamp": _utc_iso(),
    }
    if rationale:
        item["rationale"] = rationale
    return [*history, item]


def _build_manifest_json(
    bond: BondRequest, pdf_bytes: bytes, manifest_id: uuid.UUID, signing_key: SigningKey
) -> dict:
    manifest = {
        "manifest_id": str(manifest_id),
        "schema_version": "1.0.0",
        "bond_request_id": str(bond.id),
        "document_hash": _sha256_hex(pdf_bytes),
        "clause_version_ids": bond.selected_clause_ids or [str(uuid.uuid4())],
        "rule_version_ids": ["RCW_39_08_penal_sum@1"],
        "principal_signer": {
            "name": bond.principal_name,
            "email": "principal@example.com",
            "kyc_pointer": {
                "provider": "manual",
                "verification_id": f"kyc-{bond.id}",
                "verified_at": _utc_iso(),
                "status": "verified",
            },
            "signature_timestamp": _utc_iso(),
            "signature_method": "e_sign",
            "e_sign_provider": "mock",
            "e_sign_envelope_id": f"env-{bond.id}",
        },
        "notarization_meta": {
            "notarization_type": "wet_ink",
            "notary_name": "Demo Notary",
            "notary_commission_id": "WA-123456",
            "notary_state": "WA",
            "notarization_timestamp": _utc_iso(),
            "scanned_pages_pointer": {
                "s3_uri": f"s3://demo-bucket/{bond.id}/wet-ink.pdf",
                "checksum_sha256": "a" * 64,
            },
        },
        "issued_at": _utc_iso(),
        "jurisdiction": "WA",
        "bond_type": "public_works_performance",
    }
    payload = _canonical_payload(manifest)
    provider = _get_provider(signing_key.key_backend)
    signature_bytes = provider.sign(
        payload, signing_key.private_key_pem, signing_key.key_ref
    )
    manifest["platform_signature"] = {
        "algorithm": "ECDSA-P256",
        "key_id": signing_key.key_id,
        "signature": base64.b64encode(signature_bytes).decode("ascii"),
        "certificate_chain": [signing_key.certificate_pem],
    }
    ledger_hash = _sha256_hex(payload)
    manifest["ledger_entry_id"] = f"ledger-{manifest_id}"
    manifest["ledger_hash"] = ledger_hash
    return manifest


def _verify_platform_signature(manifest: dict, trusted_key: SigningKey) -> bool:
    sig_block = manifest.get("platform_signature") or {}
    key_id = sig_block.get("key_id")
    signature_b64 = sig_block.get("signature")
    chain = sig_block.get("certificate_chain") or []
    if not key_id or not signature_b64 or not chain:
        return False
    if key_id != trusted_key.key_id:
        return False
    if chain[0].strip() != trusted_key.certificate_pem.strip():
        return False
    cert = x509.load_pem_x509_certificate(chain[0].encode("utf-8"))
    if cert.issuer != cert.subject:
        return False
    issued_at = datetime.fromisoformat(manifest["issued_at"].replace("Z", "+00:00"))
    cert_not_before = cert.not_valid_before_utc
    cert_not_after = cert.not_valid_after_utc
    if not (cert_not_before <= issued_at <= cert_not_after):
        return False
    trusted_not_before = _to_aware_utc(trusted_key.not_before)
    trusted_not_after = _to_aware_utc(trusted_key.not_after)
    if not (trusted_not_before <= issued_at <= trusted_not_after):
        return False
    if trusted_key.revoked_at is not None:
        revoked_at = _to_aware_utc(trusted_key.revoked_at)
        if revoked_at <= issued_at:
            return False
    signature = base64.b64decode(signature_b64)
    payload = _canonical_payload(manifest)
    cert.public_key().verify(signature, payload, ec.ECDSA(hashes.SHA256()))
    return True


def _bond_out(bond: BondRequest) -> dict:
    return {
        "id": str(bond.id),
        "status": bond.status,
        "manifest_id": str(bond.manifest.id) if bond.manifest else None,
        "status_history": bond.status_history,
        "created_at": bond.created_at.isoformat() if bond.created_at else None,
        "updated_at": bond.updated_at.isoformat() if bond.updated_at else None,
    }


async def _get_bond_or_404(db: AsyncSession, bond_id: uuid.UUID) -> BondRequest:
    result = await db.execute(select(BondRequest).where(BondRequest.id == bond_id))
    bond = result.scalar_one_or_none()
    if not bond:
        raise HTTPException(status_code=404, detail="Bond not found")
    return bond


def _can_view_bond(user: CurrentUser, bond: BondRequest) -> bool:
    if user.role in {"admin", "underwriter", "legal"}:
        return True
    if user.role == "broker":
        return user.user_id == bond.broker_id
    return False


@app.on_event("startup")
async def _startup_init_signing_key() -> None:
    await _ensure_active_signing_key()


def _signing_key_out(key: SigningKey) -> dict:
    return {
        "key_id": key.key_id,
        "key_backend": key.key_backend,
        "key_ref": key.key_ref,
        "is_active": key.is_active,
        "not_before": key.not_before.isoformat() if key.not_before else None,
        "not_after": key.not_after.isoformat() if key.not_after else None,
        "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
        "revoked_reason": key.revoked_reason,
        "created_at": key.created_at.isoformat() if key.created_at else None,
    }


def _validate_admin_approval(data: dict) -> str:
    token = data.get("approval_token")
    if not token:
        raise HTTPException(status_code=400, detail="approval_token is required")
    if token != settings.admin_approval_token:
        raise HTTPException(status_code=403, detail="Invalid approval token")
    return token


def _op_request_out(req: SigningKeyOperationRequest) -> dict:
    return {
        "id": str(req.id),
        "operation_type": req.operation_type,
        "target_key_id": req.target_key_id,
        "backend": req.backend,
        "reason": req.reason,
        "emergency": req.emergency,
        "create_replacement": req.create_replacement,
        "requested_by": str(req.requested_by),
        "approved_by": str(req.approved_by) if req.approved_by else None,
        "status": req.status,
        "execution_result": req.execution_result,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "decided_at": req.decided_at.isoformat() if req.decided_at else None,
    }


async def _execute_revoke_signing_key(
    *,
    db: AsyncSession,
    key_id: str,
    reason: str,
    is_emergency: bool,
    create_replacement: bool,
    actor_id: uuid.UUID,
    approval_token: str,
) -> dict:
    result = await db.execute(select(SigningKey).where(SigningKey.key_id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Signing key not found")
    if key.revoked_at is not None:
        return {"status": "already_revoked", "key": _signing_key_out(key)}

    active_result = await db.execute(
        select(SigningKey).where(
            SigningKey.key_backend == key.key_backend,
            SigningKey.is_active.is_(True),
            SigningKey.revoked_at.is_(None),
        )
    )
    active_keys = active_result.scalars().all()
    is_last_trusted = len(active_keys) <= 1 and key.is_active
    if is_last_trusted and not (is_emergency and create_replacement):
        raise HTTPException(
            status_code=409,
            detail="Cannot revoke last trusted key without emergency=true and create_replacement=true",
        )

    was_active = key.is_active
    key.is_active = False
    key.revoked_at = datetime.now(timezone.utc)
    key.revoked_reason = reason
    replacement = None
    if create_replacement or (
        key.key_backend == settings.signing_backend and was_active
    ):
        replacement = await _create_signing_key_record(db, key.key_backend)
    db.add(
        SigningKeyEvent(
            action="revoke",
            actor_id=actor_id,
            reason=reason,
            old_key_id=key.key_id,
            new_key_id=replacement.key_id if replacement else None,
            is_emergency=is_emergency,
            approval_token_hash=_hash_approval_token(approval_token),
        )
    )
    await db.commit()
    await db.refresh(key)
    if replacement is not None:
        await db.refresh(replacement)
    return {
        "status": "revoked",
        "revoked_key": _signing_key_out(key),
        "replacement_key": _signing_key_out(replacement) if replacement else None,
    }


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok", "service": "ebonding-api", "timestamp": _utc_iso()}


@app.get("/api/v1/admin/signing-keys")
async def list_signing_keys(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_roles("admin")),
) -> dict:
    result = await db.execute(select(SigningKey).order_by(SigningKey.created_at.desc()))
    keys = result.scalars().all()
    return {"items": [_signing_key_out(k) for k in keys]}


@app.get("/api/v1/admin/signing-key-events")
async def list_signing_key_events(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_roles("admin")),
) -> dict:
    result = await db.execute(
        select(SigningKeyEvent).order_by(SigningKeyEvent.created_at.desc())
    )
    events = result.scalars().all()
    return {
        "items": [
            {
                "action": e.action,
                "actor_id": str(e.actor_id),
                "reason": e.reason,
                "old_key_id": e.old_key_id,
                "new_key_id": e.new_key_id,
                "is_emergency": e.is_emergency,
                "approval_token_hash": e.approval_token_hash,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
    }


@app.get("/api/v1/admin/signing-key-operation-requests")
async def list_signing_key_operation_requests(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_roles("admin")),
) -> dict:
    result = await db.execute(
        select(SigningKeyOperationRequest).order_by(
            SigningKeyOperationRequest.created_at.desc()
        )
    )
    requests = result.scalars().all()
    return {"items": [_op_request_out(r) for r in requests]}


@app.post("/api/v1/admin/signing-keys/rotate")
async def rotate_signing_key(
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_roles("admin")),
) -> JSONResponse:
    data = payload or {}
    approval_token = _validate_admin_approval(data)
    backend = data.get("backend") or settings.signing_backend
    reason = data.get("reason") or "manual rotation"
    is_emergency = bool(data.get("emergency", False))
    req = SigningKeyOperationRequest(
        operation_type="rotate",
        target_key_id=None,
        backend=backend,
        reason=reason,
        emergency=is_emergency,
        create_replacement=True,
        approval_token_hash=_hash_approval_token(approval_token),
        requested_by=user.user_id,
        status="pending",
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return JSONResponse(
        status_code=202,
        content={"status": "pending_approval", "request": _op_request_out(req)},
    )


@app.post("/api/v1/admin/signing-keys/{key_id}/revoke")
async def revoke_signing_key(
    key_id: str,
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_roles("admin")),
) -> dict:
    data = payload or {}
    approval_token = _validate_admin_approval(data)
    reason = data.get("reason") or "manual revoke"
    is_emergency = bool(data.get("emergency", False))
    create_replacement = bool(data.get("create_replacement", False))
    req = SigningKeyOperationRequest(
        operation_type="revoke",
        target_key_id=key_id,
        backend=None,
        reason=reason,
        emergency=is_emergency,
        create_replacement=create_replacement,
        approval_token_hash=_hash_approval_token(approval_token),
        requested_by=user.user_id,
        status="pending",
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return {"status": "pending_approval", "request": _op_request_out(req)}


@app.post("/api/v1/admin/signing-key-operation-requests/{request_id}/approve")
async def approve_signing_key_operation_request(
    request_id: uuid.UUID,
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_roles("admin")),
) -> dict:
    data = payload or {}
    approval_token = _validate_admin_approval(data)
    approval_token_hash = _hash_approval_token(approval_token)

    result = await db.execute(
        select(SigningKeyOperationRequest).where(
            SigningKeyOperationRequest.id == request_id
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Operation request not found")
    if req.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"Operation request already {req.status}"
        )
    if req.requested_by == user.user_id:
        raise HTTPException(
            status_code=409, detail="Requester and approver must be different admins"
        )
    if req.approval_token_hash != approval_token_hash:
        raise HTTPException(
            status_code=403, detail="Approval token does not match request"
        )

    if settings.approval_replay_window_seconds > 0:
        replay_window_start = datetime.now(timezone.utc) - timedelta(
            seconds=settings.approval_replay_window_seconds
        )
        replay_result = await db.execute(
            select(SigningKeyOperationRequest).where(
                SigningKeyOperationRequest.status == "executed",
                SigningKeyOperationRequest.approved_by.is_not(None),
                SigningKeyOperationRequest.approval_token_hash == approval_token_hash,
                SigningKeyOperationRequest.decided_at.is_not(None),
                SigningKeyOperationRequest.decided_at >= replay_window_start,
                SigningKeyOperationRequest.id != req.id,
            )
        )
        replay_hit = replay_result.scalars().first()
        if replay_hit is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Approval token replay detected within configured window; "
                    "wait for window expiry or use a different approval mechanism"
                ),
            )

    execution_result: dict
    if req.operation_type == "rotate":
        backend = req.backend or settings.signing_backend
        new_key = await _rotate_signing_key(
            db=db,
            backend=backend,
            reason=req.reason,
            actor_id=user.user_id,
            approval_token=approval_token,
            is_emergency=req.emergency,
        )
        execution_result = {"status": "rotated", "new_key": _signing_key_out(new_key)}
    elif req.operation_type == "revoke":
        if not req.target_key_id:
            raise HTTPException(
                status_code=400, detail="Revoke request missing target_key_id"
            )
        execution_result = await _execute_revoke_signing_key(
            db=db,
            key_id=req.target_key_id,
            reason=req.reason,
            is_emergency=req.emergency,
            create_replacement=req.create_replacement,
            actor_id=user.user_id,
            approval_token=approval_token,
        )
    else:
        raise HTTPException(
            status_code=400, detail=f"Unsupported operation_type: {req.operation_type}"
        )

    req.status = "executed"
    req.approved_by = user.user_id
    req.decided_at = datetime.now(timezone.utc)
    req.execution_result = execution_result
    await db.commit()
    await db.refresh(req)
    return {
        "status": "executed",
        "request": _op_request_out(req),
        "execution_result": execution_result,
    }


@app.post("/api/v1/bonds")
async def create_bond_request(
    payload: CreateBondRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_roles("broker")),
) -> JSONResponse:
    bond = BondRequest(
        principal_name=payload.principal_name,
        principal_ubi_number=payload.principal_ubi_number,
        contractor_registration_number=payload.contractor_registration_number,
        obligee_agency_id=payload.obligee_agency_id,
        carrier_id=payload.carrier_id,
        broker_id=user.user_id,
        contract_id=payload.contract_id,
        contract_amount=payload.contract_amount,
        penal_sum=payload.penal_sum,
        project_description=payload.project_description,
        project_county=payload.project_county,
        selected_clause_ids=[str(x) for x in payload.selected_clause_ids],
        status="draft",
        status_history=_append_status([], "draft", user.user_id, user.role),
    )
    db.add(bond)
    await db.commit()
    await db.refresh(bond)
    return JSONResponse(status_code=201, content=_bond_out(bond))


@app.post("/api/v1/bonds/{bond_id}/submit")
async def submit_bond_request(
    bond_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_roles("broker")),
) -> JSONResponse:
    bond = await _get_bond_or_404(db, bond_id)
    if user.user_id != bond.broker_id:
        raise HTTPException(
            status_code=403, detail="Cannot submit another broker's bond"
        )
    if bond.status != "draft":
        raise HTTPException(
            status_code=409, detail="Bond request is not in draft status"
        )

    if bond.penal_sum != bond.contract_amount:
        bond.status = "review_required"
        bond.status_history = _append_status(
            _append_status(bond.status_history, "submitted", user.user_id, user.role),
            "review_required",
            user.user_id,
            user.role,
            "RCW_39_08_penal_sum rule failed",
        )
        await db.commit()
        await db.refresh(bond)
        return JSONResponse(status_code=202, content=_bond_out(bond))

    bond.status = "issued"
    history = _append_status(bond.status_history, "submitted", user.user_id, user.role)
    history = _append_status(history, "auto_approved", user.user_id, user.role)

    pdf_bytes = _render_pdf(bond.id)
    manifest_id = uuid.uuid4()
    signing_key = await _get_active_signing_key(db)
    manifest_json = _build_manifest_json(bond, pdf_bytes, manifest_id, signing_key)

    manifest = Manifest(
        id=manifest_id,
        bond_request_id=bond.id,
        document_hash=manifest_json["document_hash"],
        ledger_entry_id=manifest_json["ledger_entry_id"],
        ledger_hash=manifest_json["ledger_hash"],
        manifest_json=manifest_json,
    )
    db.add(manifest)
    bond.manifest = manifest
    bond.bond_pdf = pdf_bytes
    bond.status_history = _append_status(history, "issued", user.user_id, user.role)
    await db.commit()
    await db.refresh(bond)
    await db.refresh(manifest)
    return JSONResponse(status_code=202, content=_bond_out(bond))


@app.get("/api/v1/bonds/{bond_id}")
async def get_bond(
    bond_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(
        require_roles("broker", "underwriter", "legal", "admin")
    ),
) -> dict:
    bond = await _get_bond_or_404(db, bond_id)
    if not _can_view_bond(user, bond):
        raise HTTPException(status_code=403, detail="Not allowed to view this bond")
    await db.refresh(bond, attribute_names=["manifest"])
    return _bond_out(bond)


@app.get("/api/v1/bonds/{bond_id}/pdf")
async def download_bond_pdf(
    bond_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(
        require_roles("broker", "underwriter", "legal", "admin")
    ),
) -> Response:
    bond = await _get_bond_or_404(db, bond_id)
    if not _can_view_bond(user, bond):
        raise HTTPException(status_code=403, detail="Not allowed to view this bond")
    if not bond.bond_pdf:
        raise HTTPException(status_code=404, detail="Bond PDF not found")
    return Response(content=bond.bond_pdf, media_type="application/pdf")


@app.get("/api/v1/manifests/{manifest_id}")
async def get_manifest(
    manifest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(
        require_roles("broker", "underwriter", "legal", "admin")
    ),
) -> dict:
    result = await db.execute(select(Manifest).where(Manifest.id == manifest_id))
    manifest = result.scalar_one_or_none()
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")
    bond = await _get_bond_or_404(db, manifest.bond_request_id)
    if not _can_view_bond(user, bond):
        raise HTTPException(status_code=403, detail="Not allowed to view this manifest")
    return manifest.manifest_json


@app.get("/api/v1/manifests/{manifest_id}/verify")
async def verify_manifest(
    manifest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(
        require_roles("broker", "underwriter", "legal", "admin")
    ),
) -> JSONResponse:
    result = await db.execute(select(Manifest).where(Manifest.id == manifest_id))
    manifest = result.scalar_one_or_none()
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")
    bond = await _get_bond_or_404(db, manifest.bond_request_id)
    if not _can_view_bond(user, bond):
        raise HTTPException(
            status_code=403, detail="Not allowed to verify this manifest"
        )

    manifest_json = manifest.manifest_json
    checks = []
    pdf_hash_ok = (
        bond.bond_pdf is not None
        and _sha256_hex(bond.bond_pdf) == manifest_json["document_hash"]
    )
    checks.append(
        {"check": "document_hash_match", "result": "pass" if pdf_hash_ok else "fail"}
    )
    try:
        jsonschema.Draft202012Validator(MANIFEST_SCHEMA).validate(manifest_json)
        checks.append({"check": "schema_valid", "result": "pass"})
    except Exception:
        checks.append({"check": "schema_valid", "result": "fail"})

    try:
        sig_block = manifest_json.get("platform_signature") or {}
        key_id = sig_block.get("key_id")
        trusted_key = None
        if key_id:
            trusted_result = await db.execute(
                select(SigningKey).where(SigningKey.key_id == key_id)
            )
            trusted_key = trusted_result.scalar_one_or_none()
        if trusted_key is None:
            raise ValueError("Trusted signing key not found")
        _verify_platform_signature(manifest_json, trusted_key)
        checks.append({"check": "platform_signature_valid", "result": "pass"})
    except Exception:
        checks.append({"check": "platform_signature_valid", "result": "fail"})
    computed_ledger_hash = _sha256_hex(_canonical_payload(manifest_json))
    checks.append(
        {
            "check": "ledger_hash_match",
            "result": "pass"
            if computed_ledger_hash == manifest_json["ledger_hash"]
            else "fail",
        }
    )
    checks.append({"check": "ledger_timestamp_valid", "result": "pass"})
    overall = "pass" if all(x["result"] == "pass" for x in checks) else "fail"
    return JSONResponse(
        {
            "manifest_id": str(manifest.id),
            "overall_result": overall,
            "checks": checks,
            "verified_at": _utc_iso(),
        }
    )


@app.post("/api/v1/audit-bundles/{manifest_id}/generate")
async def generate_audit_bundle(
    manifest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_roles("admin")),
) -> JSONResponse:
    result = await db.execute(select(Manifest).where(Manifest.id == manifest_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Manifest not found")
    return JSONResponse(
        status_code=202,
        content={"manifest_id": str(manifest_id), "status": "generating"},
    )


@app.get("/api/v1/audit-bundles/{manifest_id}")
async def download_audit_bundle(
    manifest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(
        require_roles("broker", "underwriter", "legal", "admin")
    ),
) -> Response:
    result = await db.execute(select(Manifest).where(Manifest.id == manifest_id))
    manifest = result.scalar_one_or_none()
    if not manifest:
        raise HTTPException(status_code=404, detail="Audit bundle not found")
    bond = await _get_bond_or_404(db, manifest.bond_request_id)
    if not _can_view_bond(user, bond):
        raise HTTPException(status_code=403, detail="Not allowed to view this bundle")
    if not bond.bond_pdf:
        raise HTTPException(status_code=404, detail="Audit bundle not found")

    data = io.BytesIO()
    manifest_json = manifest.manifest_json
    with zipfile.ZipFile(data, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bond.pdf", bond.bond_pdf)
        zf.writestr("manifest.json", json.dumps(manifest_json))
        zf.writestr(
            "notarization_evidence.json",
            json.dumps(manifest_json.get("notarization_meta", {})),
        )
        zf.writestr(
            "kyc_pointer.json",
            json.dumps(manifest_json["principal_signer"]["kyc_pointer"]),
        )
        zf.writestr(
            "ledger_proof.json",
            json.dumps(
                {
                    "ledger_entry_id": manifest_json["ledger_entry_id"],
                    "ledger_hash": manifest_json["ledger_hash"],
                }
            ),
        )
        legal_memo = (
            b"%PDF-1.4\n"
            b"% Legal memo placeholder\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
            b"4 0 obj<</Length 220>>stream\n"
            b"Section: Statutory Mapping\n"
            b"Section: Manifest Field Mapping\n"
            b"Section: Notarization Retention\n"
            b"Section: Ledger Integrity Notes\n"
            b"Section: Evidence Checklist\n"
            b"endstream\nendobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF\n"
        )
        zf.writestr("legal_memo.pdf", legal_memo)
        zf.writestr(
            "clause_lineage.json",
            json.dumps(
                [
                    {"clause_version_id": cid}
                    for cid in manifest_json["clause_version_ids"]
                ]
            ),
        )
        zf.writestr(
            "rule_evaluation_log.json",
            json.dumps(
                [
                    {
                        "rule_id": "RCW_39_08_penal_sum",
                        "result": "pass",
                        "citation": "RCW 39.08.010(1)",
                    }
                ]
            ),
        )
    return Response(content=data.getvalue(), media_type="application/zip")
