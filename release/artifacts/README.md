# Release Artifact Manifests

This directory records alpha-safe release artifact hygiene manifests.

The manifests are evidence inventory files. They do not publish artifacts,
create tags, sign assets, or claim production-grade supply-chain security.

Each manifest records:

- the release tag and target commit;
- expected artifact classes;
- whether each artifact is required for the release;
- whether it was published;
- checksum and signature expectations;
- provenance readiness status; and
- no-go supply-chain claims.

For v0.0.2-alpha, this directory is a post-release hygiene baseline. It must
not be read as a retroactive claim that all possible release artifacts were
uploaded, signed, or attested.
