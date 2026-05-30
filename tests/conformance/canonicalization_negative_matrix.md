# Canonicalization Negative Coverage Matrix

This matrix is additive and frozen.
Y means the landed vector covers the edge case; - means it does not.

## Edge coverage

| Edge case | Description | bom-trailing-bytes-raw.json | duplicate-json-keys-raw.json | int64-overflow-timestamp-payload.json | nfd-payload-string.json | v1/duplicate-json-keys.json | v1/embedded-nul-string.json | v1/invalid-surrogate-pair-string.json | v1/leading-zero-number.json | v1/non-minimal-number.json | v1/non-nfc-string.json | v1/non-sorted-object-keys.json | v1/schema-version-mismatch.json | v1/trailing-whitespace.json | v1/nested-array-order.json | v1/deep-nfc-string.json | v1/nested-float-prohibition.json |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dup-keys | Duplicate JSON keys must fail closed before a dict collapse hides the duplicate. | - | Y | - | - | Y | - | - | - | - | - | - | - | - | - | - | - |
| embedded-nul | A raw text input containing U+0000 must fail the text canonicalizer. | - | - | - | - | - | Y | - | - | - | - | - | - | - | - | - | - |
| surrogate | A raw text input containing an unpaired surrogate must fail the text canonicalizer. | - | - | - | - | - | - | Y | - | - | - | - | - | - | - | - | - |
| int-canon | Integer and number edge cases must reject non-canonical encodings. | - | - | Y | - | - | - | - | Y | Y | - | - | - | - | - | - | - |
| nfc | A decomposed Unicode string must fail canonicalization. | - | - | - | - | - | - | - | - | - | Y | - | - | - | - | - | - |
| nfd | A helper-emitted NFC payload rewritten as NFD must fail canonicalization. | - | - | - | Y | - | - | - | - | - | - | - | - | - | - | - | - |
| bom | A raw JSON envelope with a UTF-8 BOM prefix and trailing bytes must fail. | Y | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| key-order | Object keys must remain in canonical sorted order. | - | - | - | - | - | - | - | - | - | - | Y | - | - | - | - | - |
| schema-version | A bundle-like object declaring the wrong schema_version must be rejected. | - | - | - | - | - | - | - | - | - | - | - | Y | - | - | - | - |
| trailing-whitespace | Trailing whitespace after a JSON value is not part of the canonical bytes. | - | - | - | - | - | - | - | - | - | - | - | - | Y | - | - | - |
| nested-array-order | An array with unsorted inner object keys must fail canonicalization. | - | - | - | - | - | - | - | - | - | - | - | - | - | Y | - | - |
| deep-nfc | An NFD string in a deeply nested path must fail canonicalization. | - | - | - | - | - | - | - | - | - | - | - | - | - | - | Y | - |
| nested-float | A float value in a nested JSON path must fail canonicalization as non-canonical restricted JSON. | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | Y |

## Vector inventory

| Path | Case ID | Surface | Expected reason code | Source positive case | Canonical fixture SHA-256 |
| --- | --- | --- | --- | --- | --- |
| `tests/conformance/vectors/canonicalization/negative/bom-trailing-bytes-raw.json` | `canonicalization-negative-bom-trailing-bytes-raw` | `json` | `json.non_canonical_envelope` | `canonicalization-positive-canonical-json-no-bom-trailing` | `80646a0239f736c23369ce8be7cd964d3b3a61de1142a35ff94d93a6884f5899` |
| `tests/conformance/vectors/canonicalization/negative/duplicate-json-keys-raw.json` | `canonicalization-negative-duplicate-json-keys-raw` | `json` | `json.duplicate_key` | `canonicalization-positive-duplicate-json-keys-helper-control` | `28a49dbb24a7f7d3b0be5c878a11a2d2bcd16ad7accaa6a3672ec45d6c438e03` |
| `tests/conformance/vectors/canonicalization/negative/int64-overflow-timestamp-payload.json` | `canonicalization-negative-int64-overflow-timestamp-payload` | `json` | `canonicalization.int64` | `canonicalization-positive-int64-boundary-timestamp-payload` | `024dadd21be7c5cdd7b2bad068f4f328adc6bc75b90ea6a931b1fce264255eb6` |
| `tests/conformance/vectors/canonicalization/negative/nfd-payload-string.json` | `canonicalization-negative-nfd-payload-string` | `json` | `canonicalization.nfc` | `canonicalization-positive-nfc-payload-string` | `5683aebc715c729a81cd27bf66a76fc7ba206852a4314c82a8ee3de9ca06cf43` |
| `tests/conformance/vectors/canonicalization/negative/v1/duplicate-json-keys.json` | `canonicalization-negative-duplicate-json-keys-v1` | `json` | `att.verify.structure_invalid` | `canonicalization-positive-duplicate-json-keys-helper-control` | `79929a7ff74fd5fd77d5a7ebc37eed87a9f6d8a3a63c48b898ca1de91a8274ac` |
| `tests/conformance/vectors/canonicalization/negative/v1/embedded-nul-string.json` | `canonicalization-negative-embedded-nul-string-v1` | `text` | `att.verify.schema_invalid` | `canonicalization-positive-nfc-payload-string` | `070e0749b5479cc261e6dd26e980683f5da9f4321bcc78894e04254c1074609a` |
| `tests/conformance/vectors/canonicalization/negative/v1/invalid-surrogate-pair-string.json` | `canonicalization-negative-invalid-surrogate-pair-string-v1` | `text` | `att.verify.schema_invalid` | `canonicalization-positive-nfc-payload-string` | `ba62f18baec3d9250ff5de47672dd88c0889d150c7c129b32030533f4355e3b8` |
| `tests/conformance/vectors/canonicalization/negative/v1/leading-zero-number.json` | `canonicalization-negative-leading-zero-number-v1` | `json` | `att.verify.schema_invalid` | `canonicalization-positive-int64-boundary-timestamp-payload` | `ac2cfb90bf0808d44b15803ea3bc596ab1aee44e497ff9c4fe1f301a7293d9d8` |
| `tests/conformance/vectors/canonicalization/negative/v1/non-minimal-number.json` | `canonicalization-negative-non-minimal-number-v1` | `json` | `att.verify.canonical_mismatch` | `canonicalization-positive-int64-boundary-timestamp-payload` | `dafa5807d0fd61341e3b4cc5b718d9002c7f3f117e6b4093f9e9db02675ddb3c` |
| `tests/conformance/vectors/canonicalization/negative/v1/non-nfc-string.json` | `canonicalization-negative-non-nfc-string-v1` | `json` | `att.verify.canonical_mismatch` | `canonicalization-positive-nfc-payload-string` | `70c91fb51a16af285249d723c8b4b44502fd981c5e40cd110e3e508fa38491b7` |
| `tests/conformance/vectors/canonicalization/negative/v1/non-sorted-object-keys.json` | `canonicalization-negative-non-sorted-object-keys-v1` | `json` | `att.verify.canonical_mismatch` | `canonicalization-positive-canonical-json-no-bom-trailing` | `af873a8349d965d30b0ab77710338090f3d3979417d284e38f29258d0c3fb348` |
| `tests/conformance/vectors/canonicalization/negative/v1/schema-version-mismatch.json` | `canonicalization-negative-schema-version-mismatch-v1` | `json` | `att.verify.schema_version_unsupported` | `canonicalization-positive-canonical-json-no-bom-trailing` | `7935f935840d61f9b798a56a32ca3f4523b23232b4f3a60b7c4ae18581e1fe63` |
| `tests/conformance/vectors/canonicalization/negative/v1/trailing-whitespace.json` | `canonicalization-negative-trailing-whitespace-v1` | `json` | `att.verify.canonical_mismatch` | `canonicalization-positive-canonical-json-no-bom-trailing` | `3928181a98c72b68a00081f06777f8d7405311d8a9852397ce1c4e0ca101df6c` |
| `tests/conformance/vectors/canonicalization/negative/v1/nested-array-order.json` | `canonicalization-negative-nested-array-order-v1` | `json` | `att.verify.canonical_mismatch` | `canonicalization-positive-canonical-json-no-bom-trailing` | `74c0c0ac1981e012fa619262addee5c9a86320f1c93133a7b3f5d56b012925de` |
| `tests/conformance/vectors/canonicalization/negative/v1/deep-nfc-string.json` | `canonicalization-negative-deep-nfc-string-v1` | `json` | `att.verify.canonical_mismatch` | `canonicalization-positive-nfc-payload-string` | `e23e55d9b6d8d3af957ef715ce1125ff3c116ab01f69f8a4db7cbca654a5bc38` |
| `tests/conformance/vectors/canonicalization/negative/v1/nested-float-prohibition.json` | `canonicalization-negative-nested-float-prohibition-v1` | `json` | `att.verify.canonical_mismatch` | `canonicalization-positive-int64-boundary-timestamp-payload` | `b923b4af3979b397c7b4152f4108ce0811b7b52b1c830b0bbf17ba580cbf9983` |

## Notes

- The matrix rows are the #173 edge classes audited against the landed negative vectors.
- The inventory hashes are canonical-JSON SHA-256 values pinned by `sdk/python/tests/conformance/FIXTURE_HASHES.lock`.
- No edge class is intentionally left uncovered; if a future audit finds one, add a new negative vector and update the matrix in the same change.
