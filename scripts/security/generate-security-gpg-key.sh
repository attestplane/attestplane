#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
#
# generate-security-gpg-key.sh
#
# Generates the GPG key for `security@attestplane.com`:
#   * ed25519 primary key (certify only)
#   * ed25519 signing subkey
#   * cv25519 encryption subkey
#   * UID:    Attestplane Security <security@attestplane.com>
#   * Expiry: 2 years from generation date
#
# IMPORTANT — read before running:
#
#   * This script must be run by a maintainer on a secure laptop or
#     air-gapped machine. Do NOT run it in CI, in an agent context, or on a
#     shared host.
#   * The private key material stays on the maintainer's machine. This
#     repository never ships the private key, the passphrase, or the
#     revocation certificate.
#   * Prefer a hardware token (YubiKey 5C / OpenPGP smartcard) as the
#     long-term private-key carrier. See
#     `docs/security/gpg-key-rotation-playbook.md`.
#
# Usage:
#   ./scripts/security/generate-security-gpg-key.sh [--dry-run]
#
#   --dry-run   Print the gpg --batch config and the command that would run,
#               but do not invoke gpg. Useful for review before execution.

set -euo pipefail

UID_NAME="Attestplane Security"
UID_EMAIL="security@attestplane.com"
EXPIRE="2y"

dry_run=false
if [ "${1:-}" = "--dry-run" ]; then
  dry_run=true
elif [ "$#" -gt 0 ]; then
  echo "unknown argument: $1" >&2
  echo "usage: $0 [--dry-run]" >&2
  exit 2
fi

echo "=============================================================="
echo " Attestplane security GPG key generation"
echo "=============================================================="
echo
echo " UID:    ${UID_NAME} <${UID_EMAIL}>"
echo " Algo:   ed25519 (cert) + ed25519 (sign) + cv25519 (encrypt)"
echo " Expiry: ${EXPIRE}"
echo
echo " You are about to generate private key material on this machine."
echo " Make sure this machine is:"
echo "   * Encrypted at rest (FileVault / LUKS)."
echo "   * Not a shared host."
echo "   * Not a CI runner."
echo "   * Not running under an agent / automation context."
echo

if ! command -v gpg >/dev/null 2>&1; then
  echo "error: gpg is not installed on PATH" >&2
  exit 1
fi

gpg_version="$(gpg --version | head -n 1)"
echo " gpg version: ${gpg_version}"
echo

batch_config="$(mktemp -t attestplane-gpg-batch.XXXXXX)"
trap 'rm -f "${batch_config}"' EXIT

cat >"${batch_config}" <<EOF
%no-protection
Key-Type: EDDSA
Key-Curve: ed25519
Key-Usage: cert
Subkey-Type: EDDSA
Subkey-Curve: ed25519
Subkey-Usage: sign
Name-Real: ${UID_NAME}
Name-Email: ${UID_EMAIL}
Expire-Date: ${EXPIRE}
%commit
EOF

echo " gpg --batch --gen-key config to be used:"
echo "--------------------------------------------------------------"
cat "${batch_config}"
echo "--------------------------------------------------------------"
echo
echo " Note: %no-protection is set so gpg --batch does not prompt for a"
echo " passphrase mid-script. Immediately after generation you MUST set a"
echo " strong passphrase with:"
echo
echo "     gpg --edit-key ${UID_EMAIL} passwd"
echo
echo " Then add a cv25519 encryption subkey interactively (gpg --batch"
echo " cannot mix multiple subkey types in one config):"
echo
echo "     gpg --expert --edit-key ${UID_EMAIL}"
echo "     gpg> addkey   # choose (12) ECC (encrypt only) -> Curve 25519"
echo "     gpg> save"
echo

if [ "${dry_run}" = true ]; then
  echo " --dry-run: not invoking gpg. Exiting."
  exit 0
fi

read -r -p " Proceed with key generation on THIS machine? [y/N] " reply
case "${reply}" in
  y|Y|yes|YES) ;;
  *) echo " aborted by user."; exit 0 ;;
esac

echo
echo " >> gpg --batch --gen-key ${batch_config}"
gpg --batch --gen-key "${batch_config}"

echo
echo " >> primary key fingerprint:"
fingerprint="$(gpg --list-keys --with-colons "${UID_EMAIL}" \
  | awk -F: '/^fpr:/ { print $10; exit }')"
echo "    ${fingerprint}"

echo
echo " >> ASCII-armored public key (copy the block below):"
echo "--------------------------------------------------------------"
gpg --armor --export "${UID_EMAIL}"
echo "--------------------------------------------------------------"

echo
echo " Next steps (manual, on this machine):"
echo
echo "   1. Set a strong passphrase:"
echo "        gpg --edit-key ${UID_EMAIL} passwd"
echo
echo "   2. Add the cv25519 encryption subkey:"
echo "        gpg --expert --edit-key ${UID_EMAIL}"
echo "        gpg> addkey   # (12) ECC (encrypt only) -> Curve 25519"
echo "        gpg> save"
echo
echo "   3. Generate and store the revocation certificate offline:"
echo "        gpg --output revoke-${fingerprint}.asc \\"
echo "            --gen-revoke ${UID_EMAIL}"
echo "      Store on an air-gapped USB drive AND a paper printout in a"
echo "      separate physical location. Do not commit it to git."
echo
echo "   4. Upload the public key:"
echo "        gpg --send-keys --keyserver hkps://keys.openpgp.org ${fingerprint}"
echo "        gpg --send-keys --keyserver hkps://keyserver.ubuntu.com ${fingerprint}"
echo "      Then confirm the verification email from keys.openpgp.org."
echo
echo "   5. Add the public key to GitHub:"
echo "        GitHub -> Settings -> SSH and GPG keys -> New GPG key"
echo "        Paste the ASCII-armored block printed above."
echo
echo "   6. Open a PR that replaces the 'TBD' fingerprint placeholder in"
echo "      SECURITY.md with: ${fingerprint}"
echo "      (see docs/security/gpg-key-rotation-playbook.md)."
echo
echo " Done. The private key material remains on THIS machine only."
