# Storage Compatibility Manifests

This directory records alpha storage format compatibility policy.

The manifests and fixtures are compatibility gates, not a production storage
claim. They document what current readers accept, what they reject, and how
future migrations must behave.

Current scope:

- Python `JsonlStorageBackend`
- one JSON object per newline-terminated record
- read-only scan diagnostics
- ProofBundle export refusal from corrupt storage
- no destructive repair by default
- no database backend or multi-writer correctness claim
