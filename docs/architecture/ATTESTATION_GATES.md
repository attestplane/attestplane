<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# ATTESTATION_GATES — Attestplane A1–A5

> **Status:** v0.0.2-alpha 修订稿。A1–A4 pre-merge 强制；**A5 已激活**（pre-merge 校验 + nightly 完整 RFC-3161 信任链）。
> 任何 A 失败 = 阻塞合并或阻塞发布，不接受绕过。
>
> **命名沿革：** 本文件的 gate 编号沿用项目早期 `acceptance` 分支命名传统（AIOS Q1–Q20 → Attestplane A1–A5），与 AIOS `ACCEPTANCE_CRITERIA.md` 同源；详见 `docs/architecture/aios_to_attestplane_migration_plan_20260517.md` § 命名沿革。

---

## 0. 总览

### 验收清单编号

| 范围                  | 编号 | 触发时机                          | 当前状态                       |
|-----------------------|------|-----------------------------------|--------------------------------|
| 规范化字节确定性      | A1   | pre-merge                         | v0.0.1-alpha 通过              |
| 单事件 hash 完整性    | A2   | pre-merge                         | v0.0.1-alpha 通过              |
| 重排序与删除检测      | A3   | pre-merge                         | v0.0.1-alpha 通过              |
| 跨语言字节一致性      | A4   | pre-merge                         | v0.0.1-alpha 通过              |
| 段基数可验证（锚定）  | A5   | pre-merge + nightly + release     | **v0.0.2-alpha 激活**          |

### 失败语义

- **pre-merge** — CI 门控，PR 不得合并。`.github/workflows/sdk-python.yml`、`sdk-typescript.yml` 在 PR 流水线中直接执行。
- **nightly** — 定时跑，失败打开 P0 issue，48 h 内必须修复才可 release。
- **release blocker** — 任意 A 失败则 release tag 不可打出；签发 GitHub Release / npm `latest` 之前必须全部通过。

### 与 AIOS Q1–Q20 的关系

Attestplane A1–A5 选取了 AIOS Q-item 中**与 substrate（hash chain + canonical JSON + 跨语言）直接相关**的子集。AIOS Q1/Q2/Q5/Q7/Q10/Q12/Q14/Q15/Q18/Q19 等涉及 control-plane / lease / budget / tenant 的项目，留在 AIOS 商业版仓库；Attestplane 不承载这些语义。

| AIOS Q | Attestplane A | 备注 |
|--------|---------------|------|
| Q17（schema drift） | A1 | 改造为"canonical-JSON 字节确定性" |
| Q11（stale artifact_sha256） | A2 | 改造为"单事件 hash 完整性"（不绑定 eval 语义） |
| Q16（audit hash mismatch） | A3 | 扩展为"重排序 + 删除 + 篡改"三类 |
| —（Attestplane 独有） | A4 | 跨语言 Python ↔ TypeScript 字节一致性 |
| Q8（replay）+ Q20（audit coverage） | A5 | M5 RFC-3161 锚定后才能完整验证段基数 |

---

## 1. 验收清单

---

### A1：规范化字节确定性（Canonical JSON byte-determinism）

**类别**：Canonicalization
**Milestone 强制**：v0.0.1-alpha（已通过）
**触发时机**：pre-merge

**测试方法**：

- 步骤 1: 构造一个包含全部支持类型的 `EventDraft`（string with non-NFC 字符、嵌套 object、array、boolean、null、RFC 3339 µs UTC datetime、base64url bytes、`SubjectRef`）。
- 步骤 2: 调用 `canonicalize(draft)` 两次，比对两次输出的字节序列是否完全一致。
- 步骤 3: 对同一逻辑值的不同输入形式（key 顺序乱序、string 等价但 unicode 形式不同的两种写法、`2026-05-17T00:00:00.000000Z` 与 `2026-05-17T00:00:00.000000+00:00`）调用 `canonicalize`，验证输出字节相同。
- 步骤 4: 对**禁止类型**（float、NaN、Infinity、非 UTC 时区、未 NFC 归一化的 string）调用 `canonicalize`，验证抛出 `CanonicalizationError`。

**期望失败模式**：

- 重复调用同一输入字节不一致 → 测试 fail，stderr 包含 `CANONICAL_DETERMINISM_BROKEN`。
- 等价输入字节不一致 → 测试 fail，stderr 包含 `CANONICAL_EQUIVALENCE_BROKEN: <field_path>`。
- 禁止类型未抛异常 → 测试 fail，stderr 包含 `CANONICAL_FORBIDDEN_TYPE_ACCEPTED: <type_name>`。

**测试位置**：

- Python: `sdk/python/tests/test_canonical.py`
- TypeScript: `sdk/typescript/test/canonical.test.ts`

**反例**（绕过则视为违规）：

- canonicalize 实现内部使用 `dict.__iter__` 而非显式 key 排序（Python 3.7+ insertion order 不等于 canonical 顺序）。
- TypeScript 实现使用 `JSON.stringify` 默认行为，未对 key 排序、未拒绝 `NaN`。
- 禁止类型只 warn 不 raise（允许 float 静默写入 chain）。

---

### A2：单事件 hash 完整性（Per-event hash integrity）

**类别**：HashChain
**Milestone 强制**：v0.0.1-alpha（已通过）
**触发时机**：pre-merge

**测试方法**：

- 步骤 1: 构造一条由 5 个事件组成的合法 chain，依次 `chain.append(event_i)`，记录每个 event 的 `event_hash` 与 `prev_hash`。
- 步骤 2: 对 chain 的第 3 个事件，修改 payload 中任意一个字段（例如把 `subject.ref = "u_a"` 改为 `subject.ref = "u_b"`），但保留原 `event_hash` 不变。
- 步骤 3: 调用 `verify_chain(events)`，预期检测到 hash 不匹配。
- 步骤 4: 还原步骤 2 的修改，验证 `verify_chain` 通过。

**期望失败模式**：`verify_chain` 抛出 `ChainVerificationError`，`error.code == "EVENT_HASH_MISMATCH"`，`error.seq == 3`，message 包含期望 hash 与实际 hash 的前 16 字符。还原后 `verify_chain` 返回正常（无异常）。

**测试位置**：

- Python: `sdk/python/tests/test_hashchain.py::test_tampered_payload_detected`
- TypeScript: `sdk/typescript/test/hashchain.test.ts`（同名 case）

**反例**（绕过则视为违规）：

- `verify_chain` 只对比 `prev_hash` 链而不重算 `event_hash`（绕过 payload 一致性校验）。
- 实现使用 MD5 / SHA-1 等已破解 hash（必须 SHA-256，与 ADR-0002 锁定一致）。
- 实现在 hash 输入中跳过任何字段（如 `timestamp` 不参与 hash），允许该字段被静默修改。

---

### A3：重排序与删除检测（Reorder & deletion detection）

**类别**：HashChain
**Milestone 强制**：v0.0.1-alpha（已通过）
**触发时机**：pre-merge

**测试方法**：

- 步骤 1: 构造一条由 5 个事件组成的合法 chain，记录原始 `events` 列表。
- 步骤 2: **重排序场景**：交换 `events[2]` 与 `events[3]` 的位置（不修改任何 hash），调用 `verify_chain`。
- 步骤 3: **删除场景**：从 `events` 中删除 `events[2]`，调用 `verify_chain`。
- 步骤 4: **插入场景**：在 `events[2]` 与 `events[3]` 之间插入一条新构造的事件（hash 字段独立合法），调用 `verify_chain`。

**期望失败模式**：

- 步骤 2 → `ChainVerificationError`，`error.code == "PREV_HASH_MISMATCH"`，`error.seq == 3`。
- 步骤 3 → `ChainVerificationError`，`error.code == "SEQUENCE_GAP"` 或 `PREV_HASH_MISMATCH`，`error.seq == 3`。
- 步骤 4 → `ChainVerificationError`，`error.code == "PREV_HASH_MISMATCH"`，`error.seq == 3`（新事件的 `prev_hash` 指向原 `events[1].event_hash`，而原 `events[3]` 期望的 `prev_hash` 指向原 `events[2].event_hash`，必有一处断裂）。

**测试位置**：

- Python: `sdk/python/tests/test_hashchain.py::test_reorder_detected`、`::test_deletion_detected`、`::test_insertion_detected`
- TypeScript: `sdk/typescript/test/hashchain.test.ts`（同名 case）
- Property-based: `sdk/python/tests/test_properties.py`（hypothesis fuzzer 覆盖任意 reorder/delete/insert）

**反例**（绕过则视为违规）：

- `verify_chain` 仅校验首尾 hash（忽略中间 `prev_hash` 链）。
- 实现允许通过 `verify_chain(events, skip_seq=[3])` 等参数跳过指定 seq 的校验。
- 实现使用 `seq` 字段排序 events 再校验（任何允许 caller 重排序后通过的实现都违反 A3）。

---

### A4：跨语言字节一致性（Cross-language byte conformance）

**类别**：Conformance
**Milestone 强制**：v0.0.1-alpha（已通过）
**触发时机**：pre-merge

**测试方法**：

- 步骤 1: 从 `sdk/python/tests/conformance/vectors.json` 加载 10 个 frozen vector，每个 vector 包含 `(input_event_draft, expected_canonical_bytes_hex, expected_event_hash_hex, expected_chain_after_append_hex)`。
- 步骤 2: Python 端：对每个 vector 调用 `canonicalize(draft)` 与 `event_hash(draft, prev_hash)`，对比输出的 hex 字符串与 `expected_*_hex` 字段。
- 步骤 3: TypeScript 端：使用相同的 `vectors.json`，重复步骤 2，对比同一组 expected 值。
- 步骤 4: schema 版本校验：vectors.json 的 `schema_version` 字段必须等于 `1`（ADR-0002 锁定值）；不等则测试 fail。
- 步骤 5: vector 数量校验：vectors.json 中 vector 数量必须 ≥ 10；少于 10 则测试 fail（防止 vector 被静默删除）。

**期望失败模式**：

- 任意 vector 在 Python 或 TypeScript 端输出不匹配 → 测试 fail，stderr 包含 `CONFORMANCE_BYTE_MISMATCH: vector=<id>, lang=<python|typescript>, field=<canonical|event_hash|chain>`。
- `schema_version != 1` → 测试 fail，stderr 包含 `CONFORMANCE_SCHEMA_DRIFT: expected=1, actual=<N>`，提示需要先发布 ADR 升级 schema_version。
- vector 数量 < 10 → 测试 fail，stderr 包含 `CONFORMANCE_VECTOR_SET_INCOMPLETE`。

**测试位置**：

- Python: `sdk/python/tests/test_conformance.py`
- TypeScript: `sdk/typescript/test/conformance.test.ts`
- CI 工作流：`.github/workflows/sdk-python.yml` 与 `.github/workflows/sdk-typescript.yml`（两侧分别独立执行，共享同一 `vectors.json`）

**反例**（绕过则视为违规）：

- 一侧 SDK 在测试失败时通过修改 `vectors.json` 让两侧"对齐"（应改实现使其符合 vector，而非反过来）。
- `schema_version` 字段被绕过：实现接受任意 schema_version 而不抛错。
- TypeScript 端使用与 Python 端不同的 vector 子集（任何 vector 必须双语言都跑）。
- vector 生成器 `generate_vectors.py` 在 CI 中自动运行刷新 vectors.json（vectors.json 必须是 frozen 输入，不可由 CI 重新生成）。

---

### A5：段基数可验证（Segment cardinality via RFC-3161 anchoring）

**类别**：Anchoring + Audit
**Milestone 强制**：**v0.0.2-alpha 激活**（设计骨架 + 真 RFC-3161 实现已合入 `main`）
**触发时机**：pre-merge + nightly + release blocker

**v0.0.2-alpha 已实施的部分**：

- **Python 模块全部 ship**：`attestplane.anchoring.{base, mock, composite, verifier, worker, rfc3161, testing, http, ocsp, eidas}` —— 10 个独立模块
- **TypeScript 模块全部 ship**：`sdk/typescript/src/{anchoring.ts, der.ts, rfc3161.ts}` —— 真 DER 解析 + 真 RSA-SHA256 签名校验（用 `node:crypto`，零额外 npm 依赖）
- **TestTSAAuthority** 自签 CA + 任意深度 intermediate 链 + leaf cert + 真 RSA-PKCS1v15-SHA256 签名 + asn1crypto RFC-3161 编解码 + 真 RFC-6960 OCSP 响应（issuer-signed 模式）
- **真 RFC-3161 解析器（Python `rfc3161.py` + TypeScript `rfc3161.ts`）**：parse_timestamp_response + verify_timestamp_token 真签名校验：messageImprint、leaf 签名、**多级 intermediate 链路（含 BasicConstraints.cA 强制 + 循环检测 + max_chain_depth 限制）**、每个 cert 的 validity window
- **真 RFC-6960 OCSP（Python `ocsp.py`）**：parse_and_verify_ocsp 校验响应方 RSA 签名、按 serial 匹配 SingleResponse、good/revoked/unknown 状态解码、thisUpdate/nextUpdate 时效检查；verifier 自动按 leaf issuer-DN 查找匹配的 OCSP issuer cert
- **真 HTTP transport（Python `http.py`）**：`Rfc3161HttpProvider` + `FreeTSAProvider` + `DigiCertProvider` + `UrllibHttpTransport`（stdlib，无 requests）+ `RecordedHttpTransport`（测试 replay）+ nonce 校验
- **eIDAS Trusted List 加载器（Python `eidas.py`）**：parse_trusted_list 解析 ETSI TS 119 612 XML，按 ServiceTypeIdentifier `http://uri.etsi.org/TrstSvc/Svctype/TSA/QTST` 过滤 qualified TSA，提取 X.509 证书；纯 stdlib，无 anchor extras 依赖
- **`sdk/python/tests/conformance/anchor_vectors.json`** —— 3 个 frozen vector，每个含真 RFC-3161 TimeStampResp DER + 真 OCSP 响应 + 真 cert chain；Python 和 TypeScript 共享同一份 vector 文件
- **170 个 anchoring 测试**：Python 120（base 41 + worker 15 + rfc3161 14 + anchor_vectors 9 + ocsp 9 + multihop 9 + eidas 9 + http 14）+ TypeScript 50（anchoring 38 + rfc3161 12），全部 pre-merge 通过

**测试方法**：

- 步骤 1: 执行一组连续 100 个事件，分为 10 个 segment（每段 10 个事件），每段结束调用 `seal_segment(chain, segment_id, tsa_url)`，从 RFC-3161 TSA 获取 timestamp token（TST），将 TST + 段头 hash + 段尾 hash + 段基数 N=10 写入 `segment_anchors` 持久化。
- 步骤 2: 调用 `verify_anchored_chain(events, anchors)`，重算每段头尾 hash 并比对 TST 中嵌入的 messageImprint 是否匹配；同时校验段基数 `count(events_in_segment) == anchor.cardinality`。
- 步骤 3: 篡改场景：删除 segment 3 中的任意一条事件，重新调用 `verify_anchored_chain`，预期检测到段基数不匹配。
- 步骤 4: TSA 时间单调性：检查相邻 anchor 的 TST 时间戳 `anchor[n].tst_time <= anchor[n+1].tst_time`。

**期望失败模式**：

- TSA 不可达或返回非法响应 → `AnchoringError`，`error.code == "TSA_UNAVAILABLE"`；nightly 失败但 pre-merge 不阻塞（TSA 是外部依赖）。
- 段基数不匹配 → `ChainVerificationError`，`error.code == "SEGMENT_CARDINALITY_MISMATCH"`，`error.segment_id == 3`，`error.expected == 10`，`error.actual == 9`。
- TST messageImprint 不匹配 → `ChainVerificationError`，`error.code == "ANCHOR_HASH_MISMATCH"`。
- TSA 时间倒退 → `ChainVerificationError`，`error.code == "ANCHOR_TIME_REGRESSION"`。

**测试位置**：

Python 端（120 个用例，pre-merge）：

- `sdk/python/tests/anchoring/test_anchoring.py` —— 设计骨架 41 个用例（types、abstract base、mock provider、composite、verifier 接口）
- `sdk/python/tests/anchoring/test_worker.py` —— Anchorer 后台 worker 15 个用例（retry / backoff / quarantine / clock-skew / 线程安全）
- `sdk/python/tests/anchoring/test_rfc3161.py` —— TestTSAAuthority 端到端 14 个用例（真 RSA 签名、cert 过期、未知 trust root、tampered token）
- `sdk/python/tests/anchoring/test_anchor_vectors.py` —— frozen `anchor_vectors.json` 重放 9 个用例（含真 OCSP 全路径）
- `sdk/python/tests/anchoring/test_ocsp.py` —— OCSP 解析 + 签名校验 9 个用例（good / revoked / synthetic 拒绝 / 时效 / 错误 issuer / serial mismatch）
- `sdk/python/tests/anchoring/test_multihop.py` —— Multi-hop intermediate cert chains 9 个用例（2-tier / 3-tier / 4-tier / max_depth / 中间 cert 过期 / 非 CA cert 拒绝）
- `sdk/python/tests/anchoring/test_eidas.py` —— eIDAS Trusted List 解析 9 个用例（QTST 抽取 / 跳过非 TSA / 拒绝 withdrawn / 多语言 ServiceName）
- `sdk/python/tests/anchoring/test_http.py` —— HTTP transport + FreeTSA + DigiCert provider 14 个用例（RecordedTransport replay / nonce 校验 / 不可达 host 拒绝）

TypeScript 端（50 个用例，pre-merge）：

- `sdk/typescript/test/anchoring.test.ts` —— 设计骨架 38 个用例（与 Python 对等）
- `sdk/typescript/test/rfc3161.test.ts` —— 跨语言一致性 12 个用例：加载 Python 生成的 `anchor_vectors.json`，通过手写 DER parser + `node:crypto.verify('RSA-SHA256')` 重新校验所有 3 个 vector

nightly 工作流（`.github/workflows/nightly-anchor.yml`）：对真 FreeTSA endpoint 发起 1 次锚定请求，端到端验证 trust chain；失败开 P0 issue per ADR-0003 § 4 failure-mode

**反例**（绕过则视为违规）：

- 实现接受空的 anchor 集合而判定 chain "verified"（必须至少校验过一个 anchor）。
- 段基数字段允许 caller 在 verify 时覆盖（如 `verify_anchored_chain(events, anchors, override_cardinality=True)`）。
- TST 使用本地时间而非 TSA 返回的 `genTime`。
- 段头尾 hash 不写入 anchor（仅写入 segment_id），导致段内任意篡改可绕过。
- 不传 `trust_roots_der` 时 verifier 把 `cert_status` 标 `VALID` 而非 `VALID_UNVERIFIED`（绕过真签名校验）。
- TSA 返回 `granted_with_mods` 之外的状态时仍构造 `AnchorRecord`（必须 `AnchorVerificationError`）。
- OCSP 响应包含 v0.0.1-alpha 占位 synthetic bytes（`ATTESTPLANE-TEST-OCSP-V1|...`）而 verifier 接受为 valid（必须由 `_is_synthetic_legacy` 检查显式拒绝）。
- Multi-hop chain walk 接受 BasicConstraints.cA=false 的 cert 作为 intermediate（必须 `AnchorVerificationError`，错误信息含"not a CA"）。
- Multi-hop chain walk 超过 `max_chain_depth` 仍继续（必须 fail with "depth exceeded"）。
- eIDAS Trusted List 接受 `ServiceStatus == withdrawn` 或 `revoked` 的服务为 trust root（必须只接受 `granted` / `undersupervision`）。
- TypeScript 端使用与 Python 不同的 DER 解析行为（任何 anchor_vectors.json 必须双语言都通过）。

**Public-claim 升级**（v0.0.2-alpha 起）：

| 走的路径 | 允许的 `implementation_status` 措辞 |
|---|---|
| `verify_chain_with_anchors(..., trust_roots_der=[...])` 返回 `cert_status="VALID"`（含真 RFC-3161 签名 + 真 OCSP good 状态 + 完整 cert chain） | `field_supported` / `verified_in_test` |
| 仅 `verify_chain_with_anchors(events, anchors)`（无 trust_roots_der），`cert_status="VALID_UNVERIFIED"` | `designed_toward` |
| live TSA/provider_id 需要 claim-safe 确认但无法确认时进入 `verification_status="quarantined"` | `designed_toward`（never claim-safe verified） |
| 仅 `MockTSAProvider`（无真签名） | `designed_toward` |
| `FreeTSAProvider` / `DigiCertProvider` 对真 endpoint 成功验证 | `verified_in_test`（基于 nightly 工作流证据） |
| `load_qualified_tsa_trust_roots()` + 上述真验证路径 | `field_supported` for eIDAS qualified-TSA； `designed_toward` for full LOTL chain validation（XML 签名校验未 ship） |

任何对外材料引用 `cert_status="VALID"` 时 MUST 同时说明：trust_roots_der 的来源（自建 / DigiCert / eIDAS LOTL 快照 / 等）。trust root 来源是合规论证的核心，verifier 输出本身只证明"信任根签了链"，不证明"信任根可信"。

---

## 2. 完整 5 条速查表

| A   | 一句话约束                                | 类别              | Milestone   | 触发时机         |
|-----|-------------------------------------------|-------------------|-------------|------------------|
| A1  | canonical-JSON 字节确定 + 等价输入字节同  | Canonicalization  | v0.0.1-alpha | pre-merge        |
| A2  | 单事件 payload 篡改 → verify_chain fail   | HashChain         | v0.0.1-alpha | pre-merge        |
| A3  | reorder / delete / insert → verify fail   | HashChain         | v0.0.1-alpha | pre-merge        |
| A4  | Python ↔ TypeScript 同 vector 字节相同    | Conformance       | v0.0.1-alpha | pre-merge        |
| A5  | RFC-3161 anchor 段基数与段头尾 hash 一致  | Anchoring + Audit | v0.0.2-alpha | pre-merge + nightly + release|

---

## 3. 失败处理流程

### pre-merge 失败（A1–A4）

1. CI workflow `sdk-python` 或 `sdk-typescript` 标红。
2. PR 不可合并，CODEOWNERS 不应批准。
3. 修复对应实现（**不**修改 vectors.json / 不放宽测试），重推 commit。
4. 若 vectors.json 确需变更（schema 升级），先开 ADR，PR 描述中链接 ADR 并 bump `schema_version`。

### nightly 失败（A5，M5 起）

1. `.github/workflows/nightly-anchor.yml` 失败 → GitHub Actions 自动开 issue，title 形如 `[nightly-fail] A5 segment cardinality 2026-MM-DD`，label `gate-failure` `priority-P0`。
2. 维护者 48 h 内必须 ack 并定位：是 TSA 外部故障，还是 substrate 实现 bug。
3. TSA 外部故障：在 issue 中记录 TSA 响应日志，等待 TSA 恢复后重试；超过 7 天则评估更换 TSA。
4. substrate bug：开修复 PR，merge 后 nightly 必须连续 3 次绿。

### release blocker（所有 A）

签发 GitHub Release（tag `v*`）之前，`sign-release.yml` 检查最近一次 nightly 运行结果：

- A1–A4 在最近一次 main 分支 CI 中必须全绿。
- A5（M5 起）在最近 7 天 nightly 中至少 5 次成功。
- 任意条件不满足 → release workflow 早退，tag 不打出，发出 P0 issue。

---

## 4. 维护

- 新增 A 项：开 ADR，更新本文件 § 0 总览表与 § 1 验收清单，bump migration plan 中的 gate 计数。
- 现有 A 项变更失败语义：开 ADR，触发 release note 中的 "behavior change" 段。
- 删除 A 项：禁止；只能在 ADR 中标注 deprecated 并保留测试至少 2 个 minor 版本。

**Authority**：v0.0.1-alpha 阶段由 founder 单独维护本文件；当 maintainer 团队 > 1 时改由 `gates-review` 小组按 `GOVERNANCE.md` 流程决议。
