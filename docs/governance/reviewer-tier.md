# Reviewer Tier

**Status**: Adopted as part of the `GOVERNANCE.md` §2.5 amendment
**Companion to**: `GOVERNANCE.md` §2.5 and §5.1

---

## 1. Purpose

The Reviewer tier is a **bridge role** between Contributor (`GOVERNANCE.md`
§2.2) and Maintainer (`GOVERNANCE.md` §2.3). Before this tier existed, the
advancement path jumped directly from Contributor to Maintainer at six
months — too large a step for either side: a Maintainer nomination
required handing over merge keys to someone the existing maintainer body
had no structured way to observe in a review capacity.

The Reviewer tier fixes that gap with a smaller, revocable, observable
step. It also gives the project a public way to recognize sustained review
contributions without committing to grant merge access.

This document is the **specification** for the Reviewer tier. It does not
override `GOVERNANCE.md`; where the two appear to differ, `GOVERNANCE.md`
controls.

---

## 2. What a Reviewer Can Do

A Reviewer holds the following authority:

| Capability | Scope |
|---|---|
| Read access | Already public (repo is public); the tier simply marks formal recognition. |
| Triage | Apply and remove labels, close issues as duplicate or out-of-scope, link related issues and PRs, request reproduction details. |
| Advisory `/lgtm` | Post `/lgtm` on a PR to indicate "this looks correct to me." The signal carries weight in Maintainer review but does not by itself authorize merge. |
| Participate in discussion | Comment on RFCs, design discussions, ADR proposals, and PRs. |

## 3. What a Reviewer Cannot Do

The boundary is precise and intentionally narrow:

| Capability | Why it stays Maintainer-only |
|---|---|
| Merge PRs | Merge is the moment Apache 2.0 attribution and DCO sign-off become irrevocable; only Maintainers carry that authority under `GOVERNANCE.md` §2.3. |
| Cut or sign releases | Release authority is a §2.4 / §8 responsibility, tied to the succession plan; it does not flow with the Reviewer tier. |
| Manage release-signing material | Key custody belongs to Maintainers and is described in `SECURITY.md` and `MAINTAINERS.md` §4. |
| Vote in §4 RFCs | Neither lazy consensus (`GOVERNANCE.md` §4.1) nor supermajority votes (§4.2) count Reviewer voices. Reviewers may participate in discussion; only Maintainers vote. |
| Add or remove Maintainers | This is a §4.2 supermajority decision; Reviewer tier has no role. |
| Set or change project policy | License, security policy, governance amendments, and §4.2-class subjects are Maintainer-only. |

A Reviewer who finds the tier insufficient for what they want to do
should pursue Maintainer nomination via `GOVERNANCE.md` §5.1 — that is
exactly what the tier is designed to lead into.

---

## 4. Becoming a Reviewer

A Contributor becomes a Reviewer when **all** of the following are
satisfied:

1. **Sustained review activity for at least three months.** Three months
   is the minimum; longer service strengthens the nomination but is not
   required. Activity is measured by review participation, not commit
   count.
2. **At least five substantive PR reviews.** "Substantive" means the
   review identified a real correctness, security, audit-chain, API
   stability, or scope issue, or contributed a clear improvement
   suggestion that the PR author acted on. Boilerplate `LGTM` comments
   do not count.
3. **One Maintainer nomination.** Any active Maintainer may nominate a
   Contributor for Reviewer status by opening a GitHub Discussion or
   issue (label `[REVIEWER-NOMINATION]`) naming the candidate, linking
   five or more reviews that satisfy item 2, and stating that the
   Maintainer would trust the candidate's judgment in the areas
   reviewed.
4. **Lazy-consensus approval (72 hours).** Reviewer nomination uses the
   `GOVERNANCE.md` §4.1 lazy-consensus procedure: 72 hours from the time
   the nomination is opened, any active Maintainer may `-1` with
   reasoning; absent a `-1`, the nomination is adopted. This is
   intentionally lighter than the §5.1 supermajority procedure required
   for Maintainer addition — the Reviewer tier does not grant merge
   access, so a lighter procedure is proportionate.
5. **Self-acceptance.** The nominated Contributor confirms, on the
   nomination thread, that they accept the role. Reviewer status is not
   imposed without consent.

The candidate's name and handle are added to `MAINTAINERS.md` in a
follow-up PR after the lazy-consensus window closes, in a separate
section from §1 *Current Maintainers* to keep the merge-authority
boundary visible.

---

## 5. Revoking Reviewer Status

Reviewer status uses the same lazy-consensus mechanic for revocation as
for grant, so the tier does not silently entrench inactive members:

- **Voluntary resignation.** Honored immediately upon a written notice
  in the project's public channels.
- **Sustained inactivity.** If a Reviewer has posted no substantive
  review for six consecutive months, any Maintainer may open a
  `[REVIEWER-REVOCATION]` lazy-consensus thread (72 hours). Absent a
  `-1` from any active Maintainer, status is revoked.
- **Conduct violation.** Reviewer status may be revoked immediately
  through the `GOVERNANCE.md` §11 Code of Conduct enforcement process;
  this short-circuits the lazy-consensus mechanic.

A revoked Reviewer remains a Contributor (§2.2) — no loss of attribution,
no loss of past-merged work, no loss of standing in discussions.

---

## 6. Bridge Requirement for Maintainer Nomination

Under the revised `GOVERNANCE.md` §5.1, **service as a Reviewer for at
least three months is a precondition for Maintainer nomination**. This is
the central reason the tier exists.

The three-month figure aligns with the minimum tenure for Reviewer status
itself (§4 item 1); in practice a Maintainer candidate will usually have
served as a Reviewer for longer than the minimum before being nominated
under the §5.1 six-month overall track record.

Existing Maintainers at the time of `GOVERNANCE.md` §2.5 adoption are
**grandfathered** — the precondition is forward-looking and does not
retroactively unseat anyone.

---

## 7. What This Tier Is *Not*

- **Not** a co-maintainer-lite tier. Reviewers do not hold merge access
  in any area, even narrowly. There is no path-scoped `write` permission
  through this tier; that remains a Maintainer-only privilege under
  CODEOWNERS once branch protection is enabled.
- **Not** an attempt to expand voting. Reviewers carry zero formal vote
  weight in §4.1 or §4.2. They contribute opinion; Maintainers
  contribute votes.
- **Not** a release-engineering role. Release authority, key custody,
  and succession responsibilities remain Maintainer-only and continue to
  be tracked in `GOVERNANCE.md` §8 and `MAINTAINERS.md`.
- **Not** a permanent appointment. The §5 revocation mechanic is
  intentionally as lightweight as the §4 grant mechanic.

---

## 8. Update Policy

Substantive changes to this document — adding or removing a Reviewer
capability, changing the bridge-requirement duration in §6, changing the
grant or revocation procedure in §4 or §5 — are **governance-amendment
class** because they affect the §5.1 advancement path. They follow
`GOVERNANCE.md` §13: a 14-day public RFC labeled
`[GOVERNANCE AMENDMENT RFC]` followed by a §4.2 supermajority vote.

Editorial corrections (typos, broken links, formatting) may be merged by
any Maintainer without a vote, per `GOVERNANCE.md` §13.
