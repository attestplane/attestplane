// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0

import { existsSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const packageRoot = resolve(scriptDir, '..');
const tempRoot = '/private/tmp/attestplane-typescript-conformance';
const nodeModulesDir = resolve('/private/tmp', 'node_modules');
const localNodeModulesDir = resolve(packageRoot, 'node_modules');
const localUuidDir = resolve(localNodeModulesDir, 'uuid');
const configPath = resolve(tempRoot, 'vitest.conformance.config.mjs');

mkdirSync(tempRoot, { recursive: true });
mkdirSync(nodeModulesDir, { recursive: true });

let createdLocalNodeModulesDir = false;
if (!existsSync(localNodeModulesDir)) {
  mkdirSync(localNodeModulesDir, { recursive: true });
  createdLocalNodeModulesDir = true;
}

let createdUuidLink = false;
if (!existsSync(localUuidDir)) {
  symlinkSync(resolve('/Users/macworkers/Projects/webprobe/node_modules/uuid'), localUuidDir, 'dir');
  createdUuidLink = true;
}

writeFileSync(
  configPath,
  `export default {
  cacheDir: ${JSON.stringify(resolve(tempRoot, '.vitest-cache'))},
  test: {
    include: ['test/conformance.test.ts'],
    environment: 'node',
    reporters: 'default',
  },
};
`,
  'utf8',
);

const result = spawnSync(
  'npm',
  ['exec', '--', 'vitest', 'run', '--config', configPath, 'test/conformance.test.ts'],
  {
    cwd: packageRoot,
    env: {
      ...process.env,
      NODE_PATH: [resolve('/Users/macworkers/node_modules'), process.env.NODE_PATH]
        .filter(Boolean)
        .join(':'),
    },
    stdio: 'inherit',
  },
);

if (createdUuidLink) {
  rmSync(localUuidDir, { force: true });
}
if (createdLocalNodeModulesDir) {
  rmSync(localNodeModulesDir, { recursive: true, force: true });
}

process.exit(result.status ?? 1);
