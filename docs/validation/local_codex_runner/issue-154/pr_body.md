Fixes #154

## Summary

Local Codex runner repair for: [P1][verifier] Cross-wire canonicalization edge-case vectors into the signed-schema round-trip regression

Labels: priority:P1, area:verifier, planned-task, auto-codex-approved

## Validation

# Gate Report: PASS

Gate: `area:verifier`

## Commands

- `env PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/test_verifier_conformance.py -q`: exit=0
- `env PYTHONPATH=sdk/python/src pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q`: exit=0

## Safety Checklist

- [x] No automatic merge.
- [x] No tag creation or tag movement.
- [x] No package publish.
- [x] No PyPI push.
- [x] No severity downgrade.
- [x] No release gate weakening.
- [x] Secret-bearing files and token/cookie material are not logged.

## Evidence

/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-154

## Residual Risks

None

## No Publish / Tag / PyPI Confirmation

This PR was created for human review only. It does not merge `main`, create tags, publish packages, or push to PyPI.
