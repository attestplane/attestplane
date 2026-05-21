# Maintainers

This file consolidates *who* is responsible for what on Attestplane: merge
authority, release-signing material, area expertise, succession status, and
how to reach a human when something is wrong.

It is intentionally *separate* from `CONTRIBUTORS.md` (which is a thank-you
roll, not a responsibility roster) and from `GOVERNANCE.md` (which defines
the *rules* — this file inventories the *people* operating under those
rules).

External reviewers and downstream operators may rely on this file to answer
the audit-grade question *"who holds the merge keys, release-signing
credentials, and sealed access?"* — a question the project has not yet
answered satisfactorily, because we are still operating with a single
maintainer (see §2).

This file is **descriptive**, not aspirational: it reflects the current
state, including gaps. It does **not** introduce any new external date
commitments — every milestone referenced below is reproduced from
`GOVERNANCE.md`, the canonical source.

---

## 1. Current Maintainers

| Handle | Role | Scope | Timezone |
|---|---|---|---|
| [@merchloubna70-dot](https://github.com/merchloubna70-dot) | Lead Maintainer | ALL (sole maintainer; see §2) | UTC+8 |

The single-maintainer state is the project's most significant governance
risk. It is mitigated — not eliminated — by the succession plan in §2 and
the per-area expertise map in §3. No further information about the
maintainer (real name, employer, entity affiliation, license credentials)
is recorded here; those disclosures live in `GOVERNANCE.md` §9 where they
are part of the formal conflict-of-interest framework.

---

## 2. Succession Plan

The named emergency successor designation is a required governance
deliverable tracked in `GOVERNANCE.md` §8.

As of the date this file is added, the §8.2 successor slot is **unfilled** —
the document carries a `[Successor TBD — to be designated by M6,
2026-09-01]` placeholder.

> **This is an open governance gap, not a resolved item.** Until that slot
> is filled with a named individual and a written acceptance letter (per
> `GOVERNANCE.md` §8.2), the project operates under the §8.3 *Emergency
> Continuity Protocol* only. Reviewers, downstream operators, and
> potential foundation partners evaluating bus-factor risk should treat
> the gap as the project's primary single-point-of-failure exposure.

When the successor is designated, this file will be updated in the same
PR that updates `GOVERNANCE.md` §8.2 — keeping both documents in lockstep
so there is no risk of one referencing a successor the other does not
know about.

This section creates no new date commitments. The `M6, 2026-09-01`
reference is a pointer back to the already-published milestone in
`GOVERNANCE.md` §8.2 and §8.5; nothing here re-targets, re-dates, or
extends that schedule.

---

## 3. Per-Area Expertise Map

| Area | Path(s) | Primary Owner | Nominations Open? |
|---|---|---|---|
| Python SDK | `sdk/python/` | Lead Maintainer (sole) | Yes — per `GOVERNANCE.md` §5.1 |
| TypeScript SDK | `sdk/typescript/` | Lead Maintainer (sole) | Yes — per `GOVERNANCE.md` §5.1 |
| ADR set | `docs/adr/` | Lead Maintainer (sole) | Yes — per `GOVERNANCE.md` §5.1 |
| Supply chain (signing, SBOM, SLSA) | `release/`, `.github/workflows/` | Lead Maintainer (sole) | Yes — per `GOVERNANCE.md` §5.1 |
| Documentation | `docs/`, top-level `*.md` | Lead Maintainer (sole) | Yes — per `GOVERNANCE.md` §5.1 |
| Governance | `GOVERNANCE.md`, `docs/governance/` | Lead Maintainer (sole) | Yes — per `GOVERNANCE.md` §5.1 |

"Nominations open" means the project is actively soliciting area
co-maintainers via the contributor track described in `GOVERNANCE.md`
§5.1. The fact that every row currently lists the Lead Maintainer is the
gap, not the goal.

---

## 4. Release-Signing Key Holder

Release-signing material for v1.0 GA and forward is described in
`SECURITY.md`, *GPG Key (planned for v1.0 GA)*. The fingerprint placeholder
in that file is the authoritative reference; this file does not duplicate
the key material.

**Pre-GA reality (current state, written for audit transparency):**

- No project GPG key is in circulation yet.
- No release-signing keys are held in escrow yet.
- Release artifacts during the pre-GA soak window are produced from the
  Lead Maintainer's private workstation, with provenance recorded via the
  pipelines tracked in `docs/release/` and the workflows under
  `.github/workflows/`.
- A formal key-holder rotation policy will be added to this section once
  the v1.0 GA key is published per `SECURITY.md`. That update is a
  governance-amendment-class change and follows the §6 update policy
  below.

This file does **not** claim that current release artifacts are signed by
a project key, nor that an escrow exists, nor that any third-party
attestation covers key custody. Where pre-GA artifacts carry signatures,
those signatures and their custody are described in the release notes
that ship with the artifact, not here.

---

## 5. Emergency Contact

For security incidents (vulnerabilities, suspected compromise, takeover
attempts) use the private channels in `SECURITY.md`:

- Email: `security@attestplane.com`
- GitHub Security Advisories: the *Report a vulnerability* button on the
  repository Security tab — the recommended pre-GA path while the GPG key
  is still pending publication per `SECURITY.md`.

For Code of Conduct incidents use `conduct@attestplane.com` per
`GOVERNANCE.md` §11.2.

Please do **not** open public GitHub Issues for security or conduct
reports.

---

## 6. Update Policy

This file is maintained in the `main` branch.

Any **substantive change** — adding or removing a maintainer, updating
scope, recording a successor designation, or changing the
release-signing-custody description in §4 — requires the
`GOVERNANCE.md` §4.1 lazy-consensus procedure: a `[DECISION]`-labeled PR
open for **72 hours** for any active Maintainer to object; absent
objection the change is adopted. A single `-1` with reasoning blocks
consensus and escalates per `GOVERNANCE.md` §4.2.

Adding or removing a maintainer follows the substantive procedure in
`GOVERNANCE.md` §5 (which is supermajority-class); this file is updated
in the same PR that records the §5 outcome.

Editorial corrections (typos, broken links, table-format reflows) may be
merged by any Maintainer without a vote, mirroring `GOVERNANCE.md` §13.
