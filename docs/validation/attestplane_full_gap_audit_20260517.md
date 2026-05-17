# Attestplane Full Gap Audit — 2026-05-17

Repository: `/Users/macworkers/Documents/attestplane/repo`
Remote: `https://github.com/attestplane/attestplane.git`
HEAD: `7e6e5e414fe71ed3ee02de919d18799be8bdcc6a`
Scope: whole-repository product, architecture, OSS governance, compliance-claim, SDK, CI, and release-readiness audit.

## 1. Executive Summary

Attestplane is currently a credible **v0.0.1-alpha core hash-chain substrate**: Python and TypeScript SDKs implement typed event drafts, restricted canonical JSON, SHA-256 event hashing, in-memory append-only sequencing, chain verification, and cross-language golden vectors. Local verification passed: Python 66 tests, TypeScript 51 tests, Python mypy/ruff, TypeScript typecheck/lint, and `scripts/check-policy.sh`.

It is **not yet** a complete compliance/auditor product. The verifier CLI, proof bundle, framework obligation registry, auditor export schema, runtime adapters, durable storage, and RFC-3161 anchoring code are missing or docs-only. The safest positioning today is: **Apache-2.0 alpha SDKs for tamper-evident AI-agent audit event chains, with selected EU AI Act Article 12(2)(a) fields and cross-language hash conformance.**

Go / No-Go: continue TestPyPI/npm alpha only with claim-safety cleanup. No-Go for beta/GA, enterprise-ready, regulator-ready, DORA-ready, or externally anchored evidence-chain claims.

Execution note: `ask_opus.sh reviewer` was attempted under escalation but failed with `API Error: 403 Request not allowed`; this report is based on local repository evidence and GitHub CLI status.

## 2. Repository Fact Baseline

| Item | Result |
|---|---|
| Current branch | `main` |
| HEAD SHA | `7e6e5e414fe71ed3ee02de919d18799be8bdcc6a` |
| Clean before report generation | yes (`git status --porcelain` empty) |
| origin/main sync | after `git fetch origin main`, `main...origin/main = 0 ahead / 0 behind` |
| Open PRs | none (`gh pr list` returned `[]`) |
| Open issues | none (`gh issue list` returned `[]`) |
| Latest main workflow status | HEAD has `sign-release`, `reproducible-build`, `sbom`, `osv-scanner`, `ossf-scorecard`, `ci`, `codeql` all `success` |

Recent 10 commits:

```text
7e6e5e4 fix(ci): bump cosign-installer v3 → v4.1.2 for cosign v3 asset format
04655b6 ci(release): cosign keyless sign GitHub Releases + README release badge
7268ca5 ci(lychee): whitelist www.npmjs.com (anti-bot 403, not broken)
341edbf docs: post-v0.0.1-alpha consistency pass + add CHANGELOG
c5083f3 docs(adr,readme): ADR-0003 TSA anchoring + npm alpha install guidance
bf50665 ci(publish): add manage-npm.yml for dist-tag administration
45c05c5 docs(readme): npm package name is @attestplane/attestplane
40d3e21 ci(publish): add Python (Test)PyPI + npm publish workflows for v0.0.1 alpha
7cecd2f docs(governance): drop Chinese gloss from §1 Mission
0be6161 chore(governance): CODEOWNERS + PR-template AI disclosure + CONTRIBUTORS
```

Workflow files present: `.github/workflows/ci.yml`, `codeql.yml`, `manage-npm.yml`, `osv-scanner.yml`, `publish-python.yml`, `publish-typescript.yml`, `reproducible-build.yml`, `sbom.yml`, `scorecard.yml`, `sdk-python.yml`, `sdk-typescript.yml`, `sign-release.yml`.

## 3. File Tree Index

Top-level: `.github/`, `docs/`, `scripts/`, `sdk/`, `README.md`, `CHANGELOG.md`, `GOVERNANCE.md`, `SECURITY.md`, `TRADEMARK.md`, `CONTRIBUTING.md`, `CONTRIBUTING_zh.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTORS.md`, `DCO.txt`, `LICENSE`, `LICENSES/`, `NOTICE`, `REUSE.toml`.

Python SDK: `sdk/python/src/attestplane/__init__.py`, `canonical.py`, `hashchain.py`, `substrate.py`, `types.py`, `py.typed`, `sdk/python/tests/`, `sdk/python/tests/conformance/vectors.json`, `sdk/python/pyproject.toml`, `sdk/python/README.md`.

TypeScript SDK: `sdk/typescript/src/index.ts`, `canonical.ts`, `hashchain.ts`, `substrate.ts`, `types.ts`, `sdk/typescript/test/`, `package.json`, `package-lock.json`, `tsconfig.json`, `README.md`, `dist/`.

Docs: `docs/adr/0000-template.md`, `0001-use-apache-2-0-license.md`, `0002-substrate-data-model-and-hash-chain-v0.md`, `0003-tsa-rfc-3161-anchoring.md`, `README.md`; `docs/validation/` exists. Scripts: `scripts/check-policy.sh`. No root `examples/`, `demo/`, or standalone `conformance/` directory was found.

## 4. Current Implemented Capabilities

| Module | Paths | Language | Status | Tests | Docs | CI gate |
|---|---|---|---|---|---|---|
| Repository governance | README.md; GOVERNANCE.md; CONTRIBUTING.md; DCO.txt; CODE_OF_CONDUCT.md; SECURITY.md; TRADEMARK.md; NOTICE; LICENSE; REUSE.toml; .github/CODEOWNERS | Markdown/policy | implemented | CI policy, REUSE, DCO, markdown/yaml/spell gates | yes | ci.yml |
| Python SDK types/canonical/hashchain/substrate | sdk/python/src/attestplane/types.py; canonical.py; hashchain.py; substrate.py | Python | implemented | 66 local tests passed; mypy and ruff passed | sdk/python/README.md; ADR-0002 | sdk-python.yml |
| TypeScript SDK types/canonical/hashchain/substrate | sdk/typescript/src/types.ts; canonical.ts; hashchain.ts; substrate.ts | TypeScript | implemented | 51 local tests passed; typecheck and biome passed | sdk/typescript/README.md | sdk-typescript.yml |
| Conformance vectors | sdk/python/tests/conformance/vectors.json; sdk/python/tests/test_conformance.py; sdk/typescript/test/conformance.test.ts | JSON/Python/TypeScript | implemented | Python and TS replay same vectors | ADR-0002; SDK READMEs | sdk-python.yml; sdk-typescript.yml |
| Negative vectors | sdk/python/tests/test_canonical.py; test_hashchain.py; sdk/typescript/test/hashchain.test.ts | Python/TypeScript | partial | negative unit tests only; no versioned registry | scattered test intent only | SDK CI |
| Verifier CLI | none | n/a | missing | no | roadmap only | no |
| Proof bundle / auditor export | none | n/a | missing | no | README/ADR mentions only | no |
| Compliance mapping registry | README.md; sdk/python/README.md; docs/adr/0002-substrate-data-model-and-hash-chain-v0.md | Markdown | partial / claim-risk | no mapping tests | Art.12 field mapping only | markdown checks only |
| TSA / RFC 3161 anchoring | docs/adr/0003-tsa-rfc-3161-anchoring.md | Markdown | docs-only | no anchor tests | ADR accepted | no implementation gate |
| Sigstore / Rekor | README.md; .github/workflows/publish-typescript.yml; sign-release.yml | Actions/docs | partial | release provenance/signing workflow evidence only | README/CHANGELOG/SECURITY | publish/sign-release workflows |
| Storage / persistence | sdk/python/src/attestplane/substrate.py; sdk/typescript/src/substrate.ts | Python/TypeScript | partial | in-memory tests only | explicitly out of scope in SDK READMEs | SDK CI |
| Agent runtime adapters | none | n/a | missing | no | roadmap/product language only | no |
| Package publishing | publish-python.yml; publish-typescript.yml; pyproject.toml; package.json; CHANGELOG.md | Actions/TOML/JSON | implemented for alpha channels | workflow gates; local tests passed | README/CHANGELOG | publish workflows |
| Supply-chain hygiene | codeql.yml; osv-scanner.yml; sbom.yml; reproducible-build.yml; scorecard.yml; REUSE.toml | Actions/TOML | implemented / partial | HEAD workflows success | README/CHANGELOG/SECURITY | yes |

## 5. Product Positioning vs Current Implementation

| Area | Status | Evidence | Gap |
|---|---|---|---|
| A Core Attestation Substrate | partial | types.py; types.ts; ADR-0002 | Generic EventDraft, Art.12 reference fields, schema_version, timestamp, actor, subject_ref exist. Missing dedicated decision/policy/checkpoint schemas, tenant/project/run/session taxonomy beyond session_id, correlation/causation/idempotency fields, replay spec, and schema-evolution registry. |
| B Tamper-evident Chain | partial / alpha-implemented | hashchain.py; hashchain.ts; test_hashchain.py; hashchain.test.ts | SHA-256 hash chain, canonical hash equality, prev_hash/event_hash/seq tamper detection exist. Missing duplicate detection, explicit reorder/missing taxonomy, root/checkpoint, proof bundle, and durable append-only backend. |
| C Independent Verification | partial | verify_chain APIs; vectors.json | Library verification and golden vectors exist. Missing verifier CLI, auditor JSON API, external verifier spec, proof bundle, negative/malformed vector registry. |
| D Compliance Mapping | partial with claim-risk | sdk/python/README.md; README.md; ADR-0002 | Only narrow EU AI Act Art.12(2)(a) field mapping exists. EU AI Act Art.13-15, DORA Art.8, NIS2, GDPR accountability, ISO 42001, NIST AI RMF are missing structured obligation registry and tests. |
| E Anchoring / External Trust | docs-only | ADR-0003; README.md; CHANGELOG.md | ADR-0003 exists. No TSAProvider, AnchorRecord, TSA verification, trust roots, key lifecycle, revocation story, offline verification, Rekor substrate anchor, or anchor vectors. Implementation remains M5 blocker for temporal trust claims. |
| F Storage / Persistence | partial | substrate.py; substrate.ts; SDK READMEs | In-memory append-only container and fromEvents rehydration exist. File/SQLite/Postgres/S3, append-only durable log, retention, tenant isolation, encryption, migration, backup/recovery missing. |
| G Agent Runtime Integration | missing | no adapter files | No AIOS/generic/LangGraph/AgentScope/OpenAI/Claude/Codex/MCP adapters; no typed tool-call/policy-check/human-approval/lease/budget/supervisor event schemas. |
| H CLI / DX | missing / partial docs | README snippets; SDK READMEs | Quickstarts exist. No attestplane init/record/verify/export/inspect/map-framework/anchor/doctor, no JSONL IO, no examples directory. |
| I SDK Quality | implemented for alpha core; partial product surface | pyproject.toml; package.json; tests | Typed APIs, deterministic serialization, package metadata and tests exist. TS is ESM-only Node >=22; no CJS/browser claim. Python local audit verified 3.12; matrix is CI-dependent. Generated docs and richer error taxonomy missing. |
| J CI / Supply Chain | implemented / partial | .github/workflows; REUSE.toml; scripts/check-policy.sh | Strong baseline: pinned actions, CodeQL, OSV, SBOM, Scorecard, REUSE, DCO, publish workflows, npm provenance. Branch protection not provable from files; SLSA L3 incomplete; sdist reproducibility known gap. |
| K Legal / Claim Safety | partial with downgrade needed | README.md; pyproject.toml; package.json; GOVERNANCE.md; SECURITY.md; TRADEMARK.md | Alpha and legal-advice disclaimers exist. Risk remains around EU AI Act ready, broad framework coverage, technical guarantee, cryptographically anchored wording, certification language. |

## 6. Claim Safety Audit

| Claim | Status | Evidence | Safer wording |
|---|---|---|---|
| EU AI Act Article 12 ready | claim-risk | Only four Art.12(2)(a) reference fields exist; no obligation registry/verifier expectation. | designed toward EU AI Act Article 12 auditability; includes selected Art.12(2)(a) reference fields |
| Framework coverage table directly addresses EU AI Act Art.12-17, DORA, NIST, ISO, SOC2, CRA | unsupported | No evidence bundle schema or mapping registry; README says endpoint planned. | planned framework-mapping targets; current alpha only includes chain + selected Art.12 fields |
| Cryptographically anchored audit trails / framework-satisfying trails | claim-risk | Hash chain exists; RFC3161 anchoring is ADR-only. | tamper-evident hash-chain audit records today; external anchoring planned |
| Every tool call/model invocation/data access/decision is verifiable and mappable | partial | Generic EventDraft can encode; no typed taxonomy/adapters. | can encode generic audit records; typed runtime adapters planned |
| technical guarantee for framework mappings | unsupported | No framework mapping implementation. | technical design goal |
| tamper-evident SHA-256 hash chain | safe alpha claim | hashchain.py/hashchain.ts + tests. | Keep tamper-evident; avoid tamper-proof |
| Self-hosted first / data stays in control plane | safe for current SDK | No SaaS calls; in-memory SDK only. | Keep, but state durability is caller responsibility |

Immediate downgrade targets:

- `EU AI Act Article 12 ready` in SDK metadata, SDK READMEs, and package descriptions.
- README framework coverage table saying broad evidence bundles directly address EU AI Act Art.12-17, DORA, NIST, ISO, SOC2, CRA.
- README/GOVERNANCE wording implying externally anchored or framework-satisfying trails before RFC-3161 code ships.
- Certification/trademark language should stay future/controlled; no v0.0.1 certification program should be implied.

Safe claims: `tamper-evident SHA-256 hash chain`, Apache-2.0, DCO, REUSE, alpha disclaimers, and self-hosted/no-SaaS behavior for current SDK code.

## 7. Gap Detail Sections

### Compliance Mapping Gap

Real mapping exists only for a narrow EU AI Act Article 12(2)(a) field set: `session_id`, `reference_db_ref`, `matched_input_ref`, and `human_verifier`. No machine-readable obligation registry exists yet for EU AI Act Articles 13-15, DORA Article 8, NIS2, GDPR accountability, ISO 42001, or NIST AI RMF.

### Verification / Anchoring Gap

Library-level `verify_chain()` exists in both SDKs, but verifier CLI, proof bundle, external verifier spec, auditor JSON API, negative/malformed vector registry, and RFC3161/TSA anchoring implementation are missing. ADR-0003 is accepted design only.

### Agent Runtime Integration Gap

No AIOS, generic runtime, LangGraph, AgentScope, OpenAI Agents SDK, Claude Code, Codex CLI, or MCP adapter exists. Tool-call, policy-check, human-approval, lease, budget, supervisor, worker, retry, rollback, and control-plane events are not yet typed schemas.

### SDK / CLI Gap

The Python and TypeScript SDK cores are implemented and tested. The CLI, JSONL input/output, examples directory, generated API docs, proof bundle import/export, richer error taxonomy, and package-level verifier workflow are missing.

### OSS Governance / Supply Chain Gap

The repository has strong OSS hygiene: Apache-2.0, NOTICE, DCO, REUSE, CodeQL, OSV, SBOM, OSSF Scorecard, pinned actions, publish workflows, and npm provenance. Remaining gaps include branch-protection evidence outside repo files, incomplete SLSA L3, release-signature verification per release, and the known sdist reproducibility gap.

## 8. Missing Modules Matrix

| Module | Current status | Evidence path | Missing content | Risk | Recommended stage | Why important | Minimum deliverable |
|---|---|---|---|---|---|---|---|
| Verifier CLI | missing | README.md roadmap; no CLI files | No command surface for independent verification | P0 | Now / v0.0.1-alpha cleanup | Verification is the product core | attestplane verify JSONL/bundle with exit codes |
| Proof bundle format | missing | README mentions evidence_bundle; no schema | No portable evidence package | P0 | M5 / v0.1.0 | Auditors need SDK-independent package | JSON schema + import/export + golden bundle |
| Docs claim-safety cleanup | partial | README.md; SDK metadata; GOVERNANCE.md | Claims exceed implementation | P0 | Now / v0.0.1-alpha cleanup | Prevents compliance overclaim | Downgraded wording and rg gate |
| Negative conformance vectors | partial | negative unit tests only | No shared malformed vector registry | P1 | M5 / v0.1.0 | Third-party implementations need rejection contract | negative_vectors.json + Python/TS tests |
| Canonical JSON spec document | partial | ADR-0002; SDK READMEs | No standalone implementer spec | P1 | Now / v0.0.1-alpha cleanup | External verifiers need stable spec | docs/specs/canonical-json-v1.md |
| EU AI Act Art.12 obligation mapping | partial | sdk/python/README.md | No obligation ids/verifier expectations/status registry | P1 | M5 / v0.1.0 | Supports any Art.12 claim | obligations.json + docs + tests |
| DORA Art.8 mapping | claim-only | README.md table | No actual DORA mapping artifacts | P1 | M5 / v0.1.0 | DORA claims are high-risk | DORA rows with disclaimers and unsupported marks |
| Auditor export JSON schema | missing | README mentions Auditor JSON API | No schema/contract | P1 | M5 / v0.1.0 | Compliance review needs non-SDK contract | auditor-export-v1.schema.json |
| Generic agent runtime adapter interface | missing | no adapter files | No runtime embedding protocol | P1 | M5 / v0.1.0 | Core to agent substrate adoption | adapter protocol + no-op reference adapter |
| AIOS adapter spec | missing | no AIOS docs/integration files | Extraction boundary undocumented | P1 | M5 / v0.1.0 | Proves AIOS-derived evidence layer boundary | docs/integrations/aios.md |
| Tool-call/policy-check/human-approval events | partial / missing | EventDraft.event_type free string only | No typed schemas/constants | P1 | M5 / v0.1.0 | README names these event classes | typed helpers + conformance entries |
| ADR-0003 TSA implementation | docs-only | docs/adr/0003-tsa-rfc-3161-anchoring.md | No TSA client/verification/trust roots/anchor vectors | P1 | M5 / v0.1.0 | External temporal trust | TSAProvider + mock provider + AnchorRecord + tests |
| Examples / quickstart project | partial | README snippets only | No examples directory | P2 | M5 / v0.1.0 | Adoption and verification demo | examples/basic-jsonl + CI smoke |
| Package publishing verification report | partial | CHANGELOG hashes; workflows | No docs/validation release report | P2 | M5 / v0.1.0 | Auditable release evidence | release_verification md/json |
| Storage backend decision ADR | missing | README/SDK docs anticipate ADR-0004 | No storage path | P2 | M6 / hosted alpha | Durability and concurrency | ADR-0004 storage decision |
| Sigstore/Rekor substrate anchoring | missing | roadmap only | No event-chain transparency proof | P2 | M6 / hosted alpha | Public transparency beyond TSA | ADR-0005 + proof format |
| Retention/erasure policy | missing | ADR-0002 says out of scope | No AI Act retention vs GDPR erasure guidance | P3 | M7 / design partner | Enterprise legal deployment | docs/deployment/retention.md |
| Tenant isolation model | missing | no tenant identifiers | No multi-tenant boundary | P3 | M8 / enterprise | Enterprise/cloud readiness | ADR + schema strategy |

## 9. Four Product Routes

### Route 1 — Open-source Core Credibility
Must add verifier CLI, proof bundle, negative conformance vectors, standalone canonical JSON spec, better runnable examples, and docs claim downgrade.

### Route 2 — Compliance Product Credibility
Must add EU AI Act Article 12 mapping registry, DORA Article 8 mapping, legal disclaimer per obligation, auditor export format, framework mapping docs, and source citation placeholders.

### Route 3 — AIOS / Agent Runtime Integration
Must add AIOS adapter spec, generic runtime adapter, tool-call event, policy-check event, human-approval event, lease/budget/supervisor event mapping, and one integration example.

### Route 4 — External Trust Anchoring
ADR-0003 exists; M5 needs TSA client abstraction, timestamp token model and verification, anchoring proof format, trust-root lifecycle, key lifecycle, and a Sigstore/Rekor decision. Until code ships, say "designed for RFC-3161 anchoring" rather than "cryptographically anchored evidence chains".

## 10. Recommended M5 / v0.1 Roadmap

1. Claim-safety cleanup before the next public alpha push.
2. Verifier CLI with stable exit codes.
3. Proof bundle format and auditor export schema.
4. Negative conformance vector registry.
5. Standalone canonical JSON v1 spec.
6. EU AI Act Article 12 obligation registry.
7. DORA Article 8 obligation registry.
8. Generic agent runtime adapter interface and typed event taxonomy.
9. AIOS adapter spec and one runtime integration example.
10. TSA/RFC-3161 implementation checkpoint: mock provider + AnchorRecord + anchor vector tests.

## 11. Tickets

### AP-M5-001 — Add verifier CLI

Priority: P0
Rationale: Library-only verification is insufficient for independent auditors.
Files likely touched: sdk/python/src/attestplane; sdk/python/pyproject.toml; docs/cli.md
Acceptance Criteria: CLI verifies JSONL/bundle and returns stable exit codes.
Tests required: Valid/tampered/malformed CLI tests.
Docs required: CLI reference and README quickstart.
Security/legal considerations: Technical verification only, no legal compliance claim.
CLI command to verify: `cd sdk/python && attestplane verify tests/fixtures/valid.jsonl`

### AP-M5-002 — Add proof bundle format

Priority: P0
Rationale: Evidence must be portable beyond process memory.
Files likely touched: docs/schemas/proof-bundle-v1.schema.json; sdk/python/src/attestplane/bundle.py; sdk/typescript/src/bundle.ts
Acceptance Criteria: Bundle includes events, chain head, metadata, optional anchors, deterministic hash.
Tests required: Python/TS round trip and malformed tests.
Docs required: Proof bundle spec.
Security/legal considerations: Avoid raw PII by default.
CLI command to verify: `pytest tests/test_bundle.py && npm test`

### AP-M5-003 — Add negative conformance vectors

Priority: P1
Rationale: Implementers need shared rejection behavior.
Files likely touched: sdk/python/tests/conformance/negative_vectors.json; Python/TS tests
Acceptance Criteria: Shared malformed vectors replay in both SDKs.
Tests required: Python/TS replay tests.
Docs required: Vector versioning docs.
Security/legal considerations: Fail closed on malformed input.
CLI command to verify: `pytest tests/test_conformance_negative.py`

### AP-M5-004 — Add canonical JSON spec document

Priority: P1
Rationale: ADR prose is not an implementer spec.
Files likely touched: docs/specs/canonical-json-v1.md
Acceptance Criteria: Standalone spec with examples and rejection cases.
Tests required: Docs lint; optional generated examples.
Docs required: Spec linked from README/SDKs.
Security/legal considerations: Versioned, stable wording.
CLI command to verify: `bash scripts/check-policy.sh`

### AP-M5-005 — Add EU AI Act Article 12 obligation mapping

Priority: P1
Rationale: Current Art.12 wording needs structured support.
Files likely touched: docs/compliance/eu-ai-act-art12.md; docs/compliance/obligations.json
Acceptance Criteria: Rows include article, obligation_id, fields, event mapping, verifier expectation, status.
Tests required: Schema validation test.
Docs required: Mapping doc with disclaimer.
Security/legal considerations: No legal advice.
CLI command to verify: `python scripts/validate_obligations.py`

### AP-M5-006 — Add DORA Article 8 obligation mapping

Priority: P1
Rationale: DORA table is claim-only.
Files likely touched: docs/compliance/dora-art8.md; obligations.json
Acceptance Criteria: DORA rows use same registry; unsupported controls explicit.
Tests required: Registry validation.
Docs required: Mapping doc.
Security/legal considerations: Use designed-toward wording.
CLI command to verify: `python scripts/validate_obligations.py`

### AP-M5-007 — Add generic agent runtime adapter interface

Priority: P1
Rationale: Substrate needs a stable runtime embedding point.
Files likely touched: docs/integrations/agent-runtime-adapter.md; sdk/python/src/attestplane/adapters.py; sdk/typescript/src/adapters.ts
Acceptance Criteria: RuntimeEventAdapter maps runtime events to EventDraft.
Tests required: Dummy adapter tests.
Docs required: Adapter spec and example.
Security/legal considerations: Do not capture secrets/PII by default.
CLI command to verify: `pytest tests/test_adapters.py && npm test`

### AP-M5-008 — Add AIOS adapter spec

Priority: P1
Rationale: Extraction story needs concrete boundary evidence.
Files likely touched: docs/integrations/aios.md
Acceptance Criteria: Document AIOS sources, field mapping, out-of-scope fields, ownership boundary.
Tests required: Docs lint.
Docs required: AIOS integration guide.
Security/legal considerations: No AIOS production certification implication.
CLI command to verify: `bash scripts/check-policy.sh`

### AP-M5-009 — Add tool-call / policy-check / human-approval event types

Priority: P1
Rationale: README names these classes but code uses free-form strings.
Files likely touched: types.py; types.ts; vectors.json
Acceptance Criteria: Typed helpers/constants and vectors for each event class.
Tests required: Python/TS unit + conformance tests.
Docs required: Event taxonomy doc.
Security/legal considerations: Avoid secret payloads.
CLI command to verify: `pytest && npm test`

### AP-M5-010 — Add ADR-0003 TSA/RFC3161 anchoring implementation checkpoint

Priority: P1
Rationale: ADR exists but executable scope is missing.
Files likely touched: docs/adr/0003-tsa-rfc-3161-anchoring.md; docs/validation/tsa_m5_readiness.md
Acceptance Criteria: Clarify M5 deliverable: mock provider, AnchorRecord, anchor vectors, trust roots.
Tests required: Docs lint; future mock TSA tests.
Docs required: Readiness note.
Security/legal considerations: No anchored-chain claim until code.
CLI command to verify: `bash scripts/check-policy.sh`

### AP-M5-011 — Add docs claim-safety cleanup

Priority: P0
Rationale: Several claims exceed implementation.
Files likely touched: README.md; SDK metadata; SDK READMEs; GOVERNANCE.md
Acceptance Criteria: Risk phrases downgraded and roadmap-only claims labeled.
Tests required: rg phrase check.
Docs required: Claim-safety note.
Security/legal considerations: Avoid ready/compliant/certified/regulator-ready.
CLI command to verify: `rg -n "ready|compliant|certified|technical guarantee" README.md sdk docs GOVERNANCE.md`

### AP-M5-012 — Add examples/quickstart project

Priority: P2
Rationale: Snippets are not runnable project evidence.
Files likely touched: examples/basic-jsonl; examples/python-basic; examples/typescript-basic
Acceptance Criteria: Examples append/export/verify events.
Tests required: CI smoke.
Docs required: Examples README.
Security/legal considerations: Use pseudonymous data.
CLI command to verify: `cd examples/python-basic && python main.py`

### AP-M5-013 — Add package publishing verification report

Priority: P2
Rationale: Release evidence should be reproducible.
Files likely touched: docs/validation/release_verification_*.md/json
Acceptance Criteria: Report includes artifacts, hashes, workflow IDs, TestPyPI/npm/provenance.
Tests required: JSON shape validation.
Docs required: Release runbook.
Security/legal considerations: Only observed facts.
CLI command to verify: `python scripts/validate_release_report.py docs/validation/*.json`

### AP-M5-014 — Add storage backend decision ADR

Priority: P2
Rationale: M6 durability needs an agreed path.
Files likely touched: docs/adr/0004-storage-backend.md
Acceptance Criteria: Compare file/SQLite/Postgres/S3 and define append-only/replay invariants.
Tests required: ADR lint.
Docs required: Storage threat model.
Security/legal considerations: Cover tenant isolation and backups.
CLI command to verify: `bash scripts/check-policy.sh`

### AP-M5-015 — Add auditor export JSON schema

Priority: P1
Rationale: Auditors need a stable non-SDK contract.
Files likely touched: docs/schemas/auditor-export-v1.schema.json; docs/specs/auditor-export-v1.md
Acceptance Criteria: Schema covers events, verification result, mapping, optional anchors, disclaimers.
Tests required: Schema validation fixtures.
Docs required: Auditor export spec.
Security/legal considerations: No legal opinion language.
CLI command to verify: `python scripts/validate_schema.py docs/schemas/auditor-export-v1.schema.json`

## 12. Release Readiness

- v0.0.1-alpha: Conditional Go. Core SDK alpha is supported by implemented code, tests, conformance vectors, and successful main workflows. Must keep narrow alpha wording.
- TestPyPI / npm alpha: Continue allowed after claim cleanup. npm production registry with `alpha` tag is acceptable if package descriptions avoid compliance-ready wording.
- v0.1 / M5: No-Go until P0/P1 modules are completed or explicitly scoped down.
- Hosted alpha / enterprise: No-Go. Durable storage, tenant isolation, retention, trust roots, production TSA, external transparency, RBAC/SSO, SLA, and runbooks are missing.

## 13. Final Go / No-Go Recommendation

Continue internal and developer-facing v0.0.1-alpha: **Go with claim cleanup**. Continue TestPyPI/npm alpha: **Go with narrow alpha wording**. Public compliance marketing: **No-Go**. Beta/GA: **No-Go**. Enterprise/cloud readiness: **No-Go**.

Final status sentence: Attestplane is a tested Apache-2.0 alpha SDK substrate for tamper-evident in-memory agent audit chains, but not yet a complete independently verifiable compliance, anchoring, storage, adapter, or auditor product.
