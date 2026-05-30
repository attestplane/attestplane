// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { defineConfig } from 'vitest/config';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  cacheDir: resolve(__dirname, '.vitest-cache'),
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
    reporters: 'default',
  },
});
