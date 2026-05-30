// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { spawnSync } from 'node:child_process';

const forwardedArgs = process.argv.slice(2).filter((arg) => arg !== '--runInBand');
const result = spawnSync('vitest', ['run', ...forwardedArgs], {
  stdio: 'inherit',
});

if (result.error) {
  throw result.error;
}

process.exit(result.status ?? 1);
