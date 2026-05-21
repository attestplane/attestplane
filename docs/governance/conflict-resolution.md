# PR-Level Conflict Resolution

**Status**: Adopted (sub-ADR-class scope; lightweight; not an ADR)
**Applies to**: `github.com/attestplane/attestplane` and other repositories
under the `attestplane` GitHub organization
**Supersedes**: nothing (fills a gap in `GOVERNANCE.md` §4)

---

## 1. Why This Document Exists

`GOVERNANCE.md` §4.3 specifies what happens when a *supermajority vote*
ties: the RFC is re-opened for 14 days, then a re-vote is held. That is the
correct mechanism for project-wide policy disputes.

`GOVERNANCE.md` is **silent**, however, on a far more common case:
**two reviewers disagree on a single pull request**, not on policy.
Without an explicit procedure, such disagreements stall PRs, push
maintainers toward unilateral action, and slowly erode contributor trust —
the same dynamic that has hurt other small open-source projects.

This document fills that gap. It is intentionally **sub-ADR-class** in
scope (it does not change architecture, license, security policy, or any
other §4.2-class subject) and therefore does not require a §13 governance
amendment. It is published as a procedural reference for maintainers and
contributors.

---

## 2. Scope

This procedure applies when, and only when, **all** of the following are
true:

- The dispute is on a **single pull request**.
- The disagreement is **substantive** — i.e. about correctness, security
  impact, audit-chain semantics, API stability, or scope creep. It is
  **not** about stylistic preference (formatting, naming taste, comment
  density). Stylistic disagreements default to the existing reviewer's
  preference if the PR author requests it, with the understanding that
  the reviewer may still request follow-up.
- The disagreeing parties are **two reviewers** (Maintainers and/or
  Reviewers carrying advisory `/lgtm` weight; see future Reviewer-tier
  documentation if added). A single reviewer holding a `-1` is not yet a
  dispute — the author or another maintainer can ask for the reasoning
  and the standard PR review flow applies.

For anything outside this scope — broader policy disputes, license
questions, security-disclosure changes — use `GOVERNANCE.md` §4.3
(re-open the RFC for 14 days and re-vote).

---

## 3. Trigger

The procedure is triggered when, on a single PR:

1. Two reviewers have posted **opposing** substantive positions
   (`approve` vs `request changes`, or `-1` from one and `+1` from
   another), **and**
2. At least one of them has stated, in writing on the PR, that they
   consider the issue substantive and not resolvable by further
   discussion between just the two of them.

Either reviewer or the PR author may declare the trigger met by adding
the comment **`[CONFLICT-RESOLUTION TRIGGERED]`** to the PR. That comment
starts the clock for Step 1.

---

## 4. Steps

### Step 1 — Third reviewer (24 hours)

The PR author requests a **third reviewer** by `@`-mentioning a
maintainer or reviewer who has not yet engaged with the PR. The third
reviewer reads the prior discussion and posts an opinion within
**24 hours** of being mentioned.

Three outcomes are possible:

- **Two of three converge.** The third reviewer's opinion aligns with one
  of the original two. The minority reviewer is invited to either accept
  the outcome or escalate to Step 2 with explicit written reasoning. If
  they accept, the PR proceeds on the converged outcome and the
  resolution stops here.
- **Third reviewer proposes a synthesis.** The third reviewer suggests a
  middle path (e.g., a narrower change, an explicit follow-up issue, an
  added test). If both original reviewers accept the synthesis, the PR
  proceeds with the agreed modification. The resolution stops here.
- **No convergence and no synthesis.** All three reviewers remain in
  disagreement, or the third reviewer's opinion does not move either
  original reviewer. Escalate to Step 2.

If no third reviewer can be identified within 24 hours (e.g., because the
project has very few active maintainers), the author skips directly to
Step 2 and documents the skip in the PR thread.

### Step 2 — `[DECISION]` lazy-consensus thread (72 hours)

The PR author (or any participating reviewer) opens a `[DECISION]`-labeled
GitHub Discussion **or** PR-thread top-level comment, per `GOVERNANCE.md`
§4.1 lazy-consensus mechanics. The thread must:

- Link the PR.
- Summarize the disputed point in **one paragraph**, neutrally, naming
  both positions without advocacy.
- Propose a specific resolution (merge as-is, merge with a named
  modification, close, hold).

The thread is open for **72 hours**. Any active Maintainer may `-1` with
reasoning; absent any `-1`, the proposed resolution is adopted by lazy
consensus and the PR proceeds accordingly.

This step is intentionally aligned with `GOVERNANCE.md` §4.1 mechanics so
that no new voting machinery is invented for this lightweight procedure.

### Step 3 — `GOVERNANCE.md` §4.2 supermajority vote

If the Step 2 thread receives a substantive `-1` from any active
Maintainer, the dispute is no longer a routine PR-level disagreement: by
definition, a Maintainer has judged that the issue carries weight beyond
this single PR.

At that point the procedure terminates and the matter is escalated to a
`GOVERNANCE.md` §4.2 supermajority vote, preceded by the §4.2-required
30-day public RFC. The PR is **held**, not merged, until the vote
concludes.

---

## 5. Outcomes

The procedure can end in any of the following ways:

- **Convergence at Step 1 (third reviewer).** PR proceeds; the resolution
  is recorded only in the PR thread.
- **Synthesis at Step 1.** PR proceeds with the agreed modification; the
  synthesis is recorded in the PR thread.
- **Lazy consensus at Step 2.** PR proceeds per the proposed resolution.
  The `[DECISION]` thread serves as the durable record.
- **Escalation to Step 3.** PR is held pending §4.2 vote. The §4.2 RFC
  becomes the durable record; the outcome of the vote determines the PR
  outcome.

In all cases, the PR description should be updated to link the resolution
trail (Step 1 comment → Step 2 thread → §4.2 RFC, as applicable) so that
future contributors can trace the history.

---

## 6. What This Procedure Is Not

- It is **not** an authority shortcut. A Maintainer who feels strongly
  about a substantive PR-level issue can still escalate to §4.2 directly
  without working through Steps 1–2; this procedure offers a
  lighter-weight default for cases where escalation would be
  disproportionate.
- It is **not** a mechanism for changing project policy. The §4.2
  supermajority path remains the only way to change anything in the
  §4.2 list (license, governance, security-disclosure policy, maintainer
  add or remove, repository transfer, foundation migration).
- It is **not** an ADR. Architecture decisions still go through the ADR
  process described in `CONTRIBUTING.md` §5 and the `docs/adr/` directory.
- It does **not** introduce voting rights for non-Maintainers. The third
  reviewer in Step 1 may be a Maintainer or any other reviewer carrying
  advisory weight; only Maintainers can cast the binding `-1` in Step 2
  and only Maintainers vote in Step 3.

---

## 7. Update Policy

This document is editorial-procedural. Changes to it follow
`GOVERNANCE.md` §4.1 lazy consensus (72 hours, `[DECISION]`-labeled
thread). If a proposed change would make this procedure binding on
§4.2-class decisions, that change is itself a §4.2-class change and
follows the §13 amendment process.
