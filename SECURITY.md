# Security Policy

**Project:** Attestplane — Open Trust Substrate for AI Agents  
**Maintainer entity:** Attestplane Pte. Ltd. (Singapore, in formation as of 2026-05-17)  
**Contact:** security@attestplane.com  
**GPG key:** To be published at `https://attestplane.com/.well-known/security.txt` no later than M5 W6 (2026-08-15 target).

---

## Supported Versions

| Version range | Status | Notes |
|---------------|--------|-------|
| 0.x (alpha) | Best-effort | Pre-GA alpha. No production SLA. Security fixes applied on reasonable effort basis. |
| 1.0 GA | Full SLA | Target release 2026-08-15. Response timelines below apply from this version forward. |
| < 0.x (pre-alpha snapshots) | Unsupported | No fixes. Upgrade to current 0.x. |

Deployments running 0.x alpha are not recommended for production workloads. Operators who choose to deploy 0.x in production do so at their own risk.

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for a security report.** Public disclosure before a fix is available puts all users at risk.

| Channel | Details |
|---------|---------|
| Email | `security@attestplane.com` |
| GPG | Public key TBD; will be published at `https://attestplane.com/.well-known/security.txt` by M5 W6 |
| GitHub Security Advisories | Use the "Report a vulnerability" button in the Security tab (private disclosure) |

Please include in your report:

- A clear description of the vulnerability and affected component.
- Steps to reproduce or a minimal proof-of-concept.
- Your assessment of severity (Critical / High / Medium / Low) and exploitability.
- Whether you intend to publish; we will coordinate timing with you.

---

## Response Timeline

| Milestone | Target |
|-----------|--------|
| Acknowledgement of receipt | Within 7 days |
| Initial triage and severity assessment | Within 14 days |
| Fix or accepted mitigation — Critical | Within 30 days |
| Fix or accepted mitigation — High | Within 60 days |
| Fix or accepted mitigation — Medium / Low | Within 90 days |

If a fix requires coordinating with an upstream dependency, timelines may be extended. We will communicate any extension in the disclosure thread within the original window.

---

## Coordinated Disclosure

We follow a **90-day embargo** by default, measured from the date of initial report acknowledgement. At the end of the embargo period (or when a fix ships, whichever comes first), reporters are free to publish their findings.

- Researchers will be credited by name or handle in the release notes unless anonymity is explicitly requested.
- We will share a draft of any security advisory with the reporter before publication.
- If a critical vulnerability requires a shorter embargo, we will negotiate in good faith.

---

## Scope

### In Scope

| Component | Description |
|-----------|-------------|
| Hash chain engine | Substrate canonicalization and SHA-256 hash chain integrity (per [ADR-0002](docs/adr/0002-substrate-data-model-and-hash-chain-v0.md)); cross-language byte conformance |
| RFC-3161 anchoring | Time-stamp authority anchoring per [ADR-0003](docs/adr/0003-tsa-rfc-3161-anchoring.md) (ships v0.1 / M5) |
| Audit log API | JSON Auditor API — query, append, and verify endpoints (M5 surface) |
| SDK helpers | FastAPI / Express / NestJS / Django framework integration helpers (M5 surface) |
| Framework mapping layer | EU AI Act / NIST AI RMF / ISO 42001 / SOC 2 assertion mappings |
| Attestplane Cloud (M6+) | Hosted preview and production cloud service, once launched |
| CLI and build tooling | `attestplane` CLI, build pipeline scripts |

### Out of Scope

| Area | Guidance |
|------|----------|
| Upstream LLM model alignment | Attestplane constrains agent behaviour at the protocol layer; model-level jailbreaks are outside our control. |
| Third-party dependencies | Report vulnerabilities in PostgreSQL, FastAPI, Python, Rust crates, etc. to the respective upstream maintainer. |
| Customer self-host misconfiguration | Errors in operator-controlled infrastructure (firewall rules, secret management, etc.) are the operator's responsibility. See Hardening Guidance below. |
| Physical infrastructure and OS kernel | Report to your hosting provider or OS vendor. |

---

## Threat Categories

The following threat categories are specific to Attestplane's trust substrate model. This list supersedes any prior AIOS-era threat taxonomy.

| ID | Threat | Severity | Status |
|----|--------|----------|--------|
| AT-01 | **Audit chain tampering** — an attacker modifies or deletes historical audit records to erase evidence of agent misbehaviour. | Critical | Hash-chain integrity check in 0.x; RFC-3161 anchoring adds external timestamp proof. |
| AT-02 | **Replay attack** — a valid signed audit event or attestation is replayed out of sequence to fabricate a misleading audit trail. | High | Sequence numbers and timestamps enforced in chain; nonce policy planned M5. |
| AT-03 | **Lease / attestation forgery** — an agent or third party fabricates a framework-mapping attestation (e.g., falsely claiming EU AI Act Article 13 compliance). | Critical | Attestation signatures validated at ingestion; SLSA L3 provenance planned M5. |
| AT-04 | **Aggregation poisoning** (M7 differential privacy) — manipulated client-side inputs corrupt the aggregated privacy-preserving report submitted to regulators. | High | Planned mitigation in M7 C1 client-side DP architecture; input validation bounds. |
| AT-05 | **Supply-chain compromise** — a malicious or compromised dependency introduces a backdoor into the substrate binary or SDK. | Critical | Sigstore signing + SLSA L3 attestation + 48-hour dependency cooldown policy (see §Supply-Chain Security Posture). |
| AT-06 | **Trademark / domain phishing** — adversarial packages, domains, or repositories impersonate `attestplane` to distribute malicious tooling. | Medium | Report to security@attestplane.com; verify releases via Sigstore bundle at the official repository. |
| AT-07 | **Unauthorised auditor API access** — unauthenticated or under-privileged caller reads, writes, or purges audit events. | High | Authentication required on all Auditor API endpoints; append-only database grants enforced (see Hardening Guidance). |
| AT-08 | **Public claim drift** — README, release notes, or marketing copy claim capabilities (e.g., "EU AI Act compliant", "tamper-proof", "production-ready") that the substrate cannot substantiate, exposing the project and its founder to misleading-commercial-speech liability or future enforcement leverage. | High | All public claims governed by [`docs/policy/forbidden_claims.md`](docs/policy/forbidden_claims.md) and [`docs/policy/claims_policy.md`](docs/policy/claims_policy.md); CI policy-invariant job scans diffs; PR template asserts compliance. |

Full attack vectors and detection signals will be documented in `docs/architecture/THREAT_MODEL.md` (target M5 W7).

---

## Hardening Guidance for Operators

The following steps apply to self-hosted deployments. They are minimum-baseline expectations; production operators should apply additional controls appropriate to their risk profile.

1. **Replace default credentials before network exposure.** Default database credentials shipped for local development must be rotated before any networked deployment. Store secrets in a secrets manager (Vault, AWS Secrets Manager, or equivalent); never in environment files checked into version control.

2. **Enforce append-only grants on the audit log table.** The `audit_events` table must grant `INSERT` only — no `UPDATE` or `DELETE`. Verify the grant with:

   ```sql
   SELECT grantee, privilege_type
   FROM information_schema.role_table_grants
   WHERE table_name = 'audit_events';
   ```

   Any `UPDATE` or `DELETE` privilege on this table indicates a misconfiguration.

3. **Do not expose the substrate API directly to the public internet.** Place the Attestplane API behind a private network boundary, reverse proxy with authentication, or API gateway. No publicly routable endpoint without authentication is supported.

4. **Enable TLS for all transport.** All communication between agents, the audit API, and the RFC-3161 TSA endpoint must be encrypted in transit. Disable plain-HTTP fallback in production configuration.

5. **Pin and verify dependency checksums.** Use lockfiles (`poetry.lock`, `Cargo.lock`) and verify them against published hashes. Do not use floating version constraints in production.

6. **Run dependency vulnerability audits on a scheduled basis.**

   ```bash
   # Rust
   cargo audit
   # Python
   pip-audit
   ```

   Integrate these into CI and treat High/Critical advisories as blocking.

7. **Validate Sigstore release signatures before deploying new versions.** From M5 W4 onwards, all releases will carry a Sigstore bundle. Verify with `cosign verify` before deploying any new release into production.

---

## Supply-Chain Security Posture

The following supply-chain controls are planned or active. Status is as of 2026-05-17 (pre-M5 alpha).

| Control | Target | Status |
|---------|--------|--------|
| Sigstore / cosign release signing | M5 W4 | Planned |
| CycloneDX SBOM generation (per release) | M5 W4 | Planned |
| SLSA Build Level 3 attestation | M5 W4 | Planned |
| 48-hour dependency cooldown policy | M5 W4 | Planned — new dependencies must be proposed 48 hours before merge to allow supply-chain review |
| Dependabot version and security alerts | Active | Enabled on repository |
| Pinned lockfiles in CI | Active | `Cargo.lock` and `poetry.lock` committed and checked in CI |
| Branch protection + required reviews | Active | Main branch requires PR + review before merge |

The 48-hour dependency cooldown policy is a hard requirement derived from the v1.3 risk register (§6, supply-chain attack mitigation). Any PR introducing a net-new dependency must be open for at least 48 hours before merge to allow maintainer and community review.

SBOM artifacts will be published alongside each tagged release and signed with the project's Sigstore identity. Operators running regulated EU deployments should retain SBOM records per their internal CRA / NIS2 documentation requirements.

---

## EU Cyber Resilience Act (CRA) 2027-12 Compliance Preparation

The EU Cyber Resilience Act enters application on **2027-12-11**. Attestplane is an open-source project with a commercial entity maintainer (Attestplane Pte. Ltd.). The CRA obligations applicable to open-source stewards versus commercial manufacturers are under active legal monitoring.

| Checkpoint | Target date | Action |
|------------|-------------|--------|
| Legal posture review (OSS steward vs. commercial manufacturer classification) | 2027-Q1 | Founder (China-licensed compliance lawyer) conducts self-review of CRA recitals and implementing acts |
| SBOM auto-generation pipeline operational | M5 W4 (2026) | CycloneDX SBOM generated per release |
| ENISA reporting pipeline preparation | 2027-Q3 | Evaluate ENISA reporting tooling; draft internal incident-to-report SOP |
| Vulnerability disclosure documentation aligned to CRA Article 14 | 2027-Q3 | Review this SECURITY.md against final CRA implementing acts |
| CRA compliance ready | Before 2027-12-11 | Full review and any required adjustments complete |

Operators deploying Attestplane in EU-regulated environments (DORA, NIS2, EU AI Act Article 12–17) should monitor the CRA implementing acts independently and assess their own obligations as product manufacturers or importers.

---

## Hall of Fame / Bug Bounty

There is no formal monetary bug bounty program at this stage (pre-M5 alpha). Researchers who report valid, in-scope vulnerabilities will be:

- Credited by name or handle in the release notes for the fix (opt-out available — state preference in your report).
- Acknowledged in the project's security hall of fame in `SECURITY_HALL_OF_FAME.md` once that file is established at M5.

A structured bounty program with defined scopes, reward tiers, and safe-harbour terms is planned for **M9+ (2027-Q2)**. Scope and reward tiers will be published at that time.

---

## Residual Risk Acknowledgement

Attestplane explicitly acknowledges the following residual risks that cannot be fully mitigated within the project boundary:

- **Upstream LLM alignment failures.** Model-level jailbreaks and emergent agent behaviours are outside Attestplane's control. The audit chain records what agents did; it cannot prevent all classes of model-level misbehaviour.
- **Insider threat with database superuser access.** Technical controls (append-only grants, hash chain, RFC-3161 anchoring) reduce but do not eliminate risk from a privileged database administrator. Organisational controls — least-privilege access, four-eyes approval for schema changes, and audit log export to an independent store — are required complementary mitigations.
- **PostgreSQL zero-day vulnerabilities.** Attestplane depends on PostgreSQL for audit log persistence. Unpatched PG zero-days are outside the project's control; operators should use managed PostgreSQL services with automated patching in production.
- **Customer self-host misconfiguration.** Operators who deploy Attestplane outside the documented hardening baseline assume responsibility for misconfigurations in their own infrastructure. This includes network exposure, credential management, and TLS configuration.

---

*This document was last reviewed: 2026-05-17. Next scheduled review: 2027-Q1 (CRA legal posture checkpoint).*
