# Contributing to Attestplane

**Languages:** [English](CONTRIBUTING.md) | [中文](CONTRIBUTING_zh.md)

Attestplane 是面向 AI Agent 的 **Open Trust Substrate**——一个以密码学审计链为核心的合规基础层，
覆盖 EU AI Act / NIST AI RMF / ISO 42001 / SOC 2 框架映射。本项目采用 Apache 2.0 许可，
contributor 协议为 DCO（Developer Certificate of Origin），欢迎任何形式的实质性贡献。
项目治理与商标使用规则分别见 [`GOVERNANCE.md`](GOVERNANCE.md) 与 [`TRADEMARK.md`](TRADEMARK.md)。

---

## 1. DCO Sign-off Requirement（签名要求）

本项目使用 **Developer Certificate of Origin 1.1**（DCO），而非 CLA。
每一条 commit 必须携带 sign-off 行，表明你已阅读并同意 [DCO.txt](DCO.txt) 中的 1.1 版条款。

```bash
git commit -s -m "feat(sdk/python): add JCS canonicalization helper"
# -s 自动追加：Signed-off-by: Your Name <you@example.com>
```

若你忘记 sign-off，可以用以下命令补签最近 N 条 commit：

```bash
git rebase HEAD~N --signoff
```

**提交 PR 前请确认每一条 commit 均有 `Signed-off-by:` 行；无 sign-off 的 PR 不会被 merge。**

DCO 全文见仓库根目录 [`DCO.txt`](DCO.txt)（即 DCO 1.1 标准文本）。

---

## 2. 本地开发环境（Local Dev Setup）

### 前置依赖

| 工具 | 最低版本 |
| ---- | -------- |
| Python | 3.11+ |
| Node.js + npm | 20+ |

### 步骤

```bash
# 1. 克隆仓库
git clone https://github.com/attestplane/attestplane.git
cd attestplane

# 2. Python SDK
pip install -e "sdk/python[dev]"
pytest sdk/python/

# 3. TypeScript SDK（FastAPI / Express / NestJS helper）
cd sdk/typescript && npm install && npm test
```

完整的 runbook（数据库、TSA sidecar、本地 Rekor 实例）将在 `docs/runbooks/LOCAL_DEV.md` 提供（M5 前补齐）。

---

## 3. PR 工作流（PR Workflow）

### Branch 命名

```
feature/<short-description>    # 新功能
fix/<short-description>        # bug 修复
docs/<short-description>       # 文档变更
refactor/<short-description>   # 重构（不改行为）
test/<short-description>       # 纯测试补充
```

示例：`feature/rfc3161-anchor-retry`、`fix/blake3-chain-off-by-one`。

### Conventional Commits

强制使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
Signed-off-by: Your Name <you@example.com>
```

常用 type：`feat` / `fix` / `test` / `docs` / `refactor` / `chore` / `perf`。  
scope 对应 SDK 或包名，例如 `feat(sdk/python)`、`fix(sdk/typescript)`、`docs(adr)`。

### 开发节奏

遵循 **红→绿→重构→commit** 的 TDD 节奏：

1. **红**：先写失败的测试，明确行为契约。
2. **绿**：写最小实现让测试通过。
3. **重构**：清理代码，保持测试绿。
4. **commit**：每个逻辑单元一条 commit，一次记录完整的"红→绿→重构"单元。

保持 PR 小而聚焦——单个 PR 只做一件事，便于 review 和 bisect。

---

## 4. PR Checklist（提交前自查）

- [ ] `pytest sdk/python/` 全绿
- [ ] `npm test`（typescript SDK）全绿
- [ ] 受影响的文档已同步更新（ADR / API doc / changelog）
- [ ] 新 public API / 状态转换 / 框架映射均有对应测试覆盖
- [ ] `CHANGELOG.md` 已写入对应条目
- [ ] Breaking change 已在 commit footer 标注 `BREAKING CHANGE:` 并在 PR description 说明迁移路径
- [ ] **每一条 commit 均有 DCO `Signed-off-by:` 行**

---

## 5. Code Review 期望（Code Review Expectations）

- Review 聚焦**行为契约**：审计链不变量是否被满足，而不是风格偏好。
- 任何 **load-bearing 架构决定**（新框架映射、hash chain 算法变更、TSA 集成方式、安全边界调整）
  必须附带 ADR（Architecture Decision Record），放入 [`docs/adr/`](docs/adr/README.md)，遵循 [`docs/adr/0000-template.md`](docs/adr/0000-template.md) 模板。
  没有对应 ADR 的 load-bearing PR 不会被 merge。
- Review 意见用具体的代码行引用，不要只写"这里不对"。
- ADR 格式参考目录内已有文件；ADR 编号递增，不可跳号。

---

## 6. 报告 Bug（Reporting Bugs）

**一般 bug**：在 [GitHub Issues](https://github.com/attestplane/attestplane/issues) 提交，请附上：

- 最小可复现的命令序列
- 期望行为 vs 实际行为
- 相关日志 / panic 输出
- 受影响的 SDK / 框架映射

**安全漏洞**：**不要在公开 Issue 中披露。**  
请遵循 [`SECURITY.md`](SECURITY.md) 中的负责任披露流程，通过私有渠道报告。  
审计链伪造、hash 碰撞、RFC-3161 anchor 绕过属于高严重度漏洞，必须私下报告。

---

## 7. License Grant（许可授权声明）

本项目采用 **Apache License 2.0**，见 [`LICENSE`](LICENSE)。

向本仓库提交 contribution 即表示：

1. 你已阅读并同意 [`DCO.txt`](DCO.txt) 中 Developer Certificate of Origin 1.1 的全部条款；
2. 你的贡献在 Apache License 2.0 下对外发布；版权归你本人保留，Attestplane Pte. Ltd.（Singapore, in formation as of 2026-05-17）与所有其他下游接受者均依 Apache 2.0 接受你的贡献；本项目不要求 contributor 向任何公司转让或额外授权版权（这是 DCO 与 CLA 的关键区别）；
3. 你的 commit 上的 `Signed-off-by:` 行是上述 DCO attestation 的书面证明。

如有任何问题，请联系 [contributors@attestplane.com](mailto:contributors@attestplane.com)。

---

## 8. Code of Conduct（行为准则）

本项目遵守 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。
所有 contributor、maintainer 及社区成员均须遵守其中的行为标准。
