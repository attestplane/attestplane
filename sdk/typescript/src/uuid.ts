// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { randomBytes } from 'node:crypto';

/**
 * Generate a UUIDv7 string without relying on an external runtime dependency.
 *
 * The tests only need the stable v7 shape and timestamp ordering semantics.
 */
export function uuidV7(now: Date = new Date()): string {
  const bytes = randomBytes(16);
  const timestamp = BigInt(now.getTime());

  for (let i = 5; i >= 0; i--) {
    bytes[i] = Number((timestamp >> BigInt((5 - i) * 8)) & 0xffn);
  }

  bytes[6] = (bytes[6] & 0x0f) | 0x70;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Buffer.from(bytes).toString('hex');
  return (
    `${hex.slice(0, 8)}-${hex.slice(8, 12)}-` +
    `${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
  );
}
