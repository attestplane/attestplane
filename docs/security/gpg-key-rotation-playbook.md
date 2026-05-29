<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# GPG Key Rotation Playbook — `security@attestplane.com`

**Scope.** Operational procedure for generating, publishing, rotating, and
revoking the GPG key bound to `security@attestplane.com`. Owner: the
Attestplane maintainer holding the security contact role (rotates per
`MAINTAINERS.md`).

**Status target.** This playbook is the future operational path. The
project has explicitly deferred the `security@attestplane.com` GPG
foundation until the later security milestone recorded in
[`SECURITY.md`](../../SECURITY.md); no key material is generated yet, and
no fingerprint is published in repository history, issue text, PR text, or
logs.

## 1. Why GPG (and where it does not apply)

| Surface | Signature mechanism | Notes |
|---|---|---|
| Release artifacts (`*.tar.gz`, SBOM, SLSA provenance) | **cosign keyless via Fulcio OIDC** (`scripts/release/sign_assets_cosign_keyless.sh`) | This is the primary supply-chain signature path. GPG is **not** used for release artifact signing. |
| Security advisories / coordinated disclosure email | **GPG (this key)** | Reporters encrypt sensitive PoCs to `security@attestplane.com` using this key. |
| Git commit / tag signatures by maintainers | Individual maintainer keys (per `MAINTAINERS.md`) | This security key is **not** a personal commit-signing key. |

The two signing systems are deliberately independent. A compromise of the
GPG key does not invalidate any released artifact, and a compromise of the
maintainer's cosign OIDC identity does not expose past CVE reports.

## 2. Key shape

- Primary: **ed25519**, capability `cert` only.
- Signing subkey: **ed25519**, capability `sign`.
- Encryption subkey: **cv25519**, capability `encrypt`.
- UID: `Attestplane Security <security@attestplane.com>`.
- Expiry: **2 years** from generation. Renew (extend `Expire-Date`) at most
  60 days before expiry; never let the live key lapse.

## 3. Generation — first key

When the deferral is lifted, run the generation step **on the maintainer's
own secure laptop or an air-gapped machine**. Never on CI, never inside an
agent context.

```bash
./scripts/security/generate-security-gpg-key.sh --dry-run   # review config
./scripts/security/generate-security-gpg-key.sh             # actually generate
```

The script prints the fingerprint and the ASCII-armored public key. Copy
the fingerprint; the public key block is what gets published.

**Strongly recommended:** move the primary key offline and keep only the
subkeys on a hardware token (YubiKey 5C / OpenPGP smartcard). Procedure:

1. Generate as above on an air-gapped machine.
2. `gpg --export-secret-keys --armor <fpr> > primary.asc` (store on
   encrypted offline media; never on the working laptop).
3. `gpg --edit-key <fpr>` → `keytocard` each subkey onto the YubiKey.
4. `gpg --delete-secret-keys <fpr>` on the online laptop, leaving only the
   subkey stubs that reference the smartcard.

## 4. Publication

Once the key exists, publish through these channels on the same day:

1. **Keyserver upload:**
   `gpg --send-keys --keyserver hkps://keys.openpgp.org <fpr>`
   `gpg --send-keys --keyserver hkps://keyserver.ubuntu.com <fpr>`
   Confirm the `keys.openpgp.org` verification email so the UID is bound to
   the key.
2. **GitHub Settings → SSH and GPG keys → New GPG key** — paste the
   ASCII-armored public key block.
3. **`SECURITY.md`** — open a PR replacing the deferred-status prose under
   `## GPG Key for security@attestplane.com` with the real fingerprint and
   publication details. Reference: this playbook.

## 5. Revocation certificate

Generated once, **immediately after key creation**:

```bash
gpg --output "revoke-<fpr>.asc" --gen-revoke security@attestplane.com
```

Store **two independent copies**:

- Encrypted USB drive in a locked drawer at the maintainer's primary
  residence.
- Paper printout (the file is short ASCII) in a separate physical
  location — bank deposit box or secondary office safe.

Never commit `revoke-*.asc` to git. Never email it to yourself.

## 6. Rotation cadence

- **Scheduled rotation:** 18 months after generation, generate a successor
  key, cross-sign it from the outgoing key, publish in parallel for a
  60-day overlap window, then revoke the old key on the overlap end date.
- **Emergency rotation:** within 24h of suspected compromise — publish the
  revocation certificate, generate and publish a new key, post a
  `SECURITY-ADVISORY` issue tagged `key-rotation` describing the event.

## 7. Alignment with the deferred milestone

`SECURITY.md` and `docs/security/release-signing.md` both record the
current deferral. This playbook remains the operational procedure that
will back the commitment once the deferred milestone is lifted. Until
then, it is intentionally read-only guidance, not an execution recipe.
