# Attestplane Project Governance

**Version**: 1.0  
**Effective Date**: 2026-05-17  
**Applies to**: `github.com/attestplane/attestplane` (core substrate) and all repositories under the `attestplane` GitHub organization  
**Review Cycle**: Annually, or triggered by maintainer supermajority vote

---

## 1. Mission

Attestplane is an Open Trust Substrate for verifiable AI agent compliance — providing permanent, cryptographically-anchored audit trails that satisfy EU AI Act, NIST AI RMF, ISO 42001, and related regulatory frameworks. The project is committed to remaining **permanently open source under Apache 2.0**. No commercial arrangement will ever compromise this commitment. The substrate exists to advance public infrastructure for trustworthy AI governance; community adoption and regulator trust are assets that belong to no single entity.

---

## 2. Roles

### 2.1 User

Anyone who downloads, deploys, or uses the software. No formal obligations. Contributions of bug reports and documentation feedback are welcome via GitHub Issues.

### 2.2 Contributor

Anyone who submits a pull request, files a substantive issue, improves documentation, or participates in design discussions. All contributions require a **DCO (Developer Certificate of Origin) sign-off** (`Signed-off-by:` line in every commit). No CLA is required. By signing off, contributors certify that their contribution is original work or appropriately licensed, per the terms at <https://developercertificate.org>.

### 2.3 Maintainer

A trusted contributor granted merge access and decision-making authority. Maintainers are collectively responsible for project health, security, roadmap, and community standards. See §5 for how Maintainers are added and removed.

### 2.4 Lead Maintainer (Founder)

The current Lead Maintainer is the project founder: a China-licensed Business and Compliance lawyer and sole engineer, serving as the primary decision-maker, release authority, and security contact. The Lead Maintainer role carries no special veto beyond what is granted by supermajority mechanics — it is a designation of accountability, not a grant of unilateral authority. See §8 for continuity obligations.

### 2.5 Reviewer

A bridge role between Contributor (§2.2) and Maintainer (§2.3). A Reviewer is a Contributor who has earned triage authority and advisory review weight through sustained, substantive review participation, but who does **not** yet hold merge access or release authority.

- **Read access** — the repository is public, so this is already granted to everyone; the tier name simply marks formal recognition.
- **Triage authority** — apply and remove labels, close issues as duplicate or out-of-scope, link related issues and PRs, request reproduction details from issue authors. No power to close substantive issues without owner consensus.
- **Advisory `/lgtm`** — Reviewers may post `/lgtm` on a PR as a signal that the change looks correct from the perspective of the area in which they have been reviewing. The `/lgtm` is **advisory**, not binding; a Maintainer's `approve` is still required for merge.
- **No merge access** — the GitHub `write` or `maintain` permission is **not** granted by this tier; merge access remains a Maintainer-only privilege under §2.3.
- **No release authority** — Reviewers do not cut releases, sign artifacts, or hold any of the §8 succession responsibilities.
- **No voting rights in §4 RFCs** — Reviewer status confers no vote in §4.1 lazy consensus or §4.2 supermajority decisions. Reviewers may participate in RFC discussion; only Maintainers (§2.3, §2.4) vote.
- **Bridge requirement** — serving as a Reviewer for at least three months is a precondition for Maintainer nomination under the revised §5.1 path below.

Full Reviewer-tier specification, including the nomination procedure and revocation, is in [`docs/governance/reviewer-tier.md`](docs/governance/reviewer-tier.md).

---

## 3. Maintainer Responsibilities

Each Maintainer is expected to:

1. **Review pull requests** in a timely manner (target: first response within 7 days for non-trivial PRs).
2. **Enforce DCO sign-off** on every merged commit; do not merge contributions lacking `Signed-off-by`.
3. **Triage security reports** received at security@attestplane.com within 48 hours; coordinate coordinated disclosure per `SECURITY.md`.
4. **Participate in governance decisions** by voting within the required window (72 hours for lazy consensus items; 7 days for supermajority items).
5. **Disclose conflicts of interest** per §9 and recuse from votes where a personal or commercial interest exists.
6. **Maintain succession readiness**: ensure at least one other Maintainer has working knowledge of any area of the codebase for which they are the sole expert.

---

## 4. Decision-Making Process

### 4.1 Default: Lazy Consensus

Routine decisions (dependency upgrades, documentation changes, bug-fix releases, non-breaking feature additions) proceed by **lazy consensus**: any Maintainer may open a PR or GitHub Discussion labeled `[DECISION]`, and the change is adopted if no Maintainer objects within **72 hours**. A single `-1` with reasoning blocks consensus and escalates to a vote.

### 4.2 Supermajority Vote Required

The following decisions require an explicit vote with **≥ 2/3 of active Maintainers** approving, preceded by a **30-day public RFC** posted to GitHub Discussions:

| Category | Examples |
|---|---|
| License or re-license | Any change to the Apache 2.0 license term (see §6) |
| Governance amendment | Changes to this document |
| Security disclosure policy | Changes to `SECURITY.md` coordinated-disclosure process |
| Maintainer add or remove | See §5 |
| Repository transfer | Moving the repo to a new organization or foundation |
| Foundation migration | Initiating a hand-off to Linux Foundation, OpenSSF, or equivalent |

### 4.3 Voting Mechanics

- Votes are cast publicly in GitHub Discussions or a dedicated RFC issue.
- Each active Maintainer has one vote: `+1` (approve), `0` (abstain), or `-1` (block with stated reason).
- A Maintainer who has not voted within the 7-day voting window is counted as an abstention.
- The Lead Maintainer has no casting vote; ties that fail to reach ≥ 2/3 are resolved by re-opening the RFC for another 14-day discussion cycle before a re-vote.

---

## 5. Adding and Removing Maintainers

### 5.1 Adding a Maintainer

The advancement path is:

> **Contributor (≥ 1 merged PR + ≥ 3 months active) → Reviewer (§2.5: ≥ 3 substantive PR reviews + 1 Maintainer nomination + 72-hour lazy consensus) → Maintainer (≥ 3 months sustained Reviewer service + §4.2 supermajority).**

A Contributor may be nominated for Maintainer status if they meet all of the following:

1. **Six months of sustained, substantive contributions** — not volume of commits, but evidence of judgment: thoughtful reviews, architecture input, security awareness, or community stewardship.
2. **At least three months of service as a Reviewer** (§2.5). The Reviewer bridge tier exists specifically so that Maintainer candidates can demonstrate review judgment under public, lower-stakes conditions before merge access is granted.
3. **Nomination** by any existing Maintainer, with a written nomination posted publicly in GitHub Discussions.
4. **30-day RFC period** for community comment.
5. **Supermajority approval** (≥ 2/3 of active Maintainers).
6. **Public announcement** once approved, including the new Maintainer's disclosure per §9.

The Reviewer-service precondition (item 2) does **not** apply retroactively to anyone already serving as a Maintainer at the time §2.5 is adopted; existing Maintainers are grandfathered without further action.

### 5.2 Removing a Maintainer

A Maintainer may be removed by supermajority vote under the following circumstances:

- **Voluntary resignation**: honored immediately upon written notice.
- **Sustained inactivity** (no meaningful contribution or vote for 6+ consecutive months): the Maintainer is notified and given 14 days to re-engage before the supermajority vote proceeds.
- **Code of Conduct violation**: follows the enforcement process in §11; removal may be immediate in egregious cases.

### 5.3 Emeritus Status

Removed or resigned Maintainers may be listed as Emeritus with their consent. Emeritus maintainers have no voting rights but may participate in discussion.

---

## 6. License and Re-License Policy

### 6.1 Permanent Apache 2.0 Commitment

The core Attestplane substrate is licensed under **Apache 2.0 and will remain so permanently**. This is not merely a default — it is a binding governance commitment reflecting the v1.3 strategic decision to remove any source-available (BSL) fallback. The project depends on regulator and enterprise trust that can only be earned through irrevocable openness.

### 6.2 What Is Prohibited

The following actions are **explicitly prohibited** by this governance document without satisfying every condition in §6.3:

- Re-licensing the core substrate from Apache 2.0 to any other license (including AGPL, LGPL, EUPL, or any commercial license).
- Adding any dual-license scheme in which Apache 2.0 is paired with a non-OSI-approved license for certain use cases.
- Switching to a source-available or "eventually open" license model (e.g., Business Source License, Commons Clause, SSPL).

### 6.3 License Change Procedure (Intended to Be Effectively Permanent)

Should a future supermajority ever consider a license change, **all three** of the following conditions must be satisfied:

1. **Supermajority vote** (≥ 2/3 of active Maintainers) following a 30-day public RFC.
2. **Individual, explicit, affirmative written consent** from every contributor who has committed code that remains in the codebase at the time of the proposed change. Silence or non-response does not count as consent. This "contributor backfill" requirement is intentionally designed to make re-licensing practically infeasible — it is the permanent commitment mechanism.
3. **Trademark and brand continuity**: any license change must preserve the community's right to fork the last Apache 2.0 version under the name `attestplane-oss` or similar; the trademark holder (§7) must grant a royalty-free license to that fork.

### 6.4 Enterprise Layer

A separate, proprietary `attestplane-enterprise` repository (not yet launched) is not subject to this section. The open/closed boundary is maintained at the repository level; no proprietary code may be merged into the core substrate repository.

---

## 7. Trademark Holding and Brand Stewardship

### 7.1 Holding Entity

The **Attestplane** word mark (™ — USPTO and EUIPO registration to be filed; target W2–W3 2026), the `attestplane.com` domain, and associated logos are held by **Attestplane Pte. Ltd. (Singapore, in formation as of 2026-05-17)**. Trademark ownership is separate from the Apache 2.0 license. The license grants broad code rights; it does not grant rights to the Attestplane name or logo for non-project purposes.

Individual Maintainers do not hold and may not transfer project trademarks in their personal capacity.

### 7.2 Permitted Use

Community members may use the Attestplane name and logo to:

- Identify unmodified deployments of the software.
- Write documentation, blog posts, or talks about the project.
- Build integrations that are compatible with the substrate.

### 7.3 Prohibited Use

Without written permission from the trademark holder:

- Implying that a fork or derivative is the official Attestplane project.
- Using the Attestplane name or logo in a way that suggests endorsement.
- Registering domains, accounts, or products that incorporate the Attestplane trademark.

### 7.4 Foundation Migration and Trademark Transfer

If the project migrates to a foundation (§12), the trademark holding entity will execute a trademark assignment to the receiving foundation entity as part of the migration agreement. See §12 for the migration process.

For the full trademark policy, see `TRADEMARK.md`.

---

## 8. Succession Plan and Continuity Protocol

> **Context**: The xz utils compromise (2024) demonstrated that sole-maintainer projects are critical infrastructure risks. The v1.3 commercial strategy (§6 risk register) classifies "founder health / single point of failure" as probability: medium, impact: critical. This section is a hard governance requirement, not advisory.

### 8.1 Current State

As of the effective date of this document:

- **Sole Maintainer**: The project founder (China-licensed Business and Compliance lawyer; sole engineer).
- **Sole IP holder**: Attestplane Pte. Ltd. (Singapore entity). Even if the founder becomes unavailable, the Singapore company can appoint a new director and delegate maintainer authority — the project's trademarks, domains, and repository ownership are held at the entity level, not personally.

### 8.2 Designated Emergency Successor

A named emergency successor must be designated by **M6 (target: 2026-09-01)**:

> **[Successor TBD — to be designated by M6, 2026-09-01. This is a required governance deliverable. A real, named individual with a written acceptance letter must be recorded here before M6 ships. Until that date, the emergency protocol in §8.3 applies.]**

The designated successor should be a Contributor who has demonstrated sustained engagement with the codebase and understands the project's regulatory and security posture.

### 8.3 Emergency Continuity Protocol

If the Lead Maintainer is **unreachable for 14 or more consecutive calendar days** without prior notice:

1. Any Maintainer (or, if no other Maintainers exist, any Contributor with ≥ 3 merged PRs) may post a public `[CONTINUITY PROTOCOL TRIGGERED]` issue in the primary repository.
2. The designated successor (§8.2) is immediately activated as interim Lead Maintainer.
3. If no successor has been designated, the Attestplane Pte. Ltd. board of directors (or sole director) has authority to appoint an interim Maintainer.
4. Security keys, release signing credentials, and repository admin access must be recoverable via the sealed access document maintained at the Singapore company's registered address (updated quarterly).
5. The interim Lead Maintainer has full authority for 90 days; within that period, a permanent succession decision must be made via the Maintainer addition process in §5.1.

### 8.4 Permanent Incapacity

If the founder is permanently unable to continue (death, long-term incapacity, or voluntary withdrawal with no return):

1. **Preferred transition**: Donate the project to the **Linux Foundation**, **OpenSSF**, or **OpenJS Foundation** — whichever is most appropriate to the project's technical community at that time.
2. The Singapore entity will execute the trademark assignment and repository transfer to the receiving foundation.
3. If no foundation will accept the project, the Maintainer body (or the Singapore company board) may appoint a new Lead Maintainer and continue operations independently.
4. In no case will the project be transferred to an entity that would change the Apache 2.0 license without satisfying the conditions in §6.3.

### 8.5 Interim Milestones

| Date | Required Action |
|---|---|
| By M6 (2026-09-01) | Designate named emergency successor; record in this document |
| By M6 (2026-09-01) | Establish sealed access document at Singapore registered address |
| By M7 (2026-Q4) | Identify at least one additional Maintainer candidate from the contributor community |
| By M8 (2027-Q1) | Review succession plan as part of first FTE hire process |

---

## 9. Conflict of Interest and Disclosures

### 9.1 Disclosure Requirement

All Maintainers must publicly disclose, in their Maintainer profile or in this document's Appendix, their:

- Primary employer and role (if employed).
- Any commercial entity in which they hold equity or a leadership role that could have a direct interest in the project's direction.
- Any ongoing consulting or advisory relationship with an entity that deploys or competes with Attestplane.

Disclosures must be updated within 14 days of a material change.

### 9.2 Current Disclosures

**Lead Maintainer / Founder**: China-licensed Business and Compliance lawyer (active practice, all-in transition to full-time Attestplane founder); Founder and Director of Attestplane Pte. Ltd. (Singapore, in formation). No other employer. No competing commercial interests disclosed.

Additional Maintainer disclosures will be recorded here as Maintainers are added.

### 9.3 Recusal

A Maintainer with a direct financial or competitive interest in a decision must recuse from the formal vote on that decision. Recusal does not prevent participation in discussion. Recusal must be declared publicly in the decision thread.

---

## 10. Service Boundaries

### 10.1 Technical Compliance Mapping, Not Legal Advice

Attestplane provides **technical compliance mapping** — cryptographic audit infrastructure and regulatory framework alignment implemented as code and configuration. Nothing in this project's outputs, documentation, or tooling constitutes **legal advice or a legal opinion** in any jurisdiction.

The project founder's background as a China-licensed Business and Compliance lawyer is disclosed as professional context (§9.2). That background informed the precision of the framework mappings. It does not make the project's output a legal opinion, and it does not give the project authority to practice law in any jurisdiction outside China, or to provide legal opinions in any capacity through this project.

### 10.2 User Responsibility

Deploying organizations are solely responsible for:

- Obtaining qualified legal opinions from attorneys licensed in their jurisdiction before relying on any regulatory interpretation embedded in the software.
- Determining whether their specific deployment satisfies applicable law (EU AI Act, DORA, NIS2, GDPR, or other frameworks).
- Maintaining their own compliance records independent of Attestplane attestations.

### 10.3 Service Boundaries Notice

All official Attestplane consulting engagements and commercial contracts must incorporate the Service Boundaries Notice defined in the commercial strategy §11.3:

> *This engagement provides technical compliance analysis based on Attestplane's framework mapping. It does not constitute legal opinion or legal advice in any jurisdiction. Customer is solely responsible for obtaining legal opinions from qualified attorneys in their jurisdiction before relying on any regulatory interpretation. Attestplane Pte. Ltd. is a Singapore-incorporated technology company. Its founder's China-licensed lawyer credentials are disclosed as professional background; this engagement is technical consulting provided by Attestplane Pte. Ltd., not legal services by the founder in any personal capacity.*

---

## 11. Code of Conduct Enforcement

### 11.1 Standards

The project adopts the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct). Community spaces include the GitHub repository, issue tracker, Discord/Discourse, and any official mailing lists.

### 11.2 Reporting

Incidents should be reported to **conduct@attestplane.com** (a dedicated inbox, not monitored by a single individual). Reports are kept confidential.

### 11.3 Enforcement Process

1. Reports are reviewed by Maintainers not named in the report.
2. If a named Maintainer is the subject of the report, that Maintainer is recused from the entire process.
3. If **the Lead Maintainer** is the subject of the report, enforcement is delegated entirely to an **external arbiter** — the Linux Foundation conduct committee or the OpenSSF Technical Advisory Council, as applicable.
4. Outcomes range from a private warning to permanent ban from community spaces, depending on severity and prior history.
5. Decisions may be appealed once to the full Maintainer body (or external arbiter if §11.3.3 applies) within 14 days.

---

## 12. Foundation Migration Path

### 12.1 Rationale

Avoiding permanent founder lock-in is an explicit design goal of this governance document (see §8). If the project reaches sufficient adoption and organizational capacity, migration to an established open-source foundation reduces governance risk and increases institutional trust.

### 12.2 Target Foundations (Priority Order)

1. **Linux Foundation** — preferred for security-infrastructure projects; broadest enterprise credibility.
2. **OpenSSF** (Open Source Security Foundation) — preferred if the project's identity remains primarily security and compliance infrastructure.
3. **OpenJS Foundation** — if the project's center of gravity shifts to JavaScript-ecosystem integrations.

### 12.3 Migration Criteria

A foundation migration proposal may be raised when **all** of the following are true:

- The project has ≥ 1,000 GitHub stars and ≥ 50 active deployments documented.
- There are ≥ 3 active Maintainers with sustained contributions over ≥ 6 months each.
- At least one Maintainer is not affiliated with Attestplane Pte. Ltd.
- The Maintainer body has voted (supermajority) to initiate migration discussions.

### 12.4 Migration Process

1. A 30-day public RFC is opened to inform the community.
2. The Maintainer body selects a target foundation and opens formal discussions with that foundation.
3. Migration agreement must include: trademark assignment (§7.4), repository transfer, and a commitment by the receiving foundation to preserve the Apache 2.0 license requirement (§6).
4. A second supermajority vote ratifies the final migration agreement.
5. Attestplane Pte. Ltd. retains no special governance rights after migration, but may remain a member or sponsor of the receiving foundation.

---

## 13. Amendments to This Document

Changes to this governance document require:

1. A **14-day public RFC** posted to GitHub Discussions, clearly labeled `[GOVERNANCE AMENDMENT RFC]`.
2. A **supermajority vote** (≥ 2/3 of active Maintainers) following the RFC period.
3. The amended document is committed to the repository with a merge commit that references the RFC issue number.

Minor editorial corrections (typos, broken links, formatting) may be merged by any Maintainer without a vote, provided no substantive content is changed.

---

## Appendix A: Current Maintainers

| Name | Role | Affiliation Disclosure | Added |
|---|---|---|---|
| [Founder — name TBD for public record] | Lead Maintainer | China-licensed Business + Compliance lawyer; Founder & Director, Attestplane Pte. Ltd. (Singapore) | 2026-05-17 |

*Additional Maintainers will be listed here as added per §5.*

---

## Appendix B: Document History

| Version | Date | Summary |
|---|---|---|
| 1.0 | 2026-05-17 | Initial governance document. Permanent Apache 2.0 commitment; DCO; succession plan (xz lesson); Singapore entity trademark holding; service boundaries. |

---

*This document is maintained in the project repository. Raise questions or concerns via GitHub Issues labeled `governance`.*
