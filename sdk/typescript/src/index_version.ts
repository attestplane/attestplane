// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Single source of truth for the package's version string.
 *
 * The version is derived at load time from the package's own `package.json`
 * (the published artifact metadata) rather than a hand-maintained literal, so
 * it can never drift from the released package. A hardcoded literal silently
 * shipped a stale "1.8.4" inside the 1.9.x/1.10.0 tarballs.
 *
 * Isolated in its own module so other modules can read it without importing
 * from `./index.ts`, which would create a circular import (index.ts re-exports
 * symbols from those same modules).
 */
import { readFileSync } from 'node:fs';

function readPackageVersion(): string {
  try {
    // From dist/index_version.js (and src/index_version.ts), `../package.json`
    // resolves to the package root manifest, which is always shipped.
    const manifestUrl = new URL('../package.json', import.meta.url);
    const pkg = JSON.parse(readFileSync(manifestUrl, 'utf8')) as { version?: string };
    return pkg.version ?? '0.0.0+unknown';
  } catch {
    return '0.0.0+unknown';
  }
}

export const VERSION: string = readPackageVersion();
