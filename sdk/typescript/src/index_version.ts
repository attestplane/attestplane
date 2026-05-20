// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Single source of truth for the package's version string.
 *
 * Isolated in its own module so other modules can read it without
 * importing from `./index.ts`, which would create a circular import
 * (index.ts re-exports symbols from those same modules).
 */

export const VERSION = '1.0.1';
