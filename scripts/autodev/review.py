# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""autodev-train Stage 2: AI review script called by review-autodev-pr.yml."""
import json
import os
import urllib.request

api_key = os.environ["DEEPSEEK_API_KEY"]
issue_body = os.environ.get("ISSUE_BODY", "（无关联 Issue）")

with open("/tmp/autodev_pr.diff") as f:
    diff = f.read()

if len(diff) > 40_000:
    diff = diff[:40_000] + "\n\n[... diff truncated at 40 000 chars ...]"

fence = chr(96) * 3
prompt = (
    "你是 Attestplane 项目的自动化代码审查员。\n\n"
    "## 任务来源（planned-task Issue 描述）\n"
    + issue_body
    + "\n\n"
    "## PR Diff\n"
    + fence + "diff\n"
    + diff + "\n"
    + fence + "\n\n"
    "## 审查标准（逐项检查）\n"
    "1. **实现完整性** — 代码是否覆盖了 Issue 中所有验收标准？\n"
    "2. **REUSE 合规** — 新增文件是否包含 SPDX-License-Identifier 和 SPDX-FileCopyrightText 头部？\n"
    "3. **代码正确性** — 逻辑是否正确，有无明显 bug 或边界条件遗漏？\n"
    "4. **安全性** — 无硬编码密钥，无命令注入，无路径穿越。\n"
    "5. **项目规范** — 未修改 .github/workflows/、scripts/release/、CHANGELOG.md。\n\n"
    "## 输出格式（严格遵守）\n"
    "第一行必须且只能是以下两个词之一（不加任何标点或空格）：\n"
    "APPROVE\n"
    "或\n"
    "REQUEST_CHANGES\n\n"
    "第二行起输出详细审查说明（中文），通过项用 ✅，不通过项用 ❌ 并给出修复建议。"
)

payload = json.dumps({
    "model": "deepseek-v4-pro",
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 2048,
}).encode()

req = urllib.request.Request(
    "https://api.deepseek.com/v1/chat/completions",
    data=payload,
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
)

try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
        content = result["choices"][0]["message"]["content"].strip()
except Exception as exc:
    content = f"REQUEST_CHANGES\n\n❌ AI review API 调用失败: {exc}\n\n请重新运行 review 工作流或人工审查。"

with open("/tmp/review_output.txt", "w") as f:
    f.write(content)

first_line = content.splitlines()[0].strip()
decision = first_line if first_line in ("APPROVE", "REQUEST_CHANGES") else "REQUEST_CHANGES"
print(f"DECISION={decision}")
