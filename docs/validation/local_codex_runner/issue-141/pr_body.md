Fixes #141

## Summary

Local Codex runner repair for: P2 docs: Extend #125 with the v1.7.1 SDK + CLI delta

Labels: type:docs, area:docs, priority:P2, planned-task, auto-codex-approved

## Validation

# Gate Report: PASS

Gate: `type:docs`

## Commands

- `python -m compileall scripts`: exit=0

## Safety Checklist

- [x] No automatic merge.
- [x] No tag creation or tag movement.
- [x] No package publish.
- [x] No PyPI push.
- [x] No severity downgrade.
- [x] No release gate weakening.
- [x] Secret-bearing files and token/cookie material are not logged.

## Evidence

/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-141

## Residual Risks

None

## No Publish / Tag / PyPI Confirmation

This PR was created for human review only. It does not merge `main`, create tags, publish packages, or push to PyPI.
