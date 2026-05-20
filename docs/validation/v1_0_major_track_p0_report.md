# v1.0 Major Track P0 Report

Date: 2026-05-21
Branch: `next/v1.0`
Base commit: `f73d944`

## Scope

This P0 change opens a parallel major-upgrade track without changing the
current stable `autodev-train` path. It does not create releases, tags,
milestones, or issues.

## Added Artifacts

- `MAJOR-UPGRADE.md` defines the major-track triggers, merge rules, and rollback
  path.
- `api/public/v1.0/python_surface_freeze.json` captures the current Python root
  public API surface.
- `api/public/v1.0/typescript_surface_freeze.json` captures the current
  TypeScript root export surface.

## Surface Snapshot

- Python exported symbols: 138.
- TypeScript exported symbols: 206.
- Python freeze SHA-256:
  `5c7f3043c7d1438342a83ff1cff655d58f0794b66d9c993256cc55666297ad47`.
- TypeScript freeze SHA-256:
  `aabd18987036ee40fe57cda1f2c539aaba8ba3d971fd8c5804069f5e5f51f105`.

## Non-Goals

- No issue fan-out.
- No registry publishing from `next/*`.
- No changes to `release-cd`.
- No changes to the running stable train.
- No automatic major-version decision.

## Validation

The public surface files were generated with:

```bash
python scripts/api/extract_python_public_api.py --out api/public/v1.0/python_surface_freeze.json
python scripts/api/extract_typescript_public_api.py --out api/public/v1.0/typescript_surface_freeze.json
```

The intended follow-up is a P1 guard that requires release-gate audit track
when `track:major` work merges into `main`.
