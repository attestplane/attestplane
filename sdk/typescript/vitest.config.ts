// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { defineConfig } from 'vitest/config';

export default defineConfig({
  cacheDir: '/private/tmp/attestplane-vitest-cache',
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
    reporters: 'default',
  },
});
