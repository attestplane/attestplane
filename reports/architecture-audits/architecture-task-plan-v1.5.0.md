<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Medium Development Plan for v1.5.0

## Concise Plan

- Wire the frozen ADR-0010 `ReasonCodeV1` enum into `BundleVerificationResult` as an additive field alongside the existing `att.verify.*` taxonomy. This closes the most impactful medium-scope product gap since v1.0.0: downstream tooling (audit reports, compliance evidence packs, regulator dashboards) gets a machine-readable semantic code without changing the existing reason-code surface.
- Add cross-SDK conformance vectors that pin the new `reason_code` field for every positive and negative verify scenario.
- Ship the NIS2 Article 21 and GDPR Article 30 obligation registry stubs, following the existing `load_eu_ai_act_article_12` / `load_dora_article_8` pattern.
- Publish a docs task that records the v1.5.0 user-visible delta and validation evidence, without touching `CHANGELOG.md` or release workflows.
- Reference the existing open issues for signing/anchoring integration (deferred to v2.0.0 architecture-level redesign) and the dual-taxonomy cleanup ADR to avoid duplication.

## P0 Issues

### ISSUE 1 · [P0]\[verifier\]\[api\] Wire ReasonCodeV1 into BundleVerificationResult

**Priority**: P0  
**Owner**: verifier / SDK API  
**Affected modules**:

- Python SDK `verifier.py` — `BundleVerificationResult` dataclass
- Python SDK `reason_codes.py` — `ReasonCodeV1` enum (already frozen, additive-only)
- Python SDK `verify_reason_codes.py` — reason-derivation bridge
- TypeScript SDK `verifier.ts` — mirror change
- CLI `main.py` — `--json` and `--explain` serialization
- Proof bundle schema (if `reason_code` is exposed in `verification_report`)

**Acceptance criteria**:

1. `BundleVerificationResult` gains an additive `reason_code: ReasonCodeV1 | None` field that does not break existing consumers reading `ok`, `reasons`, `error_code`, or `anchoring`.
2. Every verify outcome (OK, chain mismatch, schema invalid, signature missing, anchor invalid, etc.) produces the correct ADR-0010 ReasonCodeV1 value.
3. The existing `VERIFY_REASON_*` / `att.verify.*` codes remain unchanged and continue to be emitted in `reasons`.
4. TypeScript SDK exposes an isomorphic `reasonCode` field in its verification result type.
5. CLI `--json` output includes `"reason_code": "<value>"` when available, `null` when the result spans multiple distinct codes.
6. Backward compatibility is maintained: old consumers see no new required fields, no removed fields, and no changed field names.

**Validation commands**:

```bash
cd sdk/python && python3.11 -m pytest tests/ -k 'verifier or reason_code or taxonomy' -x -q --tb=short 2>&1 | tail -20
cd sdk/typescript && npm test -- --runInBand -t 'verifier|reasonCode|taxonomy'
git diff --check
```

**Rollout / migration notes**:

- The new `reason_code` field is additive-only (`None` when multiple distinct codes apply).
- Do not remove or rename `error_code`, `reasons`, or any existing `BundleVerificationResult` fields.
- The bridge logic should map every `VerifyReasonCodeV1` value to a canonical `ReasonCodeV1` value (e.g., `att.verify.canonical_mismatch` → `CHAIN_EVENT_HASH_MISMATCH`). For multi-reason outcomes, leave `reason_code` as `None` and document that consumers should iterate `reasons` for the full picture.

## P1 Issues

### ISSUE 2 · [P1]\[test\]\[conformance\] Add cross-SDK conformance vectors for ReasonCodeV1

**Priority**: P1  
**Owner**: conformance  
**Affected modules**:

- Python conformance vectors
- Python verifier conformance tests
- TypeScript verifier conformance tests
- Fixture-lock maintenance

**Acceptance criteria**:

1. Add a conformance vector set that maps every ReasonCodeV1 value (from `CHAIN_OK` through `VERIFIER_INTERNAL_ERROR`) to a known proof-bundle fixture and its expected verify outcome.
2. Include positive vectors: bundles that verify cleanly → `CHAIN_OK`, valid-signature bundles → `SIGNATURE_OK`, valid-anchor bundles → `ANCHOR_OK`.
3. Include negative vectors: tampered-hash bundle → `CHAIN_EVENT_HASH_MISMATCH`, missing-signature bundle → `SIGNATURE_MISSING`, expired-cert anchor → `ANCHOR_CERT_EXPIRED`, etc.
4. Python and TypeScript conformance runners each assert expected reason_code against the vector's expected value.
5. The conformance fixtures are added to the existing fixture-lock validation to prevent accidental regeneration.

**Validation commands**:

```bash
cd sdk/python && python3.11 -m pytest tests/conformance -k 'reason_code or ReasonCodeV1' -x -q --tb=short 2>&1 | tail -20
cd sdk/python && python3.11 -m pytest sdk/python/tests/conformance -k 'reason_code' -x -q --tb=short 2>&1 | tail -20
cd sdk/typescript && npm test -- --runInBand -t 'conformance|reasonCode'
python3.11 scripts/conformance/verify_fixture_lock.py
git diff --check
```

**Rollout / migration notes**:

- New fixture files must not be added under a path that would conflict with the existing v1 conformance vector layout.
- Update locked fixture hashes explicitly; do not regenerate unrelated fixtures.
- The vector schema must carry both the expected `ReasonCodeV1` value and the existing expected `att.verify.*` code(s) to pin the bridge mapping.

### ISSUE 3 · [P1]\[conformance\]\[obligations\] Ship NIS2 Article 21 and GDPR Article 30 obligation registry stubs

**Priority**: P1  
**Owner**: conformance / obligations  
**Affected modules**:

- `obligations/nis2_article_21.json` (new file)
- `obligations/gdpr_article_30.json` (new file)
- `obligations/__init__.py` — add `load_nis2_article_21`, `load_gdpr_article_30`
- `obligations/registry.py` — add loader references
- Python conformance tests for obligations

**Acceptance criteria**:

1. NIS2 Article 21 JSON registry follows the same schema as `eu_ai_act_article_12.json`, covering at least the incident notification (Art 21(2)), supply chain security (Art 21(2)(d)), and risk assessment (Art 21(1)) obligations, each mapped to the appropriate v1 event types.
2. GDPR Article 30 JSON registry covers record-of-processing-activities (Art 30(1)), categories of processing (Art 30(1)(a-f)), and technical-organisational measures (Art 30(5)) obligations.
3. Both registries load successfully via `Registry.load_file()` and pass the existing `test_obligation_registry_structure` suite.
4. `load_all_registries()` returns both new registries alongside the existing EU AI Act and DORA registries.
5. Each entry's `implementation_status` is set to `designed_toward` (stub, not field-supported) with a note referencing the future implementation issue.

**Validation commands**:

```bash
cd sdk/python && python3.11 -m pytest tests/ -k 'obligation or registry' -x -q --tb=short 2>&1 | tail -20
cd sdk/python && python3.11 -c "from attestplane.obligations import load_all_registries; r = load_all_registries(); assert len(r) >= 4, f'expected >=4 registries, got {len(r)}'"
git diff --check
```

**Rollout / migration notes**:

- These are stub registries only. Do not claim field-level compliance for NIS2 or GDPR; every entry must carry `implementation_status: "designed_toward"` and an explicit `"note": "stub shipped for v1.5.0; field-level implementation tracked in #<follow-up-issue>"`.
- Do not modify existing EU AI Act or DORA entries.

## P2 Issues

### ISSUE 4 · [P2]\[docs\]\[release\] Document the v1.5.0 user-visible delta and validation evidence

**Priority**: P2  
**Owner**: docs / release  
**Affected modules**:

- docs
- validation evidence
- runbooks

**Acceptance criteria**:

1. Document the v1.5.0 user-visible delta: `BundleVerificationResult.reason_code` (ADR-0010), new obligation registries (NIS2 Art 21, GDPR Art 30), and CLI `--json` serialization of `reason_code`.
2. Record the validation evidence from ISSUE 1 and ISSUE 3 on the task issue before close.
3. Link the documentation to the source planning issue and the three task issues.
4. Keep wording within claim-safety boundaries and do not touch `CHANGELOG.md`.

**Validation commands**:

```bash
markdown-link-check docs/**/*.md
git diff --check
```

**Rollout / migration notes**:

- This is support work for the product increments in ISSUE 1 and ISSUE 3.
- Do not modify release tags, publish artifacts, or weaken gates.
- Documentation must not imply that NIS2 or GDPR compliance is certified or audited.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.0.0","consultation_level":"feature","head_sha":"3b1ead442184599a68af266e9a564dbcb02acc12","issues":[{"acceptance_criteria":["BundleVerificationResult gains an additive reason_code: ReasonCodeV1 | None field that does not break existing consumers reading ok, reasons, error_code, or anchoring.","Every verify outcome (OK, chain mismatch, schema invalid, signature missing, anchor invalid, etc.) produces the correct ADR-0010 ReasonCodeV1 value.","The existing VERIFY_REASON_* / att.verify.* codes remain unchanged and continue to be emitted in reasons.","TypeScript SDK exposes an isomorphic reasonCode field in its verification result type.","CLI --json output includes reason_code when available, null for multi-reason outcomes.","Backward compatibility is maintained with no new required fields."],"modules":["Python SDK verifier.py — BundleVerificationResult","Python SDK reason_codes.py — ReasonCodeV1 enum","Python SDK verify_reason_codes.py — reason-derivation bridge","TypeScript SDK verifier.ts — mirror change","CLI main.py — JSON serialization"],"ordinal":1,"priority":"P0","rollout_notes":"Additive field only (None when multiple distinct codes apply). Do not remove or rename error_code, reasons, or existing fields. Bridge maps every VerifyReasonCodeV1 to a canonical ReasonCodeV1.","title":"[P0][verifier][api] Wire ReasonCodeV1 into BundleVerificationResult","validation_commands":["cd sdk/python && python3.11 -m pytest tests/ -k 'verifier or reason_code or taxonomy' -x -q --tb=short 2>&1 | tail -20","cd sdk/typescript && npm test -- --runInBand -t 'verifier|reasonCode|taxonomy'","git diff --check"]},{"acceptance_criteria":["Conformance vector set mapping every ReasonCodeV1 value to a known proof-bundle fixture and expected verify outcome.","Positive vectors: clean bundles → CHAIN_OK, valid-signature → SIGNATURE_OK, valid-anchor → ANCHOR_OK.","Negative vectors: tampered-hash → CHAIN_EVENT_HASH_MISMATCH, missing-signature → SIGNATURE_MISSING, expired-cert → ANCHOR_CERT_EXPIRED, etc.","Python and TypeScript runners each assert expected reason_code.","Fixtures are part of existing fixture-lock validation."],"modules":["Python conformance vectors","Python verifier conformance tests","TypeScript verifier conformance tests","Fixture-lock maintenance"],"ordinal":2,"priority":"P1","rollout_notes":"New fixture files must not conflict with existing v1 layout. Update locked fixture hashes explicitly; do not regenerate unrelated fixtures.","title":"[P1][test][conformance] Add cross-SDK conformance vectors for ReasonCodeV1","validation_commands":["cd sdk/python && python3.11 -m pytest tests/conformance -k 'reason_code or ReasonCodeV1' -x -q --tb=short 2>&1 | tail -20","cd sdk/python && python3.11 -m pytest sdk/python/tests/conformance -k 'reason_code' -x -q --tb=short 2>&1 | tail -20","cd sdk/typescript && npm test -- --runInBand -t 'conformance|reasonCode'","python3.11 scripts/conformance/verify_fixture_lock.py","git diff --check"]},{"acceptance_criteria":["NIS2 Article 21 JSON registry follows the same schema as eu_ai_act_article_12.json, covering incident notification (Art 21(2)), supply chain security (Art 21(2)(d)), and risk assessment (Art 21(1)).","GDPR Article 30 JSON registry covers record-of-processing-activities (Art 30(1)), categories of processing (Art 30(1)(a-f)), and technical-organisational measures (Art 30(5)).","Both registries load via Registry.load_file() and pass existing test_obligation_registry_structure.","load_all_registries() returns both new registries alongside existing ones.","Every entry carries implementation_status: designed_toward with a follow-up note."],"modules":["obligations/nis2_article_21.json (new)","obligations/gdpr_article_30.json (new)","obligations/__init__.py — add load_* functions","obligations/registry.py — add loader references","Python conformance tests for obligations"],"ordinal":3,"priority":"P1","rollout_notes":"Stub registries only; every entry must carry implementation_status: designed_toward and an explicit follow-up note. Do not modify existing EU AI Act or DORA entries.","title":"[P1][conformance][obligations] Ship NIS2 Article 21 and GDPR Article 30 obligation registry stubs","validation_commands":["cd sdk/python && python3.11 -m pytest tests/ -k 'obligation or registry' -x -q --tb=short 2>&1 | tail -20","cd sdk/python && python3.11 -c \"from attestplane.obligations import load_all_registries; r = load_all_registries(); assert len(r) >= 4, f'expected >=4 registries, got {len(r)}'\"","git diff --check"]},{"acceptance_criteria":["Document v1.5.0 user-visible delta: BundleVerificationResult.reason_code, new obligation registries, CLI --json serialization.","Record validation evidence from ISSUE 1 and ISSUE 3 on the task issue.","Link documentation to source planning issue and task issues.","Keep wording within claim-safety boundaries; do not touch CHANGELOG.md."],"modules":["docs","validation evidence","runbooks"],"ordinal":4,"priority":"P2","rollout_notes":"Support work only. Do not modify release tags, publish artifacts, or weaken gates. Documentation must not imply NIS2/GDPR compliance is certified.","title":"[P2][docs][release] Document the v1.5.0 user-visible delta and validation evidence","validation_commands":["markdown-link-check docs/**/*.md","git diff --check"]}],"milestone_tag":"v1.5.0","plan_level":"medium","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
