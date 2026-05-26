# `verify --json` v1 output-contract snapshots

This directory pins the versioned `attestplane verify --json` contract for CI
gating.

- `pass.json` snapshots the accept path and the `exit_code = 0` contract.
- `fail.json` snapshots a verifier rejection and the stable non-zero failure
  contract (`exit_code = 1`), distinct from usage/I-O/schema errors.

Add a new `vN/` directory for incompatible output-shape changes instead of
mutating these v1 snapshots in place.
