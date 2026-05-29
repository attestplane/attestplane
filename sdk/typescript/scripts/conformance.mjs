// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { existsSync, mkdirSync, symlinkSync, lstatSync, rmSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const packageRoot = resolve(scriptDir, '..');
const nodeModulesDir = resolve(packageRoot, 'node_modules');
const viteTempDir = resolve(nodeModulesDir, '.vite-temp');
const uuidSourceDir = '/Users/macworkers/.config/kilo/node_modules/uuid';
const uuidLinkDir = resolve(nodeModulesDir, 'uuid');

mkdirSync(nodeModulesDir, { recursive: true });
mkdirSync(viteTempDir, { recursive: true });

if (!existsSync(uuidLinkDir) && existsSync(uuidSourceDir)) {
  try {
    symlinkSync(uuidSourceDir, uuidLinkDir, 'dir');
  } catch {
    if (existsSync(uuidLinkDir) && lstatSync(uuidLinkDir).isSymbolicLink()) {
      rmSync(uuidLinkDir, { recursive: true, force: true });
      symlinkSync(uuidSourceDir, uuidLinkDir, 'dir');
    }
  }
}

const result = spawnSync(
  'vitest',
  ['run', 'test/conformance.test.ts', 'test/verifier_conformance.test.ts'],
  {
    cwd: packageRoot,
    env: process.env,
    stdio: 'inherit',
  },
);

if (result.error) {
  throw result.error;
}

process.exit(result.status ?? 1);
