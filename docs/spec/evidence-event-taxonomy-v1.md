<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Evidence Event Taxonomy v1

> **Status**: Accepted (locked by [ADR-0008](../adr/0008-evidence-event-taxonomy-v1.md))
> **Schema version**: `evidence_taxonomy_version = 1`
> **Effective from**: v0.1.0 (M5)
> **Authors**: @merchloubna70-dot

This document defines the **twelve** evidence event types that Attestplane
records in v1. Each type is identified by a fixed `event_type` string used in
the `EventDraft.event_type` field; the substrate never validates the string
against this list at the hashing layer (canonical-JSON byte determinism is
governed only by [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md))
but adapters, exporters, and the obligation registry rely on the strings
defined here for cross-runtime semantic agreement.

The taxonomy is binding on:

- Concrete adapters (e.g., AIOS adapter, LangGraph adapter)
- The proof-bundle exporter (M5)
- The verifier library / CLI (M5)
- The EU AI Act / DORA obligation registries (M5)
- Public claims about "what Attestplane records"

The taxonomy is **not** binding on:

- Internal payload field names within a runtime's own event store
- Runtime-specific schemas (those live outside this repo per [ADR-0004 § 4](../adr/0004-aios-to-attestplane-boundary.md))

## Boundary recap

Every entry below is a **record-only** event. Per ADR-0004 § 1, Attestplane
never owns the underlying decision — it only records that a runtime made one.
Each entry explicitly states the would-be boundary violation it prevents.

## Naming convention

- `event_type` is `snake_case`, ends in `_event`, has no namespace prefix.
- Field names inside `payload` are `snake_case`, never `camelCase`. This matches
  the cross-language wire-format convention locked in `types.py` / `types.ts`.
- All timestamps inside `payload` MUST be RFC 3339 UTC microsecond `Z` form
  (canonicalization layer rejects others).
- All cryptographic digests inside `payload` MUST be lowercase hex SHA-256
  (64 chars). Other digest algorithms require an ADR.
- `decision` enum values are `UPPER_SNAKE_CASE`. Examples: `GRANTED`,
  `BLOCKED`, `PASS`, `REJECT`.

## Subject-reference rule

Any field that references a data subject (a natural person under GDPR
Art. 4(1)) MUST be wrapped in `SubjectRef`. Raw direct identifiers inside
`payload` are an Art. 4(5) violation and the relevant adapter MUST be
rejected at PR review. Adapters apply the wrapping; the substrate's type
system enforces it at the top level (`event.subject_ref` and
`event.human_verifier` fields) but cannot enforce it for nested fields
inside `payload` — that responsibility sits with the adapter.

## EU AI Act Article 12(2)(a) correlation fields

Four optional top-level fields on `EventDraft` carry Art. 12(2)(a) context
and are populated when relevant:

- `session_id` — runtime session / run identifier (free-form opaque token)
- `reference_db_ref` — the upstream resource the event refers to (policy id,
  budget id, lease id, etc.)
- `matched_input_ref` — content-addressed reference to the artifact under
  evaluation (typically a SHA-256 hex)
- `human_verifier` — `SubjectRef` for a human-in-the-loop reviewer

Each event-type entry below indicates which of these four to populate.

---

## 1. `tool_call_event`

**Purpose.** Records that a runtime initiated a tool / function / MCP call.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `tool_name` | string | Fully qualified tool name. Example: `"mcp.fs.read_file"`. |
| `tool_call_id` | string | Runtime-assigned correlation id; opaque to substrate. |
| `arguments_hash` | string (sha256 hex) | SHA-256 of the canonical-JSON encoding of arguments. Raw arguments MUST NOT appear. |
| `result_status` | enum | `"OK" \| "ERROR" \| "TIMEOUT" \| "CANCELLED"`. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `tool_version` | string | If runtime tracks tool versions. |
| `result_hash` | string (sha256 hex) | Hash of result body when present. Raw result MUST NOT appear. |
| `latency_ms` | integer | Wall-clock duration. |
| `error_code` | string | Stable error code when `result_status != "OK"`. |

**Required redactions:**

- Raw tool arguments (use `arguments_hash` only)
- Raw tool result body (use `result_hash` only)
- Any credential or secret embedded in arguments

**Correlation fields:** populate `session_id` with the runtime's session id;
`matched_input_ref` is unused.

**Boundary anti-requirement:** This event MUST NOT carry an `executed: true`
flag or any field implying Attestplane caused the call. Attestplane records
that the runtime initiated the call; it does not execute tools.

---

## 2. `policy_check_event`

**Purpose.** Records that a policy gate evaluated and produced a decision.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `policy_id` | string | Stable identifier for the policy. |
| `policy_version` | string | Version of the policy at evaluation time. |
| `decision` | enum | `"ALLOW" \| "BLOCK" \| "ALLOW_WITH_OBLIGATION"`. |
| `evidence_refs` | array of string | Content-addressed refs (sha256) of inputs the policy consumed. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `policy_expression_hash` | string (sha256 hex) | Hash of the rendered policy body. Raw expression MUST NOT appear. |
| `obligation_refs` | array of string | When `decision == "ALLOW_WITH_OBLIGATION"`, references to obligations registered with the runtime. |
| `evaluator_id` | string | Identity of the engine that evaluated (e.g., `"opa-1.x"`, `"cedar-3.x"`). |

**Required redactions:**

- Raw policy expression body (only the hash)
- Raw input values to the policy (only `evidence_refs`)

**Correlation fields:** `reference_db_ref` populated with the policy id.

**Boundary anti-requirement:** MUST NOT carry an `enforced: true` field.
Whether the runtime obeyed the decision is the runtime's responsibility, not
Attestplane's claim.

---

## 3. `human_approval_event`

**Purpose.** Records a human-in-the-loop approval/rejection.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `approval_kind` | enum | `"PRE_EXECUTION" \| "POST_EXECUTION" \| "OVERRIDE"`. |
| `decision` | enum | `"APPROVED" \| "REJECTED" \| "DEFERRED"`. |
| `requested_at` | string (RFC 3339) | When the approval was requested. |
| `decided_at` | string (RFC 3339) | When the human decided. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `decision_reason_hash` | string (sha256 hex) | Hash of the human's free-text reason. Raw text MUST NOT appear. |
| `escalation_level` | integer | 0-indexed escalation tier. |

**Required redactions:**

- Free-text reason (only the hash)
- Direct identifiers of the human reviewer (use `human_verifier` top-level
  field with `SubjectRef`)

**Correlation fields:** `human_verifier` is REQUIRED (this is the single event
type where the substrate-level field is non-optional).

**Boundary anti-requirement:** MUST NOT carry execution-side effects (no
`tool_call_dispatched: true` etc.). The approval is a fact; the consequence
is its own event.

---

## 4. `lease_lifecycle_event`

**Purpose.** Records that an execution-plane lease transitioned state.
Recording-only; the lease authority is the runtime per ADR-0004 § 2 row 1.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `lease_id` | string | Opaque runtime-assigned lease identifier. |
| `lifecycle` | enum | `"GRANTED" \| "CONSUMED" \| "EXPIRED" \| "REVOKED"`. |
| `transitioned_at` | string (RFC 3339) | Time of state change per the runtime. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `previous_lifecycle` | enum | Prior lifecycle value if known. |
| `cause` | string | Short structured cause code, e.g., `"BUDGET_EXHAUSTED"`. |
| `expires_at` | string (RFC 3339) | When the lease would have expired. |

**Required redactions:**

- Lease secrets, token bodies, signing keys, JWT contents

**Correlation fields:** `reference_db_ref` populated with the lease id.

**Boundary anti-requirement:** MUST NOT carry `granted_by_attestplane: true`
or any field implying Attestplane issued the lease.

---

## 5. `budget_event`

**Purpose.** Records that a budget decision occurred (allocation, observation,
breach). Recording-only.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `budget_id` | string | Opaque budget identifier. |
| `decision` | enum | `"ALLOCATED" \| "OBSERVED" \| "BREACHED" \| "RESET"`. |
| `observed_value` | number | Current consumption metric. |
| `threshold` | number | Threshold against which `observed_value` was compared. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `unit` | string | E.g., `"tokens"`, `"usd_cents"`, `"requests"`. |
| `period` | string | E.g., `"daily"`, `"per_run"`. |

**Required redactions:**

- Customer billing identifiers (use `budget_id` only)
- Invoice / contract refs

**Correlation fields:** `reference_db_ref` populated with the budget id.

**Boundary anti-requirement:** MUST NOT include `enforcement_applied: true`.
A budget breach is a fact; enforcement is the runtime's responsibility and
appears (if relevant) as a `policy_check_event` or `lease_lifecycle_event`.

---

## 6. `settlement_event`

**Purpose.** Records that a settlement / billing event occurred. Recording-only.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `settlement_id` | string | Opaque runtime-assigned settlement id. |
| `lifecycle` | enum | `"REQUESTED" \| "VERIFIED" \| "COMPLETED" \| "FAILED"`. |
| `amount_numerator` | integer | Amount in smallest currency unit. |
| `amount_currency` | string | ISO 4217 three-letter code, uppercase. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `counterparty_ref` | string | Hashed counterparty reference. Raw counterparty identifiers MUST NOT appear. |
| `failure_code` | string | Stable code when `lifecycle == "FAILED"`. |

**Required redactions:**

- Payment instrument fields (card PAN, IBAN, account number) — **never**
  present, hashed or otherwise
- Personal identifiers of counterparties (hash via `SubjectRef`)

**Correlation fields:** `reference_db_ref` populated with the settlement id.

**Boundary anti-requirement:** MUST NOT include payment-processor API
responses, gateway raw payloads, or anything that could replay a charge.

---

## 7. `worker_assignment_event`

**Purpose.** Records that a worker was assigned to a unit of work.
Recording-only.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `worker_id` | string | Opaque worker identifier. |
| `assignment_id` | string | Opaque assignment id. |
| `decision` | enum | `"ASSIGNED" \| "RELEASED" \| "REASSIGNED"`. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `capability_tag` | string | E.g., `"gpu-h100"`, `"region-eu-west-1"`. |
| `previous_worker_id` | string | When `decision == "REASSIGNED"`. |

**Required redactions:**

- Worker auth tokens, JWTs, signing keys
- Worker IP addresses / network locations

**Correlation fields:** `reference_db_ref` populated with the worker id.

**Boundary anti-requirement:** MUST NOT contain code or container image
references that could be used to reconstruct execution.

---

## 8. `runtime_lifecycle_event`

**Purpose.** Records that a runtime process started / stopped / restarted.
Recording-only.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `runtime_name` | string | Stable runtime identifier; matches the producing adapter's `runtime_name`. |
| `lifecycle` | enum | `"STARTED" \| "STOPPED" \| "RESTARTED" \| "CRASHED"`. |
| `runtime_version` | string | Semver or commit-sha of the runtime build. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `exit_code` | integer | When `lifecycle ∈ {STOPPED, CRASHED}`. |
| `node_id` | string | Hashed node/host identifier. |

**Required redactions:**

- Process credentials, environment secrets
- Raw command-line arguments (hash via separate `tool_call_event` if needed)

**Correlation fields:** none (this event is its own anchor).

**Boundary anti-requirement:** MUST NOT include startup config / secrets.
Runtime config integrity is out of scope for v1.

---

## 9. `gateway_decision_event`

**Purpose.** Records that an inbound-API gateway decided to admit or deny a
request. Recording-only.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `gateway_id` | string | Stable gateway identifier. |
| `decision` | enum | `"ADMITTED" \| "DENIED" \| "RATE_LIMITED"`. |
| `request_method` | string | HTTP method or RPC verb. |
| `request_path_hash` | string (sha256 hex) | SHA-256 of the request path. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `decision_reason_code` | string | Stable reason code. |
| `caller_ref` | string | Hashed caller identifier. |

**Required redactions:**

- Auth headers, bearer tokens, cookies — **never** present
- Raw request path / query string (use `request_path_hash`)
- Raw request body

**Correlation fields:** none.

**Boundary anti-requirement:** MUST NOT carry the request body, response
body, or any header value. The taxonomy is intentionally lossy.

---

## 10. `state_transition_event`

**Purpose.** Records that a runtime task / run / step transitioned state.
Recording-only.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `entity_kind` | enum | `"TASK" \| "RUN" \| "STEP" \| "WORKFLOW"`. |
| `entity_id` | string | Opaque runtime-assigned id. |
| `from_state` | string | UPPER_SNAKE_CASE state name. |
| `to_state` | string | UPPER_SNAKE_CASE state name. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `transition_reason` | string | Stable structured reason code. |
| `transitioned_at` | string (RFC 3339) | When the transition occurred per the runtime. |

**Required redactions:**

- Free-text reason fields (use `transition_reason` enumerated code only)

**Correlation fields:** `reference_db_ref` populated with the entity id.

**Boundary anti-requirement:** MUST NOT carry full entity payloads. The
event records the transition, not the entity's current value.

---

## 11. `eval_event`

**Purpose.** Records that an evaluation / scoring result was produced.
Recording-only.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `eval_id` | string | Opaque evaluation identifier. |
| `decision` | enum | `"PASS" \| "REJECT" \| "INCONCLUSIVE"`. |
| `evaluator_kind` | enum | `"AUTOMATED" \| "HUMAN" \| "ENSEMBLE"`. |
| `artifact_sha256` | string (sha256 hex) | The artifact under evaluation. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `score` | number | Numeric score when meaningful; bounds runtime-defined. |
| `criteria_id` | string | Reference to the evaluation criteria. |
| `evaluator_id` | string | Opaque id of the evaluator. For human evaluator, prefer `human_verifier` top-level field. |

**Required redactions:**

- Raw artifact content (only `artifact_sha256`)
- Free-text evaluator commentary (omit; if needed, hash separately)

**Correlation fields:** `matched_input_ref` populated with `artifact_sha256`;
`human_verifier` populated when `evaluator_kind == "HUMAN"`.

**Boundary anti-requirement:** MUST NOT include the artifact itself, the
evaluation prompt, or the model weights.

---

## 12. `routing_event`

**Purpose.** Records that an agent-to-agent (A2A) routing decision was made.
Recording-only.

**Required `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `route_id` | string | Opaque routing decision id. |
| `from_agent_ref` | string | Hashed source agent identifier. |
| `to_agent_ref` | string | Hashed destination agent identifier. |
| `decision` | enum | `"FORWARDED" \| "BLOCKED" \| "REWRITTEN"`. |

**Optional `payload` fields:**

| Field | Type | Notes |
|-------|------|-------|
| `route_policy_id` | string | Policy that produced the decision. |
| `rewrite_reason` | string | Stable code when `decision == "REWRITTEN"`. |

**Required redactions:**

- Direct agent identifiers (always hashed before recording)
- The message body itself (record via a separate `tool_call_event` or
  similar if needed; do not embed in the routing event)

**Correlation fields:** none.

**Boundary anti-requirement:** MUST NOT carry the A2A message body. Routing
decisions and message bodies are decoupled at the substrate level.

---

## Versioning

This is `evidence_taxonomy_version = 1`. The taxonomy version is independent
of `chain.schema_version` (frozen at 1 per ADR-0002) and independent of
`anchor_schema_version` (per ADR-0003).

Adding a new event type to v1 requires:

- An ADR amendment (`ADR-0008-amendment-N`) or a superseding ADR.
- A new entry below the existing twelve, with no renaming of existing entries.
- Public release-note announcement.

Removing or renaming an event type from v1 requires a `v2` taxonomy and a
1-minor-version deprecation window. The old strings remain readable.

Adding a new **required** `payload` field to an existing event type is a
**breaking change** and requires a `v2` taxonomy. Adding a new **optional**
field is non-breaking.

## Cross-references

- [ADR-0008](../adr/0008-evidence-event-taxonomy-v1.md) — accepts this taxonomy
- [ADR-0004](../adr/0004-aios-to-attestplane-boundary.md) — boundary that
  every entry above respects
- [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md) — the
  underlying canonical-JSON / hash-chain primitives
- `sdk/python/src/attestplane/event_types.py` — the constants module
- `sdk/typescript/src/event_types.ts` — TypeScript counterpart
- `docs/policy/forbidden_claims.md` — public-claim phrasings tied to this taxonomy
