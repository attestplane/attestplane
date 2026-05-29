// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

const root = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  root,
  cacheDir: '.vitest-temp',
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
    reporters: 'default',
  },
});
