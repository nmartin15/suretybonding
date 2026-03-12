from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


@dataclass
class GeneratedKeyMaterial:
    private_key_pem: str | None
    certificate_pem: str
    key_ref: str | None
    not_before: datetime
    not_after: datetime


class DbPemSigningProvider:
    backend_name = "db_pem"

    def generate(self) -> GeneratedKeyMaterial:
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        not_before = datetime.now(timezone.utc)
        not_after = not_before + timedelta(days=365)
        cert = _self_signed_cert(public_key, private_key, not_before, not_after)
        private_key_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("utf-8")
        certificate_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        return GeneratedKeyMaterial(
            private_key_pem=private_key_pem,
            certificate_pem=certificate_pem,
            key_ref=None,
            not_before=not_before,
            not_after=not_after,
        )

    def sign(
        self, payload: bytes, private_key_pem: str | None, key_ref: str | None = None
    ) -> bytes:
        if not private_key_pem:
            raise ValueError("Missing PEM key material for db_pem signing backend")
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"), password=None
        )
        return private_key.sign(payload, ec.ECDSA(hashes.SHA256()))


class MockHsmSigningProvider:
    backend_name = "mock_hsm"

    def __init__(self) -> None:
        self._keys: dict[str, ec.EllipticCurvePrivateKey] = {}

    def generate(self) -> GeneratedKeyMaterial:
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        not_before = datetime.now(timezone.utc)
        not_after = not_before + timedelta(days=365)
        cert = _self_signed_cert(public_key, private_key, not_before, not_after)
        key_ref = f"mock-hsm-{uuid.uuid4()}"
        self._keys[key_ref] = private_key
        certificate_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        return GeneratedKeyMaterial(
            private_key_pem=None,
            certificate_pem=certificate_pem,
            key_ref=key_ref,
            not_before=not_before,
            not_after=not_after,
        )

    def sign(
        self, payload: bytes, private_key_pem: str | None, key_ref: str | None = None
    ) -> bytes:
        if not key_ref:
            raise ValueError("Missing key_ref for mock_hsm signing")
        private_key = self._keys.get(key_ref)
        if private_key is None:
            raise ValueError("HSM key handle not loaded in runtime")
        return private_key.sign(payload, ec.ECDSA(hashes.SHA256()))

    def has_key(self, key_ref: str | None) -> bool:
        return bool(key_ref and key_ref in self._keys)


def _self_signed_cert(
    public_key: ec.EllipticCurvePublicKey,
    private_key: ec.EllipticCurvePrivateKey,
    not_before: datetime,
    not_after: datetime,
) -> x509.Certificate:
    return (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name(
                [
                    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    x509.NameAttribute(
                        NameOID.ORGANIZATION_NAME, "SuretyBonding Dev CA"
                    ),
                    x509.NameAttribute(
                        NameOID.COMMON_NAME, "SuretyBonding Active Signing Cert"
                    ),
                ]
            )
        )
        .issuer_name(
            x509.Name(
                [
                    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    x509.NameAttribute(
                        NameOID.ORGANIZATION_NAME, "SuretyBonding Dev CA"
                    ),
                    x509.NameAttribute(
                        NameOID.COMMON_NAME, "SuretyBonding Active Signing Cert"
                    ),
                ]
            )
        )
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(_to_naive_utc(not_before))
        .not_valid_after(_to_naive_utc(not_after))
        .sign(private_key=private_key, algorithm=hashes.SHA256())
    )
