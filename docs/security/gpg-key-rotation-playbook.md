<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# GPG Key Rotation Playbook — `security@attestplane.com`

**Scope.** Operational procedure for generating, publishing, rotating, and
revoking the GPG key bound to `security@attestplane.com`. Owner: the
Attestplane maintainer holding the security contact role (rotates per
`MAINTAINERS.md`).

**Status target.** First key generated and published **at or before M5 W6
(2026-08-15 v1.0 GA)**. The placeholder block in `SECURITY.md` is replaced
with the real fingerprint in the same commit that lands this playbook's
output.

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

* Primary: **ed25519**, capability `cert` only.
* Signing subkey: **ed25519**, capability `sign`.
* Encryption subkey: **cv25519**, capability `encrypt`.
* UID: `Attestplane Security <security@attestplane.com>`.
* Expiry: **2 years** from generation. Renew (extend `Expire-Date`) at most
  60 days before expiry; never let the live key lapse.

## 3. Generation — first key

Run **on the maintainer's own secure laptop or an air-gapped machine**.
Never on CI, never inside an agent context.

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

Three channels, all on the same day:

1. **Keyserver upload:**
   `gpg --send-keys --keyserver hkps://keys.openpgp.org <fpr>`
   `gpg --send-keys --keyserver hkps://keyserver.ubuntu.com <fpr>`
   Confirm the `keys.openpgp.org` verification email so the UID is bound to
   the key.
2. **GitHub Settings → SSH and GPG keys → New GPG key** — paste the
   ASCII-armored public key block.
3. **`SECURITY.md`** — open a PR replacing the `TBD` fingerprint placeholder
   under `## GPG Key for security@attestplane.com` with the real fingerprint.
   Reference: this playbook.

## 5. Revocation certificate

Generated once, **immediately after key creation**:

```bash
gpg --output "revoke-<fpr>.asc" --gen-revoke security@attestplane.com
```

Store **two independent copies**:

* Encrypted USB drive in a locked drawer at the maintainer's primary
  residence.
* Paper printout (the file is short ASCII) in a separate physical
  location — bank deposit box or secondary office safe.

Never commit `revoke-*.asc` to git. Never email it to yourself.

## 6. Rotation cadence

* **Scheduled rotation:** 18 months after generation, generate a successor
  key, cross-sign it from the outgoing key, publish in parallel for a
  60-day overlap window, then revoke the old key on the overlap end date.
* **Emergency rotation:** within 24h of suspected compromise — publish the
  revocation certificate, generate and publish a new key, post a
  `SECURITY-ADVISORY` issue tagged `key-rotation` describing the event.

## 7. Alignment with the M5 W6 GA window

`SECURITY.md` commits Attestplane to having a published GPG key on or
before the **v1.0 GA target of 2026-08-15** (M5 W6). The supply-chain
posture table in the same document targets cosign / SBOM / SLSA at M5 W4
(2026-08-01). This playbook is the operational procedure that backs that
commitment; it lands before any private key material exists so the
process is review-ready when the maintainer executes step 3.
