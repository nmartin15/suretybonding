# Washington Performance Bond E-Bonding Platform V1 — PRD

> **Version:** 2.0 | **Date:** March 2026 | **Status:** CONFIDENTIAL — Internal engineering and legal review only

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Success Metrics](#2-success-metrics)
3. [Scope](#3-scope)
4. [User Roles and Journeys](#4-user-roles-and-journeys)
5. [Functional Requirements](#5-functional-requirements)
6. [Data Model](#6-data-model)
7. [API Design](#7-api-design)
8. [Integration Contracts](#8-integration-contracts)
9. [Non-Functional Requirements](#9-non-functional-requirements)
10. [Acceptance Tests](#10-acceptance-tests)
11. [Error Handling and Edge Cases](#11-error-handling-and-edge-cases)
12. [Authorization Model](#12-authorization-model)
13. [Rollout Plan (12 Weeks)](#13-rollout-plan-12-weeks)
14. [Risks and Mitigations](#14-risks-and-mitigations)
15. [Deliverables for Engineering Handoff](#15-deliverables-for-engineering-handoff)

---

## 1. Executive Summary

This document defines the product requirements for a hardened V1 platform that issues court-defensible Washington State public-works performance bonds. The platform produces HSM-signed manifests and exportable audit bundles that satisfy Washington notarial and electronic-signature expectations while minimizing bespoke legal review.

The E-Bonding platform replaces the current manual, paper-intensive surety bond issuance process with a digital workflow that enforces statutory compliance at every step, provides cryptographic proof of document integrity and signer identity, and packages all evidence into a litigation-ready audit bundle.

### 1.1 Problem Statement

Washington public-works performance bond issuance currently involves fragmented manual processes spanning multiple parties (broker, underwriter, obligee, notary). Each bond requires bespoke legal review to confirm clause compliance, signer authentication, and statutory alignment. This results in median issuance times exceeding 5 business days, high legal costs per bond, and audit bundles assembled ad hoc under litigation pressure.

### 1.2 Solution Overview

The platform digitizes the full issuance lifecycle through five interlocking capabilities: guided intake with Washington-specific field validation, an authoritative clause registry with carrier approval provenance, deterministic statutory rule checking, HSM-signed manifest generation with notarization evidence, and a permissioned ledger for immutable proof of issuance. Every bond produces a self-contained audit bundle within 5 minutes of request.

### 1.3 Target Outcome

By the end of the 12-week pilot, the platform will have issued at least 10 bonds for the pilot agency through the new workflow, with zero post-issue legal corrections required and each bond producing a valid audit bundle that passes all five acceptance tests defined in this document.

---

## 2. Success Metrics

All metrics are measured during the 12-week pilot period and gate the decision to proceed to multi-agency rollout.

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| Provenance completeness | 100% of bonds produce valid audit bundle within 5 min of request | T4 acceptance test on every issuance |
| Legal review reduction | 60% fewer bespoke counsel reviews vs. baseline for pilot bond class | Compare review requests: 12 weeks pre-pilot vs. pilot period |
| Time to issue (auto-approved) | Median < 8 hours from intake submission to signed PDF | Timestamp delta: `bond_requests.created_at` to `manifests.issued_at` |
| False positive clause matches | < 1% of auto-issued bonds require post-issue legal correction | Count of bonds needing amendment / total auto-issued |
| Acceptance test pass rate | 100% of T1–T5 pass in CI on every merge to main | CI pipeline dashboard |
| Platform availability | 99.9% during business hours (M–F 6 AM–10 PM PT) | Uptime monitoring (Datadog or equivalent) |

---

## 3. Scope

### 3.1 In Scope (V1)

- **Bond type:** Washington public-works performance bonds (RCW 39.08) for a single pilot agency.
- **Carrier:** single pilot carrier with delegated authority for the pilot bond class.
- **Users:** broker/principal, underwriter/carrier reviewer, platform legal reviewer, obligee (agency clerk).
- **Core outputs:** signed bond PDF, HSM-signed manifest (JSON), exportable audit bundle (ZIP).
- **Notarization:** Remote Online Notarization (RON) with wet-ink fallback pathway.
- **Ledger:** permissioned consortium ledger (manifest hash + event ID only).
- **CI/CD:** full acceptance test suite (T1–T5) gating every deployment.

### 3.2 Out of Scope (V1)

- Multi-carrier delegated authority beyond the pilot carrier.
- Public blockchain writes or token-based claim structures.
- Multi-agency rollout beyond pilot agency.
- Payment and maintenance bond types (future phases).
- Real-time premium calculation engine (pilot uses pre-calculated rates from carrier).
- End-user mobile application (web-only for V1).

### 3.3 Assumptions

1. Pilot carrier and pilot agency will sign an Acceptance Attestation for the audit bundle format and RON/wet-ink fallback before week 6.
2. Legal counsel validates the manifest schema and legal memo template before week 2.
3. HSM infrastructure (or sandbox equivalent) is provisioned by week 4.
4. Permissioned ledger node (or sandbox equivalent) is accessible by week 5.
5. Vector database for clause discovery is available from week 2 (Pinecone, Weaviate, or pgvector).
6. Pilot agency accepts RON per RCW 42.45 (Revised Uniform Law on Notarial Acts) or provides written specification of their wet-ink requirements.

---

## 4. User Roles and Journeys

### 4.1 Role Definitions

| Role | Description | Key Permissions |
|------|-------------|-----------------|
| Broker / Principal | Initiates bond request on behalf of the contractor | Create bond request, upload documents, sign bond, view own requests |
| Underwriter / Carrier Reviewer | Reviews risk, approves or rejects bond applications | View all requests, approve/reject, set clause overrides, manage carrier policy |
| Platform Legal Reviewer | Reviews flagged bonds that fail auto-issue criteria | View flagged requests, approve/reject with notes, manage clause registry |
| Obligee (Agency Clerk) | Receives and validates the final bond and audit bundle | View issued bonds for their agency, download audit bundles, verify manifests |
| System Admin | Manages platform configuration and user access | User management, HSM key rotation, ledger configuration, system settings |

### 4.2 Primary Journey: Bond Issuance (Happy Path)

The following describes the end-to-end flow for a bond that qualifies for auto-issuance.

1. Broker logs in, selects "New Bond Request," chooses bond type (WA Public Works Performance).
2. Guided intake collects: principal info, obligee agency, contract details, penal sum, project description, required attachments (contract, financials, SOS filing).
3. System validates all required Washington fields and file uploads against the intake schema.
4. Hybrid discovery runs: vector search identifies candidate clauses, deterministic metadata gate filters to only registry-approved clauses for the jurisdiction, bond type, and carrier.
5. Deterministic rule layer checks: statutory requirements (RCW 39.08), agency-specific templates, carrier policy limits, exposure calculations.
6. If all checks pass and exposure is within carrier auto-approve thresholds: system auto-selects clauses and proceeds to document assembly.
7. Document assembly generates bond PDF from approved clause version IDs, plus a plain-English summary document.
8. System sends signing request to broker/principal via e-sign adapter.
9. Upon principal signature: system triggers notarization flow (RON or wet-ink based on agency preference).
10. Upon notarization completion: system generates manifest JSON (document hash, signer metadata, notarization evidence, KYC pointer), signs manifest with platform HSM.
11. System writes manifest hash + event ID to permissioned ledger.
12. System generates audit bundle (ZIP: bond PDF, manifest, notarization evidence, KYC pointer, ledger proof, legal memo).
13. Bond status moves to `issued`. Obligee receives notification with secure download link for bond and audit bundle.

### 4.3 Secondary Journey: Human-in-Loop Review

When a bond request fails auto-issue criteria, it enters human review.

1. Deterministic rule layer or underwriting engine flags the request (reasons: clause confidence below threshold, exposure exceeds auto-approve limit, statutory rule ambiguity, missing carrier approval token).
2. System creates a review card showing: flagged clauses with diffs to nearest approved version, delta risk analysis, precedent history for similar bonds, specific rule failures with citations.
3. Platform legal reviewer or underwriter opens the review card.
4. Reviewer can: approve as-is, approve with clause substitutions, request additional information from broker, or reject with documented rationale.
5. If approved: flow resumes at step 7 of the happy path.
6. If rejected: broker receives notification with rejection rationale and can resubmit.

### 4.4 State Machine

Bond requests progress through the following states. Each transition is logged with actor, timestamp, and rationale.

| State | Description | Transitions To |
|-------|-------------|----------------|
| `draft` | Intake in progress, not yet submitted | `submitted` (broker submits) |
| `submitted` | Intake complete, pending rule evaluation | `auto_approved`, `review_required`, `rejected`, `kyc_failed` |
| `auto_approved` | All checks passed, within carrier policy | `signing` |
| `review_required` | Flagged for human review | `approved`, `rejected`, `info_requested` |
| `info_requested` | Reviewer needs additional docs from broker | `submitted` (broker resubmits) |
| `approved` | Human reviewer approved | `signing` |
| `signing` | Awaiting e-signature from principal | `signed`, `expired`, `signing_failed` |
| `signing_failed` | Signing operation failed after retries | `signing` (retry), `rejected` |
| `kyc_failed` | KYC verification failed; manual remediation required | `submitted` (retry KYC), `review_required`, `rejected` |
| `signed` | Principal signed, pending notarization | `notarizing` |
| `notarizing` | RON or wet-ink notarization in progress | `notarized`, `notarization_failed` |
| `notarization_failed` | Notarization attempt failed | `notarizing` (retry), `wet_ink_fallback` |
| `wet_ink_fallback` | Routed to wet-ink notarization process | `notarized` |
| `notarized` | Notarization complete, pending manifest generation | `issued` |
| `issued` | Manifest signed, ledger written, audit bundle generated | Terminal state |
| `rejected` | Bond request rejected | Terminal state (broker may create new request) |
| `expired` | Signing window expired (configurable, default 72 hours) | Terminal state (broker may re-initiate) |

---

## 5. Functional Requirements

### 5.1 FR-01: Guided Intake

**Purpose:** Collect all information required for bond issuance with Washington-specific validation.

- Multi-step form with progress indicator and save/resume capability.
- Required fields derived from RCW 39.08 and pilot agency filing requirements: principal legal name, UBI number, contractor registration number, obligee agency name and address, contract number, contract amount, penal sum (validated: must equal contract amount for WA public works), project description, project location (WA county).
- File uploads: executed contract (PDF), most recent financial statement, WA Secretary of State filing confirmation, additional documents per agency requirements.
- Validation: all fields validated client-side and server-side against intake schema (JSON Schema). File uploads checked for format, size limits, and virus scan.
- Draft persistence: broker can save and resume incomplete applications.

### 5.2 FR-02: Authoritative Clause Registry

**Purpose:** Maintain a versioned, immutable registry of approved bond clause language with carrier approval provenance.

- Each clause version has a unique, immutable `clause_version_id`.
- Clause metadata: `jurisdiction`, `bond_type`, `effective_date`, `expiration_date` (nullable), `text_hash` (SHA-256 of clause text), `carrier_approval_tokens` (array of carrier IDs that have approved this version), `created_by`, `created_at`.
- Clauses are append-only: modifications create new versions. Previous versions remain queryable but are marked superseded.
- Carrier approval is recorded as a signed token: `carrier_id`, `clause_version_id`, `approved_at`, `approved_by`, `approval_scope` (e.g., "WA public works performance, penal sum up to $5M").
- Registry exposes a deterministic lookup API: given jurisdiction + bond_type + carrier_id + effective_date, returns all approved clause versions.
- Full-text search and vector embeddings are generated for each clause version to support hybrid discovery, but vector similarity is never sufficient for issuance—only registry lookup governs what appears in the final bond.

### 5.3 FR-03: Hybrid Discovery and Deterministic Gating

**Purpose:** Use AI-assisted search to surface candidate clauses, then enforce strict metadata gating before any clause can be included in a bond.

- **Discovery layer:** vector similarity search (cosine distance) against clause embeddings to find candidate clauses matching the bond request context.
- **Gating layer:** every candidate must pass deterministic metadata checks: (a) clause is approved for this jurisdiction, (b) clause is approved for this bond type, (c) clause has a valid carrier approval token for the selected carrier, (d) clause `effective_date <= today` and (`expiration_date` is null or `>= today`), (e) clause `text_hash` matches stored text (integrity check).
- If any candidate fails gating, it is excluded with a logged reason.
- If fewer than the required clauses pass gating, the bond enters `review_required` state with a specific flag: `insufficient_approved_clauses`.
- **Confidence scoring:** the system computes a confidence score for the overall clause selection. If confidence is below a configurable threshold (default: 0.85), the bond enters `review_required`.

### 5.4 FR-04: Deterministic Rule Layer

**Purpose:** Enforce statutory, agency, and carrier rules as code with versioned rule definitions tied to citations.

Rules are organized into three tiers executed sequentially. A failure at any tier halts auto-issuance.

| Tier | Rule Source | Example Rules |
|------|-------------|---------------|
| Statutory | RCW 39.08, WAC 296-127 | Penal sum must equal contract amount. Bond must name the State of WA or political subdivision as obligee. Contractor must hold active WA registration. |
| Agency | Pilot agency filing requirements | Bond form must include agency-specific header. Notarization must be RON per agency policy (or wet-ink if specified). Bond must reference contract number in agency format. |
| Carrier | Pilot carrier underwriting guidelines | Exposure within carrier auto-approve threshold. Principal financial ratio within acceptable range. No outstanding claims on principal exceeding threshold. |

Each rule is stored as a versioned record: `rule_id`, `version`, `tier` (statutory/agency/carrier), `description`, `citation` (e.g., "RCW 39.08.010(1)"), `check_function_ref` (reference to deterministic check function), `effective_date`, `deprecated_date`. Rule changes trigger CI regression tests.

### 5.5 FR-05: Document Assembly

**Purpose:** Generate the final bond PDF and plain-English summary from approved clause versions and validated request data.

- Template engine assembles bond PDF by injecting: header (agency and carrier details), selected clause texts (referenced by `clause_version_id`), variable fields (principal name, penal sum, contract details, project description, effective dates), signature blocks (principal, surety, notary).
- Every clause in the assembled document is traceable to its `clause_version_id` in the manifest.
- Plain-English summary document generated alongside the bond: summarizes key terms, obligations, and conditions in non-legal language for the principal.
- PDF is generated as PDF/A-2b for long-term archival compliance.
- Document hash (SHA-256) is computed immediately after generation and stored in the manifest.

### 5.6 FR-06: Signer Provenance and Manifest

**Purpose:** Create a tamper-evident, HSM-signed manifest that binds the bond document to signer identity, notarization evidence, and ledger proof.

The manifest is a JSON document conforming to `manifest.schema.json` and includes the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `manifest_id` | UUID v4 | Unique identifier for this manifest |
| `schema_version` | semver string | Version of `manifest.schema.json` used |
| `bond_request_id` | UUID v4 | Reference to the originating bond request |
| `document_hash` | hex string | SHA-256 of the final bond PDF |
| `clause_version_ids` | array of UUIDs | All clause versions included in the bond |
| `rule_version_ids` | array of strings | All rule versions applied during evaluation |
| `principal_signer` | object | Name, email, KYC pointer (reference to KYC verification record, not PII itself), `signature_timestamp`, `signature_method` |
| `notarization_meta` | object | `notary_name`, `notary_commission_id`, `notary_state`, `notarization_type` (RON/wet-ink), `notary_certificate` (X.509 ref), `ron_session_id`, `ron_video_pointer` (S3 URI + checksum), `notarization_timestamp` |
| `platform_signature` | object | `algorithm` (e.g., ECDSA-P256), `key_id` (HSM key reference), `signature` (base64), `certificate_chain` (array of PEM certs) |
| `ledger_entry_id` | string | Identifier of the ledger record |
| `ledger_hash` | hex string | Hash stored on ledger (must equal SHA-256 of this manifest minus `platform_signature` and ledger fields) |
| `issued_at` | ISO 8601 | Timestamp of issuance |
| `jurisdiction` | string | Always `"WA"` for V1 |
| `bond_type` | string | Always `"public_works_performance"` for V1 |

### 5.7 FR-07: Notarization Adapter

**Purpose:** Integrate with RON providers and support wet-ink fallback for agencies that require it.

- **RON integration:** adapter interface supporting at least one RON provider (e.g., Notarize, DocVerify). Adapter handles session creation, signer identity verification, audio/video recording, notary certificate retrieval.
- **Audio/video retention:** RON recordings stored in S3 (or equivalent) with AES-256 encryption, pointer and checksum recorded in manifest. Retention per WA rules (minimum 10 years per RCW 42.45.280).
- **Wet-ink fallback:** if RON is unavailable or agency requires it, system generates a wet-ink notarization instruction package (PDF with signature pages, notary jurat, mailing instructions). System tracks wet-ink completion via manual upload of scanned notarized pages.
- **Notarization failure handling:** if RON session fails (network, identity verification failure, notary unavailability), system retries up to 2 times with exponential backoff, then offers wet-ink fallback. Failure details logged.

### 5.8 FR-08: Permissioned Ledger

**Purpose:** Provide an immutable, independently verifiable record of bond issuance.

- **Minimal on-chain footprint:** only `manifest_hash` (SHA-256 of the manifest JSON excluding `platform_signature` and ledger fields) and `event_id` are written to the ledger.
- **Consortium governance:** ledger participants include the platform operator, pilot carrier, and (optionally) pilot agency. Consensus requires platform + carrier.
- **Write-once:** ledger entries are append-only with no update or delete capability.
- **Verification API:** given a `manifest_id`, the system can query the ledger and confirm the stored hash matches the manifest, and the ledger timestamp is <= `manifest.issued_at`.
- **Ledger abstraction layer:** the system uses an adapter pattern so the underlying ledger technology (Hyperledger Fabric, R3 Corda, or database-backed audit log for sandbox) can be swapped without changing application code.

### 5.9 FR-09: Human-in-Loop Review Card

**Purpose:** Provide reviewers with all context needed to make an informed approve/reject decision in a single screen.

- Review card displays: bond request summary, flagged items with specific rule citations, clause diffs (selected vs. nearest approved version), delta risk analysis (how this bond compares to historical approvals on key risk dimensions), precedent history (up to 10 most similar previously issued bonds), one-click actions (approve, reject, request info, substitute clause).
- All reviewer actions are logged with timestamp, actor, and rationale (free text required for reject and clause substitution).
- SLA tracking: review cards have a configurable SLA (default: 4 business hours). Escalation notification fires if SLA is breached.

### 5.10 FR-10: Audit Bundle Export

**Purpose:** Package all evidence of a bond issuance into a self-contained, litigation-ready ZIP archive.

The audit bundle contains:

| Artifact | Format | Description |
|----------|--------|-------------|
| Bond PDF | PDF/A-2b | The final signed bond document |
| Manifest | JSON | HSM-signed manifest (`manifest.schema.json`) |
| Notarization evidence | X.509 cert + metadata JSON | Notary certificate and RON session metadata (video pointer, not video itself) |
| KYC pointer | JSON | Reference to KYC verification record (provider, verification ID, timestamp—not PII) |
| Ledger proof | JSON | Ledger entry ID, stored hash, ledger timestamp, verification query result |
| Legal memo | PDF | One-page memo mapping manifest fields to WA statutes and notarization retention rules |
| Clause lineage | JSON | For each clause in the bond: `clause_version_id`, version history, carrier approval tokens |
| Rule evaluation log | JSON | Complete log of all rules evaluated, results, and citations |

Bundle generation must complete within 5 minutes of request (T4 acceptance test). Bundle is stored in S3 with per-tenant encryption and retention policy (default 10 years).

---

## 6. Data Model

The following entities represent the core relational data model. All tables include `created_at`, `updated_at`, and `created_by` audit columns. All IDs are UUID v4 unless otherwise noted.

### 6.1 `clause_versions`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | Immutable clause version identifier |
| `clause_id` | UUID | FK | Groups versions of the same clause |
| `version` | integer | NOT NULL | Monotonically increasing per `clause_id` |
| `jurisdiction` | varchar(10) | NOT NULL, indexed | E.g., `"WA"` |
| `bond_type` | varchar(100) | NOT NULL, indexed | E.g., `"public_works_performance"` |
| `text` | text | NOT NULL | Full clause text |
| `text_hash` | char(64) | NOT NULL, UNIQUE | SHA-256 of text field |
| `effective_date` | date | NOT NULL | |
| `expiration_date` | date | nullable | Null = no expiration |
| `superseded_by` | UUID | FK nullable | Points to newer version if superseded |
| `carrier_approval_tokens` | jsonb | NOT NULL, default `[]` | Array of approval objects |
| `embedding_vector` | vector(1536) | indexed (ANN) | For hybrid discovery |

### 6.2 `bond_requests`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `principal_id` | UUID | FK to users | |
| `broker_id` | UUID | FK to users | May equal `principal_id` if self-filed |
| `obligee_id` | UUID | FK to agencies | |
| `carrier_id` | UUID | FK to carriers | |
| `penal_sum` | decimal(15,2) | NOT NULL | Must equal `contract_amount` for WA |
| `contract_id` | varchar(100) | NOT NULL | Agency contract number |
| `contract_amount` | decimal(15,2) | NOT NULL | |
| `project_description` | text | NOT NULL | |
| `project_county` | varchar(50) | NOT NULL | WA county |
| `selected_clause_ids` | UUID[] | NOT NULL after approval | References `clause_versions.id` |
| `status` | varchar(30) | NOT NULL, indexed | See state machine (Section 4.4) |
| `status_history` | jsonb | NOT NULL, default `[]` | Array of `{status, actor, timestamp, rationale}` |
| `intake_data` | jsonb | NOT NULL | Full validated intake payload |
| `rule_evaluation_log` | jsonb | nullable | Populated after rule evaluation |
| `review_card_data` | jsonb | nullable | Populated if `review_required` |
| `attachments` | jsonb | NOT NULL, default `[]` | Array of `{filename, s3_pointer, checksum, uploaded_at}` |

### 6.3 `manifests`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | Equals `manifest_id` in JSON |
| `bond_request_id` | UUID | FK, UNIQUE | One manifest per bond |
| `schema_version` | varchar(20) | NOT NULL | Semver of `manifest.schema.json` |
| `document_hash` | char(64) | NOT NULL | SHA-256 of bond PDF |
| `manifest_json` | jsonb | NOT NULL | Complete manifest per schema |
| `platform_signature` | text | NOT NULL | Base64 HSM signature |
| `key_id` | varchar(100) | NOT NULL | HSM key reference used for signing |
| `ledger_entry_id` | varchar(200) | nullable | Populated after ledger write |
| `ledger_hash` | char(64) | nullable | |
| `notarization_meta` | jsonb | NOT NULL | Notarization details |
| `issued_at` | timestamptz | NOT NULL | |

### 6.4 `audit_bundles`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `manifest_id` | UUID | FK, UNIQUE | One bundle per manifest |
| `s3_pointer` | text | NOT NULL | S3 URI for the ZIP archive |
| `s3_checksum` | char(64) | NOT NULL | SHA-256 of the ZIP file |
| `retention_until` | date | NOT NULL | Computed from issuance + `retention_days` |
| `retention_days` | integer | NOT NULL, default 3650 | 10 years default |

### 6.5 `ledger_events`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `manifest_id` | UUID | FK, UNIQUE | |
| `ledger_hash` | char(64) | NOT NULL | Hash written to ledger |
| `network` | varchar(50) | NOT NULL | E.g., `"hyperledger_fabric_pilot"` |
| `ledger_tx_id` | varchar(200) | NOT NULL | Transaction ID on the ledger |
| `timestamp` | timestamptz | NOT NULL | Ledger-confirmed timestamp |

### 6.6 `statutory_rules`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | varchar(50) | PK | E.g., `"RCW_39_08_penal_sum"` |
| `version` | integer | NOT NULL | |
| `tier` | enum | NOT NULL | `statutory`, `agency`, `carrier` |
| `description` | text | NOT NULL | Human-readable rule description |
| `citation` | varchar(200) | NOT NULL | E.g., `"RCW 39.08.010(1)"` |
| `check_function_ref` | varchar(200) | NOT NULL | Module path to check function |
| `effective_date` | date | NOT NULL | |
| `deprecated_date` | date | nullable | |

---

## 7. API Design

The platform exposes a RESTful API documented in `openapi.yaml`. All endpoints require authentication (JWT bearer token) and enforce role-based access per Section 4.1. Below are the primary endpoints.

### 7.1 Bond Request Lifecycle

| Method | Path | Description | Auth Roles |
|--------|------|-------------|------------|
| POST | `/api/v1/bonds` | Create new bond request (intake submission) | broker |
| GET | `/api/v1/bonds/{id}` | Retrieve bond request with current status | broker (own), underwriter, legal, obligee (own agency) |
| PATCH | `/api/v1/bonds/{id}` | Update draft bond request | broker (own, status=draft only) |
| POST | `/api/v1/bonds/{id}/submit` | Submit draft for evaluation | broker (own) |
| POST | `/api/v1/bonds/{id}/review` | Submit review decision (approve/reject/request-info) | underwriter, legal |
| GET | `/api/v1/bonds/{id}/review-card` | Get review card data | underwriter, legal |
| POST | `/api/v1/bonds/{id}/sign` | Trigger signing flow | broker |
| GET | `/api/v1/bonds` | List bond requests (filtered by role permissions) | all authenticated |

### 7.2 Manifest and Audit

| Method | Path | Description | Auth Roles |
|--------|------|-------------|------------|
| GET | `/api/v1/manifests/{id}` | Retrieve manifest JSON | underwriter, legal, obligee, admin |
| GET | `/api/v1/manifests/{id}/verify` | Verify manifest signature and ledger proof | all authenticated |
| GET | `/api/v1/audit-bundles/{manifest_id}` | Download audit bundle ZIP | underwriter, legal, obligee, admin |
| POST | `/api/v1/audit-bundles/{manifest_id}/generate` | Trigger audit bundle regeneration | admin |

### 7.3 Clause Registry

| Method | Path | Description | Auth Roles |
|--------|------|-------------|------------|
| GET | `/api/v1/clauses` | List clauses with filtering | underwriter, legal, admin |
| GET | `/api/v1/clauses/{id}/versions` | Get version history for a clause | underwriter, legal, admin |
| POST | `/api/v1/clauses` | Create new clause (or new version) | legal, admin |
| POST | `/api/v1/clauses/{id}/approve` | Record carrier approval token | underwriter |
| GET | `/api/v1/clauses/discover` | Hybrid discovery endpoint (vector + gating) | internal service only |

### 7.4 Error Contract

All error responses follow a standard envelope:

- HTTP status codes: `400` (validation), `401` (unauthenticated), `403` (unauthorized), `404` (not found), `409` (state conflict, e.g., approving an already-issued bond), `422` (business rule violation), `500` (internal), `503` (dependency unavailable).
- Response body: `{ "error": { "code": "RULE_CHECK_FAILED", "message": "...", "details": [...], "request_id": "..." } }`
- All 5xx errors trigger SIEM alert. All 4xx errors are logged with request context.

---

## 8. Integration Contracts

The platform depends on four external systems. Each integration uses an adapter pattern with a defined interface, allowing the underlying provider to be swapped.

| Integration | Interface | Provider (Pilot) | Fallback |
|-------------|-----------|------------------|----------|
| HSM Signing | `sign(payload) → {signature, key_id, cert_chain}`; `verify(payload, signature) → bool`; `rotate_key() → new_key_id` | AWS CloudHSM (or SoftHSM for sandbox) | N/A — signing is mandatory |
| RON Provider | `create_session(signer_info) → session_id`; `get_status(session_id) → {status, certificate, video_pointer}`; `get_recording(session_id) → {s3_uri, checksum}` | Notarize or DocVerify | Wet-ink fallback flow |
| Permissioned Ledger | `write(manifest_hash, event_id) → {tx_id, timestamp}`; `read(event_id) → {hash, timestamp}`; `verify(event_id, expected_hash) → bool` | Hyperledger Fabric (or DB-backed audit log for sandbox) | DB-backed audit log |
| KYC Provider | `verify_identity(principal_info) → {verification_id, status, provider, timestamp}` | Persona, Plaid Identity, or manual verification | Manual verification with uploaded docs |

---

## 9. Non-Functional Requirements

### 9.1 Security

- HSM for all platform signing operations. No private key material in application memory.
- Per-tenant encryption keys for data at rest (AES-256). Encryption key hierarchy: master key in HSM, data keys derived per tenant.
- TLS 1.3 for all data in transit.
- SIEM integration: all authentication events, authorization failures, HSM operations, ledger writes, and audit bundle exports logged to centralized SIEM.
- Key rotation: HSM signing keys rotated on a configurable schedule (default: annual). Emergency revoke procedure documented and tested quarterly.
- Access control: JWT-based authentication with role claims. API gateway enforces role-based access per endpoint (Section 7).
- Secret management: all credentials (database, HSM, RON provider, ledger) stored in AWS Secrets Manager (or equivalent) with audit trail.

### 9.2 Retention and Data Residency

- RON recordings: encrypted, stored in US-region S3 bucket, retained minimum 10 years per RCW 42.45.280.
- Bond PDFs and audit bundles: retained per configurable policy (default 10 years) aligned with WA public records retention schedules.
- PII: principal PII stored in a dedicated, encrypted data store with access logging. KYC results stored as pointers (`verification_id`), not raw PII.
- Right to deletion: platform supports PII deletion requests while preserving non-PII bond records (manifest, clause versions, ledger entries) required for public records compliance.

### 9.3 Availability and Performance

| Requirement | Target | Monitoring |
|-------------|--------|------------|
| Availability | 99.9% during business hours (M–F 6 AM–10 PM PT) | Synthetic monitoring + real-user monitoring |
| Intake form load | < 2 seconds (p95) | Front-end performance monitoring |
| Rule evaluation | < 10 seconds (p95) | Application metrics |
| Document assembly | < 30 seconds (p95) | Application metrics |
| Manifest signing | < 5 seconds (p95) | HSM latency metrics |
| Audit bundle generation | < 5 minutes (p99) | T4 acceptance test + application metrics |
| Ledger write confirmation | < 60 seconds (p95) | Ledger adapter metrics |
| Auto-issue end-to-end | Median < 8 hours | Timestamp analysis (`bond_requests.created_at` to `manifests.issued_at`) |

### 9.4 Testing

- **Legal regression suite:** every clause change and rule change triggers a full re-evaluation of all test cases against the updated registry/rules. Test cases cover known-good bonds, known-bad bonds, and edge cases identified by legal counsel.
- **Litigation simulation tests (T4):** run on every merge to main and nightly. Simulates a subpoena by requesting an audit bundle and validating completeness.
- **Integration tests:** HSM signing, RON session lifecycle, ledger write/read, KYC verification—each tested against sandbox or mock providers in CI.
- **Load testing:** simulate 50 concurrent bond requests to validate performance targets under expected peak load.

---

## 10. Acceptance Tests

These five tests gate every CI merge and every production deployment. All tests are machine-runnable and produce structured pass/fail output.

### 10.1 T1: Manifest Validation

**Input:** Issued bond PDF + generated manifest JSON.

**Steps:**

1. Compute SHA-256 of the bond PDF.
2. Assert `document_hash` in manifest equals computed hash.
3. Validate manifest JSON against `manifest.schema.json` (JSON Schema validation).
4. Extract `platform_signature` from manifest.
5. Verify signature against the manifest payload (manifest JSON minus `platform_signature` and ledger fields) using the certificate chain in `platform_signature.certificate_chain`.
6. Verify certificate chain terminates at a trusted root (platform CA).

**Expected:** All checks pass. Test returns `{ "test": "T1", "result": "pass", "manifest_valid": true }`.

### 10.2 T2: Notarization Evidence

**Input:** Manifest with `notarization_required=true`.

**Steps:**

1. Extract `notarization_meta` from manifest.
2. Resolve `notary_certificate`: fetch X.509 certificate, validate it is not expired and issuer chain is valid.
3. Resolve `ron_video_pointer` (if `notarization_type=RON`): verify S3 object exists, compute checksum, assert checksum matches pointer.
4. If `notarization_type=wet_ink`: verify `scanned_pages_pointer` exists and checksums match.
5. Verify `notarization_timestamp` is before or equal to manifest `issued_at`.

**Expected:** All evidence present and checksums match. Test returns `{ "test": "T2", "result": "pass" }`.

### 10.3 T3: Ledger Proof

**Input:** Manifest with `ledger_entry_id` and `ledger_hash`.

**Steps:**

1. Query permissioned ledger for `ledger_entry_id`.
2. Confirm stored hash on ledger equals `ledger_hash` from manifest.
3. Confirm ledger timestamp is less than or equal to manifest `issued_at`.
4. Compute expected `ledger_hash`: SHA-256 of manifest JSON excluding `platform_signature` and ledger fields. Confirm it matches both the ledger and the manifest.

**Expected:** Ledger proof verified. Test returns `{ "test": "T3", "result": "pass" }`.

### 10.4 T4: Litigation Simulation (Subpoena Drill)

**Input:** Audit bundle request for a given `manifest_id`.

**Steps:**

1. Trigger audit bundle export via `POST /api/v1/audit-bundles/{manifest_id}/generate`.
2. Measure time from request to ZIP availability.
3. Download ZIP and validate contents: bond PDF, manifest JSON, notarization evidence, KYC pointer JSON, ledger proof JSON, legal memo PDF, clause lineage JSON, rule evaluation log JSON.
4. Run T1 on the bond PDF + manifest from the bundle.
5. Run T2 on the manifest from the bundle.
6. Run T3 on the manifest from the bundle.
7. Validate legal memo PDF is non-empty and contains expected section headers.

**Expected:** Bundle produced within 5 minutes. All sub-validations pass. Test returns `{ "test": "T4", "result": "pass", "generation_time_seconds": N }`.

### 10.5 T5: Auto-Issue Policy Gate

**Input:** Bond request with pre-approved clause IDs and exposure within carrier auto-approve policy.

**Steps:**

1. Submit bond request via `POST /api/v1/bonds` with valid intake data and pre-approved clause references.
2. Trigger submission via `POST /api/v1/bonds/{id}/submit`.
3. Poll bond status until terminal state (timeout: 10 minutes for test purposes).
4. Assert status is `"issued"` (not `"review_required"`).
5. Retrieve manifest via `GET /api/v1/manifests/{id}`.
6. Run T1, T2, T3 on the manifest and associated bond PDF.
7. Verify no human review actions in the bond request `status_history`.

**Expected:** Bond auto-issued. Manifest and audit bundle created. No human review. Test returns `{ "test": "T5", "result": "pass", "auto_issued": true }`.

---

## 11. Error Handling and Edge Cases

| Scenario | System Behavior | User Experience |
|----------|----------------|-----------------|
| HSM unavailable during signing | Retry 3x with exponential backoff (1s, 4s, 16s). If all retries fail, bond moves to `signing_failed` state. PagerDuty alert fires. | Broker sees "Signing temporarily unavailable, we will retry automatically. You will be notified when signing is complete." |
| RON session fails mid-notarization | RON adapter logs failure reason. System retries up to 2x. On final failure, offers wet-ink fallback. | Broker sees "Notarization session interrupted. Retrying… [or] We can switch to wet-ink notarization." |
| Ledger write fails | Retry 3x. If all fail, bond issuance pauses in `notarized` state (pre-ledger). Alert fires. Bond can be issued once ledger is restored (idempotent write). | No user-facing impact during retry window. If extended outage, broker notified of delay. |
| Clause deprecated after selection but before signing | System re-evaluates clause selection before signing. If selected clause is now deprecated: substitute with superseding version if auto-approvable, otherwise route to review. | Broker notified: "Bond terms have been updated due to a clause revision. Please review the updated document." |
| Duplicate bond request (same principal + contract + agency) | System checks for existing non-rejected bond requests matching the tuple. If found, returns 409 Conflict with link to existing request. | Broker sees: "A bond request already exists for this contract. View existing request." |
| Penal sum does not equal contract amount | Intake validation rejects at submission. Rule: `RCW_39_08_penal_sum`. | Broker sees field-level error: "For WA public works performance bonds, penal sum must equal the contract amount (RCW 39.08)." |
| KYC verification fails | Bond moves to `kyc_failed` state. Broker can retry KYC or upload manual verification documents. | Broker sees: "Identity verification was unsuccessful. Please retry or upload verification documents." |
| Audit bundle requested for revoked/amended bond | System generates bundle with current bond status prominently flagged. Legal memo notes revocation/amendment history. | Obligee downloads bundle with clear status indicator: "REVOKED" or "AMENDED—see amendment history." |

---

## 12. Authorization Model

Access control uses role-based authorization with JWT claims. The following matrix defines endpoint access by role.

| Resource / Action | Broker | Underwriter | Legal | Obligee | Admin |
|-------------------|--------|-------------|-------|---------|-------|
| Create bond request | Yes | No | No | No | No |
| View own bond requests | Yes | Yes (all) | Yes (all) | Yes (own agency) | Yes (all) |
| Submit / update draft | Yes (own) | No | No | No | No |
| Review / approve / reject | No | Yes | Yes | No | No |
| Trigger signing | Yes (own) | No | No | No | No |
| View manifest | Yes (own) | Yes | Yes | Yes (own agency) | Yes |
| Download audit bundle | No | Yes | Yes | Yes (own agency) | Yes |
| Manage clause registry | No | No | Yes | No | Yes |
| Approve clause (carrier) | No | Yes | No | No | No |
| System configuration | No | No | No | No | Yes |
| Key rotation / revoke | No | No | No | No | Yes |

---

## 13. Rollout Plan (12 Weeks)

### 13.1 Phase 1: Foundation (Weeks 0–2)

- Legal mapping: map RCW 39.08, WAC 296-127, and RCW 42.45 to rule definitions. Draft initial `statutory_rules` records.
- Carrier/agency MOU: secure signed Acceptance Attestation for audit bundle format, RON/wet-ink preference, and pilot scope.
- Manifest schema: finalize `manifest.schema.json` with legal counsel review. Publish as versioned artifact.
- Infrastructure: provision development environment, database, vector DB, and sandbox HSM.
- OpenAPI spec: draft `openapi.yaml` covering all endpoints in Section 7.

### 13.2 Phase 2: Core Build (Weeks 2–6)

- Guided intake: multi-step form with WA-specific validation, file uploads, draft persistence.
- Clause registry: relational store with versioning, approval tokens, and deterministic lookup API.
- Hybrid discovery: vector embeddings + metadata gating pipeline.
- Deterministic rule layer: implement statutory, agency, and carrier rule checks with citation tracking.
- Document assembly: PDF generation from approved clauses, template engine, PDF/A-2b output.
- E-sign adapter stub: integrate with e-sign provider (DocuSign, Adobe Sign, or equivalent) for principal signature.
- RON adapter stub: interface defined, mock implementation for testing.

### 13.3 Phase 3: Provenance and Audit (Weeks 6–9)

- HSM signing: integrate with AWS CloudHSM (or SoftHSM sandbox). Implement manifest signing and verification.
- Manifest generator: full manifest JSON generation per schema, including all provenance fields.
- Ledger writes: integrate with permissioned ledger (or DB-backed audit log). Implement write, read, and verify operations.
- RON integration: connect to live RON provider. Implement session creation, recording retrieval, and failure handling.
- Review card UX: build human-in-loop review interface with clause diffs, risk analysis, and one-click actions.
- Audit bundle export: implement ZIP generation with all required artifacts and legal memo template.
- Acceptance tests T1–T5: implement and integrate into CI pipeline.

### 13.4 Phase 4: Pilot and Harden (Weeks 9–12)

- Pilot 10 issuances: issue 10 bonds through the full workflow with pilot carrier and agency.
- Litigation simulation: run T4 (subpoena drill) on all pilot bonds. Measure generation time and completeness.
- Legal memo finalization: legal counsel reviews and approves the legal memo template based on pilot results.
- Operational playbooks: document runbooks for key rotation, emergency revoke, ledger recovery, and incident response.
- Performance testing: validate all latency targets under expected load.
- Security review: penetration test, SIEM validation, access control audit.
- Go/no-go decision: based on success metrics (Section 2) from pilot data.

---

## 14. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agency rejects e-bond format or RON | Medium | High | Secure Acceptance Attestation in Phase 1. Implement wet-ink fallback. If agency rejects all electronic formats, pilot with a different agency. |
| Incorrect clause selection leads to invalid bond | Low | Critical | Vector discovery + strict metadata gating + human review for confidence < 0.85. Legal regression suite catches regressions. Post-issuance audit catches escapes. |
| HSM key compromise | Very Low | Critical | HSM hardware isolation. Key rotation schedule. Emergency revoke procedure tested quarterly. Signed key history enables forensic analysis. |
| Regulatory change to RCW 39.08 or RCW 42.45 | Low | High | Versioned statutory rules with effective/deprecated dates. Automated monitoring of WA legislative updates. Rule update pipeline tested in CI. |
| RON provider outage during signing window | Medium | Medium | Retry with backoff. Wet-ink fallback. SLA terms with RON provider. Second RON provider as backup (post-V1). |
| Ledger infrastructure unavailable | Low | Medium | Idempotent write design. Bond issuance pauses (does not fail) pending ledger. DB-backed audit log as fallback for sandbox/emergency. |
| Legal counsel delays attestation beyond week 2 | Medium | High | Engage counsel in week 0. Pre-draft manifest schema for review. Escalation path to project sponsor. |
| Pilot carrier revokes delegated authority mid-pilot | Very Low | Critical | MOU includes minimum pilot commitment. Contingency: identify backup carrier during Phase 1. |

---

## 15. Deliverables for Engineering Handoff

| Artifact | Format | Status | Owner |
|----------|--------|--------|-------|
| PRD (this document) | Markdown | V2.0 (this version) | Product |
| `manifest.schema.json` | JSON Schema | To be finalized in Phase 1 | Product + Legal |
| `openapi.yaml` | OpenAPI 3.1 | To be drafted in Phase 1 | Engineering + Product |
| `requirements.txt` | pip | To be generated from project setup | Engineering |
| `dev-requirements.txt` | pip | Includes test and CI dependencies | Engineering |
| `README.md` | Markdown | Runbook: setup, test, deploy, produce audit bundle | Engineering |
| Legal memo template | PDF template | To be drafted in Phase 1, finalized in Phase 4 | Legal |
| Acceptance test suite (T1–T5) | Python / pytest | To be implemented in Phase 3 | Engineering |
| CI pipeline config | GitHub Actions / equivalent | T1–T5 gating every merge | Engineering |
| Operational playbooks | Markdown / Confluence | Key rotation, revoke, ledger recovery, incident response | Engineering + Ops |

---

**Open question for pilot scoping:** Which specific pilot agency and bond class should be assumed for the acceptance test fixtures, `manifest.schema.json` field defaults, and agency-specific rule definitions? This decision gates the start of Phase 1 work on legal mapping and agency MOU.
