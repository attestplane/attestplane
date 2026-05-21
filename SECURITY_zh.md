---
source: "[SECURITY.md](./SECURITY.md)"
source_sha: ff04817ec4405ca57c90998240c6ae09f8c1270c
translation_status: reviewed
translator: "@merchloubna70-dot"
reviewed_at: 2026-05-21
reviewed_by: native-speaker (AI-assisted, fluency + normative-equivalence sweep)
---

> **Source / 英文原文：** [SECURITY.md](./SECURITY.md) @ `ff04817e`

# 安全策略

**项目：** Attestplane — Open Trust Substrate for AI Agents（面向 AI 智能体的开放可信底座）
**维护实体：** Attestplane Pte. Ltd.（Singapore，截至 2026-05-17 处于设立中状态）
**联系方式：** security@attestplane.com
**GPG 密钥：** 将于 M5 W6（目标 2026-08-15）之前发布在 `https://attestplane.com/.well-known/security.txt`。

---

## 受支持的版本

| 版本范围 | 状态 | 说明 |
|---------------|--------|-------|
| 1.0.x（Pre-GA tag 线） | Pre-GA 支持 | 当前的活跃发布线。在 Pre-GA / GA 之前的稳定期内，安全修复优先发布在最新的 1.0.x tag 上。在 v1.0 GA 之前，不提供生产 SLA。 |
| 0.8.x | 不再支持 | 已被 1.0.x Pre-GA tag 线取代。请升级至最新的 1.0.x tag 以获取安全修复。 |
| 0.7.x-alpha 及更早的 alpha 系列 | 冻结的预发布版本 | 不接受新功能。仅在向后移植比升级更安全时才提供安全修复。 |
| 1.0 GA | 完整 SLA | 目标发布日期 2026-08-15。下文的响应时限自该版本起向前适用。 |
| Pre-alpha 快照 | 不支持 | 不提供修复。请升级至当前的 1.0.x Pre-GA tag 线。 |

不建议在生产环境中运行 beta 或 RC 版本。若运营方选择在生产环境
部署 Pre-GA / GA 之前的版本，其风险由其自行承担。

---

## 漏洞报告

**请勿就安全问题在 GitHub 公开提交 Issue。** 在修复方案发布之前进行公开披露，将会使所有用户面临风险。

| 通道 | 详情 |
|---------|---------|
| 邮件 | `security@attestplane.com` |
| GPG | 公钥待定；将于 M5 W6 之前发布在 `https://attestplane.com/.well-known/security.txt` |
| GitHub Security Advisories | 使用 Security 标签页中的 "Report a vulnerability" 按钮（私下披露） |

请在报告中提供：

- 对该漏洞及受影响组件的清晰描述。
- 复现步骤或最小化的概念验证（PoC）。
- 您对严重程度（Critical / High / Medium / Low）和可利用性的评估。
- 您是否计划公开发表；我们会与您协调披露时机。

---

## GPG 密钥（计划用于 v1.0 GA）

将在 **v1.0 GA 目标日期 2026-08-15** 当天或之前，发布一份用于
`security@attestplane.com` 的专用 GPG 密钥。在该日期之前，项目尚无
任何 GPG 密钥在流通；在通过下列渠道正式发布之前，不要信任任何自称是
`security@attestplane.com` 密钥的密钥材料。

**计划的发布渠道（GA 切版时三处一并发布）：**

- 本 `SECURITY.md` 文件（fingerprint 内嵌在下方占位区块内）。
- 项目主页 `https://attestplane.io`（安全页面）。
- MIT PGP 密钥服务器（`pgp.mit.edu`），可通过 `security@attestplane.com` UID 检索。

**Pre-GA / GA 之前的备选私密通道。** 在密钥发布之前，若报告人需要
一条传输层加密的通道，**可以**使用 **GitHub Security Advisories**
（本仓库 Security 标签页中的 "Report a vulnerability" 按钮）。
GitHub Security Advisories 提供具备 TLS-in-transit 机密性的私下披露
通道，是 Pre-GA / GA 之前对于不便以明文邮件提交敏感细节的报告人
所推荐的路径。

**Fingerprint 占位（<v1.0 GA 时填入>）：**

```
Primary fingerprint: <to be filled in at v1.0 GA cut, target 2026-08-15>
UID:                 Attestplane Security <security@attestplane.com>
Key type:            <to be filled in at v1.0 GA cut>
```

---

## 响应时限

| 节点 | 目标 |
|-----------|--------|
| 收件确认 | 7 天以内 |
| 初步分级与严重度评估 | 14 天以内 |
| 修复或可接受的缓解方案 — Critical | 30 天以内 |
| 修复或可接受的缓解方案 — High | 60 天以内 |
| 修复或可接受的缓解方案 — Medium / Low | 90 天以内 |

如果修复需要协同上游依赖，时限可能会被延长。我们会在原始时限内于披露线程中告知任何此类延期。

---

## 协调披露

我们默认采用 **90 天的禁止披露期（embargo）**，从最初报告获得确认之日起算。
在禁止披露期结束时（或在修复发布时，以两者中较早者为准），
报告人即可自由发表其研究成果。

- 除非报告人明确要求匿名，研究者将以姓名或 handle 在版本发布说明中获得致谢。
- 在公开发布安全公告之前，我们会向报告人分享公告草稿。
- 如果严重漏洞需要更短的禁止披露期，我们会本着善意进行协商。

---

## 范围

### 范围内

| 组件 | 描述 |
|-----------|-------------|
| 哈希链引擎 | 底座（Substrate）规范化与 SHA-256 哈希链完整性（参见 [ADR-0002](docs/adr/0002-substrate-data-model-and-hash-chain-v0.md)）；跨语言的字节级一致性 |
| RFC-3161 anchoring | 按 [ADR-0003](docs/adr/0003-tsa-rfc-3161-anchoring.md) 描述的时间戳机构（TSA）锚定（随 v0.1 / M5 发布） |
| Audit log API | JSON Auditor API — 查询、追加与校验端点（M5 发布面） |
| SDK helpers | FastAPI / Express / NestJS / Django 框架集成辅助库（M5 发布面） |
| 框架映射层 | EU AI Act / NIST AI RMF / ISO 42001 / SOC 2 断言映射 |
| Attestplane Cloud（M6+） | 托管预览版与生产云服务，上线后纳入 |
| CLI 与构建工具链 | `attestplane` CLI、构建管线脚本 |

### 范围外

| 领域 | 指引 |
|------|----------|
| 上游 LLM 模型对齐 | Attestplane 在协议层约束智能体行为；模型层的 jailbreak 超出我们的控制范围。 |
| 第三方依赖 | 请将 PostgreSQL、FastAPI、Python、Rust crates 等的漏洞向各自的上游维护方报告。 |
| 客户自建部署的配置错误 | 由运营方控制的基础设施（防火墙规则、密钥管理等）中的错误由运营方自行负责。详见下方《面向运营方的加固指引》。 |
| 物理基础设施与操作系统内核 | 请向您的托管服务商或 OS 厂商报告。 |

---

## 威胁类别

下列威胁类别针对 Attestplane 的可信底座模型。本清单取代任何先前 AIOS 时代的威胁分类法。

| ID | 威胁 | 严重程度 | 状态 |
|----|--------|----------|--------|
| AT-01 | **审计链篡改** — 攻击者修改或删除历史审计记录，以销毁智能体不当行为的证据。 | Critical | 0.x 版本中已实现哈希链完整性校验；RFC-3161 anchoring 提供外部时间戳证明。 |
| AT-02 | **重放攻击** — 一条合法的、已签名的审计事件或 attestation 以乱序方式被重放，伪造出具误导性的审计链。 | High | 链中已强制使用序号与时间戳；nonce 策略计划于 M5。 |
| AT-03 | **Lease / attestation 伪造** — 智能体或第三方伪造一条框架映射 attestation（例如，谎称满足 EU AI Act Article 13 合规）。 | Critical | 在数据摄入时校验 attestation 签名；计划在 M5 引入 SLSA L3 来源证明。 |
| AT-04 | **聚合投毒（M7 差分隐私）** — 客户端被操纵的输入污染了提交给监管机构的隐私保护聚合报告。 | High | 计划在 M7 C1 的客户端 DP 架构中缓解；并对输入施加边界校验。 |
| AT-05 | **供应链入侵** — 恶意或被入侵的依赖在底座的二进制或 SDK 中植入后门。 | Critical | Sigstore 签名 + SLSA L3 attestation + 48 小时依赖冷却策略（见《供应链安全态势》一节）。 |
| AT-06 | **商标 / 域名钓鱼** — 对抗性的软件包、域名或仓库假冒 `attestplane`，分发恶意工具。 | Medium | 请向 security@attestplane.com 报告；请通过官方仓库提供的 Sigstore bundle 校验发布版本。 |
| AT-07 | **未授权访问 Auditor API** — 未经身份验证或权限不足的调用者读取、写入或清除审计事件。 | High | 所有 Auditor API 端点均要求身份验证；并强制 append-only 的数据库授权（详见加固指引）。 |
| AT-08 | **公开声明漂移** — README、版本发布说明或营销文案声明了底座并不能支撑的能力（例如，"EU AI Act compliant"、"tamper-proof"、"production-ready"），从而使项目及其创始人承担误导性商业言论的法律风险或未来的执法压力。 | High | 所有公开声明均受 [`docs/policy/forbidden_claims.md`](docs/policy/forbidden_claims.md) 与 [`docs/policy/claims_policy.md`](docs/policy/claims_policy.md) 约束；CI policy-invariant 任务会扫描差异；PR 模板要求声明合规。 |

完整的攻击路径与检测信号将在 `docs/architecture/THREAT_MODEL.md` 中记录（目标 M5 W7）。

---

## 面向运营方的加固指引

下列步骤适用于自托管部署。这些是最低基线要求；生产环境的运营方应根据其风险画像增加额外控制。

1. **在接入网络之前替换默认凭据。** 用于本地开发的默认数据库凭据，必须在进入任何接入网络的部署之前轮换。请将密钥保存在密钥管理系统中（Vault、AWS Secrets Manager 或同等系统）；切勿将其放入提交至版本控制的环境文件中。

2. **对审计日志表强制 append-only 授权。** `audit_events` 表必须仅授予 `INSERT` 权限 — 不得授予 `UPDATE` 或 `DELETE`。请用以下语句校验授权：

   ```sql
   SELECT grantee, privilege_type
   FROM information_schema.role_table_grants
   WHERE table_name = 'audit_events';
   ```

   若该表上出现任何 `UPDATE` 或 `DELETE` 权限，即表明存在配置错误。

3. **不要将底座 API 直接暴露在公网。** 请把 Attestplane API 部署在私有网络边界之后，或置于带认证的反向代理 / API 网关之后。我们不支持任何无认证的公网可路由端点。

4. **为所有传输启用 TLS。** 智能体、Audit API 与 RFC-3161 TSA 端点之间的所有通信，必须在传输层加密。生产环境配置中应禁用 HTTP 明文回退。

5. **锁定并校验依赖校验和。** 请使用 lockfile（`poetry.lock`、`Cargo.lock`），并以已发布的哈希值进行校验。生产环境中不要使用浮动版本约束。

6. **定期运行依赖漏洞审计。**

   ```bash
   # Rust
   cargo audit
   # Python
   pip-audit
   ```

   请将上述检查集成进 CI，并将 High/Critical 等级的告警视为阻断项。

7. **在部署新版本之前校验 Sigstore 发布签名。** 自 M5 W4 起，所有发布物都会附带 Sigstore bundle。在将任何新版本发布到生产环境之前，请用 `cosign verify` 进行校验。

---

## 供应链安全态势

下表所列供应链控制为计划中或已启用状态。状态以 2026-05-17（M5 之前、alpha 阶段）为准。

| 控制项 | 目标 | 状态 |
|---------|--------|--------|
| Sigstore / cosign 发布签名 | M5 W4 | 计划中 |
| CycloneDX SBOM 生成（每次发布） | M5 W4 | 计划中 |
| SLSA Build Level 3 attestation | M5 W4 | 计划中 |
| 48 小时依赖冷却策略 | M5 W4 | 计划中 — 新引入的依赖必须在合并前 48 小时提出，以便供应链审查 |
| Dependabot 版本与安全告警 | 已启用 | 仓库中已开启 |
| CI 中固定的 lockfile | 已启用 | `Cargo.lock` 与 `poetry.lock` 已提交并在 CI 中校验 |
| 分支保护 + 必需 review | 已启用 | Main 分支要求合并前必须通过 PR 与 review |

48 小时依赖冷却策略是源自 v1.3 风险登记册（§6，供应链攻击缓解）的硬性要求。任何引入全新依赖的 PR，必须在合并之前至少保持开放 48 小时，以便维护者与社区进行 review。

SBOM 产物会与每一个 tag 化的发布版本一同发布，并使用项目的 Sigstore 身份进行签名。运行受监管 EU 部署的运营方，应根据其自身内部的 CRA / NIS2 文档要求保存 SBOM 记录。

---

## EU Cyber Resilience Act (CRA) 2027-12 合规筹备

EU Cyber Resilience Act 将于 **2027-12-11** 起生效。Attestplane 是一个由商业实体（Attestplane Pte. Ltd.）维护的开源项目。开源项目维护方与商业制造商在 CRA 下的义务区分，目前处于持续的法律观察之中。

| 检查点 | 目标日期 | 行动 |
|------------|-------------|--------|
| 法律立场评估（OSS steward 对比 commercial manufacturer 分类） | 2027-Q1 | 由创始人（China-licensed compliance lawyer）对 CRA recitals 与实施细则进行自我评估 |
| SBOM 自动生成管线上线 | M5 W4（2026） | 每次发布生成 CycloneDX SBOM |
| ENISA 上报管线筹备 | 2027-Q3 | 评估 ENISA 上报工具；起草内部 incident-to-report SOP |
| 漏洞披露文档与 CRA Article 14 对齐 | 2027-Q3 | 对照最终的 CRA 实施细则审查本 SECURITY.md |
| CRA 合规筹备完成 | 2027-12-11 之前 | 完成完整评估与所需的调整 |

运营方在受监管的 EU 环境中部署 Attestplane（DORA、NIS2、EU AI Act Article 12–17）时，应独立追踪 CRA 实施细则，并自行评估其作为产品制造者或进口商可能承担的义务。

---

## 荣誉墙 / Bug Bounty

本阶段（M5 之前的 alpha 阶段）暂无正式的金钱性 Bug Bounty 计划。提交了在范围内、且经核实有效漏洞的研究者将会：

- 在该修复的版本发布说明中以姓名或 handle 获得致谢（可选退出 — 请在报告中说明偏好）。
- 在 M5 阶段建立 `SECURITY_HALL_OF_FAME.md` 后，于该项目的安全荣誉墙获得致谢。

带有明确范围、奖励等级与 safe-harbour 条款的结构化 bounty 计划，计划在 **M9+（2027-Q2）** 推出。范围与奖励等级届时公布。

---

## 残余风险声明

Attestplane 明确承认下列残余风险无法在项目边界内被完全缓解：

- **上游 LLM 对齐失败。** 模型层的 jailbreak 以及涌现的智能体行为，超出 Attestplane 的控制范围。审计链记录的是智能体做了什么；它无法防止所有类别的模型层不当行为。
- **拥有数据库超级用户权限的内部威胁。** 技术控制（append-only 授权、哈希链、RFC-3161 anchoring）只能减小但无法消除来自高权限数据库管理员的风险。组织性控制 — 最小权限访问、schema 变更的双人复核（four-eyes）、以及将审计日志导出到独立存储 — 是必需的互补缓解。
- **PostgreSQL 0-day 漏洞。** Attestplane 依赖 PostgreSQL 进行审计日志持久化。未打补丁的 PG 0-day 超出本项目的控制；运营方在生产中应使用具备自动补丁能力的托管 PostgreSQL 服务。
- **客户自托管配置错误。** 在文档化加固基线之外部署 Attestplane 的运营方，自行承担其自身基础设施中配置错误的责任。这包括网络暴露、凭据管理与 TLS 配置。

---

> **翻译说明：** 本文件为 SECURITY.md 的中文译本，如与英文原版存在歧义，以英文原版为准。

*本文件最近一次审阅：2026-05-20。下次计划审阅：2027-Q1（CRA 法律立场检查点）。*
