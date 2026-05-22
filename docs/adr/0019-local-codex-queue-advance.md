# ADR 0019: Local Codex Queue Advance

## Status

Accepted

## Context

The stable release train must not publish a new suffix-free version when there is
no real change on `main` after the latest stable tag. That idle state is correct,
but it can hide upstream automation stalls: completed Codex PRs may wait for
merge, and downstream planned-task issues may wait for dependency approval.

## Decision

Extend the local Codex runner with a queue advance stage that runs before normal
issue consumption when explicitly enabled.

The stage has two guarded decisions:

- PR gatekeeper: a Codex PR may be merged only when it targets `main`, is not a
  draft, has clean merge state, has green checks, has no blocking labels, has the
  `auto-merge-ready` label, and the PR author is allow-listed.
- Dependency unlocker: a planned-task issue may receive `auto-codex-approved`
  only when it declares explicit `Depends on: #N` dependencies and all of those
  dependency issues are closed.

Both decisions are pure state machines with unit tests. Write actions remain
disabled unless the matching config flags are explicitly set.

## Consequences

The runner can distinguish healthy release idle from a blocked development
queue. The release train still only reacts to real commits on `main`; queue
advance cannot publish, tag, force-push, or bypass release gates.

Auto-merge remains a higher-risk mode. It requires explicit config, an author
allow-list, and the `auto-merge-ready` label so a human or trusted upstream gate
can keep branch-protection policy in control.
