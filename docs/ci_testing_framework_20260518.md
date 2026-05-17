# Attestplane CI Testing Framework — Design v1.0 (2026-05-18)

> **状态**：Draft — 待 founder 审批后实施。
> **战略锚定**：P1 OSS 国际信誉建设阶段（2026-2028），CI 是 EU notified body / Big 4 / 监管机构能"引用"的可信度信号载体。
> **设计原则**：substrate 字节级确定性 + `AP-EVD/1.0` 协议稳定性 + ADR 治理纪律物化为 CI 红线。
> **不追求**：line-coverage 数字、chaos engineering、e2e 浏览器测试（详见 §5 NOT-IN-SCOPE）。

---

## 1. 背景与目标

Attestplane 当前 CI 覆盖 13 个 workflow / 1330 LOC，已通过 6/6 gate（ci / codeql / ossf-scorecard / osv-scanner / reproducible-build / sbom）。但作为面向 EU AI Act + ISO/IEC 42001 + DORA 的 evidence substrate，**当前 CI 没有为以下 P1 战略关键资产建立红线**：

1. `AP-EVD/1.0` 协议 schema 字节级稳定（ADR-0014 v2 刚锁定）
2. Py↔TS 双 SDK 跨语言闭环字节守恒
3. 11 篇 Accepted ADR 的治理纪律（frozen decision blocks）
4. Dual-runner reproducible-build（非单机 self-check）
5. SLSA Level 3 provenance + Sigstore Rekor transparency log

本设计采纳 opus-architect 5-tier 框架 + 7 gap 矩阵，**2-4 周分两 sprint 落地**。

## 2. 当前 CI Baseline（2026-05-18）

| Workflow | LOC | 角色 | 拟归 Tier |
|---|---|---|---|
| `ci.yml` (11 jobs) | 160 | markdown-lint / yaml-lint / typos / codespell / link-check / dco-check / policy-invariants / actionlint / shellcheck / reuse-lint / license-detection | T0 + T1 拆 |
| `sdk-python.yml` (3 jobs) | 88 | lint-and-typecheck / test (cov ≥ 90%) / conformance-vectors-frozen | T1 + T2 拆 |
| `sdk-typescript.yml` (3 jobs) | 91 | lint-and-typecheck / test / build | T1 + T2 拆 |
| `reproducible-build.yml` | 91 | 同机两次构建 wheel diff（**非 dual-runner**） | T4 升级 |
| `codeql.yml` | 42 | static analysis | T2 |
| `osv-scanner.yml` | 44 | dep vuln scan | T2 |
| `scorecard.yml` | 41 | OSSF Scorecard | T3 |
| `sbom.yml` | 71 | CycloneDX SBOM | T4 |
| `nightly-anchor.yml` | 255 | FreeTSA 真实 anchor | T3 |
| `sign-release.yml` | 137 | cosign sign | T4 升级 |
| `publish-python.yml` / `publish-typescript.yml` / `manage-npm.yml` | 310 | release publish | T4 |

**关键现状**：
- `conformance-vectors-frozen` job 已 regen + diff 17 fixtures（覆盖 G7 一半，但单机 ubuntu-latest，无矩阵）。
- `reproducible-build` 是同 runner 上 `.venv1` vs `.venv2`（self-check），不是两台独立 runner（Big 4 / SLSA L3 看的是后者）。
- `sign-release.yml` 已有 cosign 但**未将 attestation 上传 Rekor transparency log**（G4 缺口）。
- 无 protocol schema hash gate（G2）、无 ADR-frozen-block gate（G3）、无 Py↔TS round-trip（G1）。

## 3. 五层 Tier 框架

| Tier | 触发 | 时长预算 | 阻塞？ | 内容 |
|---|---|---|---|---|
| **T0 — Invariant Gates** | 每 push | < 30s | 阻塞 | 17 fixture byte-equality (Py SHA-256 = TS SHA-256) / `AP-EVD/1.0` schema hash 锁 / ADR frozen-block diff / `check-policy.sh` / license headers |
| **T1 — Pre-merge Fast** | 每 PR | < 5 min | 阻塞 | ruff / mypy (single py) / pytest (single py × ubuntu) / biome / tsc / vitest (single node × ubuntu) / typos / markdownlint / lychee (cached) |
| **T2 — Pre-merge Thorough** | 每 PR | < 15 min（并行） | 阻塞 | pytest 矩阵 py3.11/3.12/3.13 × {macos, ubuntu} / vitest node 22/24 / **Py↔TS round-trip** / CodeQL increment / osv-scanner / conformance fixture replay |
| **T3 — Nightly Advisory** | nightly schedule | 不限 | **不阻塞** | nightly-anchor (FreeTSA real) / full lychee (no cache) / Scorecard / dep freshness / benchmark regression / mutation testing (`evidence/`, `protocol/` 子集) / fuzz harness (24h budget) |
| **T4 — Pre-release Blocking** | tag (`v*.*.*`) | 不限 | 阻塞 | dual-runner reproducible-build / SBOM (CycloneDX) + diff 上版 / **in-toto/SLSA L3 provenance** / cosign sign + **Rekor transparency log** / 所有 T0-T2 绿 + 最近 T3 绿 / `AP-EVD/1.0` 跨次版本 backward-compat 回放 |

**性能预算保证**：T0 < 30s 用 cache-warm + minimal deps；T1 < 5 min 用 uv + npm + 单机；T2 < 15 min 用 matrix shard + concurrency cancel-in-progress。

## 4. Gap Matrix（7 条，按优先级）

| # | Gap | Evidence Artifact | Consumer | Cost | Tier | 状态 |
|---|---|---|---|---|---|---|
| **G1** | Py↔TS cross-SDK round-trip（Py 写 → TS 读 → Py 再读，hash 守恒） | round-trip SHA-256 log | Side A 审计 / 适配方 | 低 | T2 | **缺失** |
| **G2** | `AP-EVD/1.0` protocol schema hash lock + canonical JSON serializer 字节稳定性 | schema hash + diff | 协议消费方 / 监管 | 低 | T0 | **缺失** |
| **G3** | ADR-frozen-block enforcement（Accepted ADR 的 Decision 段哈希锁） | ADR diff fail log | OSS 社区 / 治理审计 | 低 | T0 | **缺失** |
| **G4** | in-toto/SLSA L3 provenance + Sigstore Rekor 透明日志 | attestation JSON + Rekor UUID | EU notified body / Big 4 | 中 | T4 | **缺失**（cosign 已有，未上 Rekor） |
| **G5** | Dual-runner reproducible-build（两台独立 runner 输出 byte-equal） | dual-build SHA-256 + diff | 审计 / SLSA | 中 | T4 | **半缺失**（当前同机 self-check） |
| **G6** | Mutation testing on `evidence/` + `protocol/`（mutation score badge） | mutation score badge | 审计 / OSS 公信力 | 中 | T3 | **缺失** |
| **G7** | Conformance fixture regen drift gate（独立 CI 重生 + 比对） | regen log + diff | 适配方 / 协议消费 | 低 | T1 | **半完成**（Py 单机，无 TS 端） |

## 5. NOT-IN-SCOPE（显式拒绝项）

按 architect 设计 + founder 工程纪律（避免 P1 信誉污染）：

1. **不加 line-coverage ≥ X% 门禁** — substrate 重点是"语义正确 + 字节稳定"，coverage 指标会诱导写无意义测试。当前 sdk-python `--cov-fail-under=90` 保留但**不作为 P1 对外信誉信号**（仅本地纪律）。
2. **不加 chaos engineering / 故障注入** — AP 是无状态加密 substrate，无运行时拓扑可混；只增噪音。
3. **不加 e2e 浏览器/UI 测试** — AP 无 UI 层，加 Playwright/webprobe = 自找维护债。

## 6. 第一周 Top-3（最高优先级）

仅落地这 3 个 gap，覆盖 substrate determinism + 协议稳定 + 治理可信三角支柱：

### Sprint-1 (W1, 2026-05-18 → 2026-05-25)

| 优先级 | Gap | Tier | 落地动作 | 预估工时 |
|---|---|---|---|---|
| **P0** | **G2** AP-EVD/1.0 schema hash lock | T0 | 新建 `.github/workflows/invariants.yml` — `policy-invariants` job 移入 + 加 `AP-EVD/1.0` envelope schema 文件 SHA-256 锁（schema 文件改动需显式 bump 版本） | 0.5 天 |
| **P1** | **G3** ADR frozen-block gate | T0 | 在 11 篇 Accepted ADR 内插入 `<!-- frozen-block: start -->...<!-- frozen-block: end -->` 标记 + 新 job 哈希锁该区间 | 1 天（含逐篇人工判断冻结段） |
| **P2** | **G1** Py↔TS round-trip | T2 | 新 job `cross-sdk-roundtrip`：Python 生成 evidence → TS verify + re-serialize → Python re-verify，全程 SHA-256 守恒 | 2-3 天 |

**Sprint-1 验收**：3 job 在 PR 上稳定 < 30s (G2/G3) + < 5min (G1)；连续 5 个 PR 无 flake。

### Sprint-2 (W2-3, 2026-05-25 → 2026-06-08)

| Gap | Tier | 落地动作 |
|---|---|---|
| **G7** | T1 | 新 `fixture-regen.yml` — 在 PR 即触发，TS 端补 regen 对照（与 Py 已有 `generate_vectors.py` 对齐） |
| **G5** | T4 | `reproducible-build.yml` 改 matrix `runs-on: [ubuntu-latest, macos-latest]`，两 runner 独立 build → 上传 artifact → 第三 job 下载比对 SHA-256 |
| **G4** | T4 | `sign-release.yml` 加 `cosign attest --predicate slsa-provenance.json --y --rekor-url=https://rekor.sigstore.dev` 步骤，发布 Rekor UUID |
| **G6** | T3 | `nightly.yml` 加 `mutmut run --paths-to-mutate sdk/python/src/attestplane/evidence/,sdk/python/src/attestplane/protocol/`；TS 端用 Stryker；advisory only |

### Sprint-3 (W4, 2026-06-08 → 2026-06-15) — 框架治理

- ci.yml 拆分为 `tier0-invariants.yml` + `tier1-fast.yml`（不阻塞老 ci.yml，灰度迁移）
- sdk-python.yml + sdk-typescript.yml 拆 T1 单机快速 + T2 全矩阵
- 文档：在 README 增 "CI 五层框架" 一小节 + 在 `docs/adr/` 新建 ADR-0015 *CI tiering for AP-EVD substrate integrity*

## 7. 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| R1: T2 矩阵 15min 预算紧张 | GHA cache + uv + npm + shard | cross-SDK round-trip 降级到 nightly |
| R2: mutation testing 噪音/不稳定 | 仅 `evidence/` + `protocol/` 子集 + advisory | 转为月度报告 |
| R3: SLSA L3 工具链迭代快 | 锁 action 版本 + 每季度 review | 降级到 SLSA L2 + 手工 cosign |
| R4: ADR frozen-block 误伤合法编辑 | 显式 `<!-- frozen-block -->` 标注，gate 只锁该区间 | git revert + 在 ADR 内开新区间 |

## 8. 战略锚定（为什么这样设计）

- **T0 invariant < 30s**：substrate 字节漂移会击穿所有下游 consumer，必须秒级即死，是 substrate 的生死线。
- **T2 cross-SDK round-trip**：Py + TS 双语言 substrate 的最大风险是单语言 silently diverge；round-trip 是唯一闭环证据。
- **T4 SLSA L3 + Rekor**：EU AI Act / ISO 42001 / Big 4 看的就是 provenance + transparency log，是 **P1 国际可信度的核心信号**。
- **ADR frozen-block gate**：11 篇 Accepted ADR 是治理资产；CI 锁住 = 治理纪律物化进代码，审计端"治理可信度"信号极强。
- **无 coverage 门禁对外**：避免落入 "Twitter marketing numbers" 陷阱，保持工程纪律可信度。

## 9. 参考引用

### ADR 引用

- ADR-0001 Apache-2.0 license
- ADR-0002 substrate data model
- ADR-0003 RFC-3161 anchoring (← T3 nightly-anchor)
- ADR-0009 AIOS absorption boundary (← T0 `check-policy.sh` INV-NEW-3/3b)
- **ADR-0014 v2 AP-EVD/1.0 conformance** (← T0 G2 / T2 G1 / T4 G5 核心依赖)

### 战略 memory 引用

- `project_attestplane_strategic_narrative_v2.md` — P1 不强收原则 / OSS 国际信誉建设 KPI
- `feedback_attestplane_aios_boundary.md` — T0 `check-policy.sh` INV-NEW-3 硬边界

### 外部标准

- in-toto / SLSA Level 3 — <https://slsa.dev/spec/v1.0/levels>
- Sigstore Rekor — <https://docs.sigstore.dev/logging/overview/>
- CycloneDX SBOM — <https://cyclonedx.org/>
- OpenSSF Scorecard — <https://github.com/ossf/scorecard>
- EU AI Act + Omnibus 2026-05-07（Annex III 推至 2027-12-02）

---

## 10. 待 founder 决策点

1. **Sprint-1 三项是否本周启动？**（G2 + G3 + G1，预估 3.5-4.5 天工作量）
2. **ADR frozen-block 标记方案：HTML 注释 vs YAML frontmatter 字段？**
3. **G4 Rekor 上传是否绑定 `v0.0.2-alpha` release，还是从 `v0.1.0` 起？**
4. **G6 mutation testing 工具选型：mutmut + Stryker，还是统一用 cosmic-ray？**

---

*本文档为 2026-05-18 CI 框架设计稿，作者 Claude Opus 4.7（1M context），架构审查由 opus-architect agent 完成。*
