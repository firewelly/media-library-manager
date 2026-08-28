---
type: 参考资料
title: AGENTS.md 摘要
description: AGENTS.md 代理指令文件的摘要 — 针对在仓库中工作的 AI 代理的 OpenWiki 证据索引通知与指导。
tags: [documentation, agents]
openwiki:
  roles: [repository]
  source_paths: [AGENTS.md]
---

# AGENTS.md 摘要

`AGENTS.md` 是本仓库中为 AI 代理提供的简要指令文件。它包含：

1. **OpenWiki 通知**：本仓库包含一个生成的 `openwiki/` 证据索引。它是可选的即时上下文，并非必需的启动阅读材料。

2. **代理的核心原则：**
   - 将源代码和测试视为权威依据
   - 简报中的未知项属于验证盲区，而非自动产生的需求
   - 优先采用范围最窄的静默验证方式来证明行为已变更
   - 保留完整的失败输出

3. **OpenWiki 工作流**：定时执行的 OpenWiki GitHub Actions 工作流会刷新 wiki。除非明确要求，请勿手动编辑生成的页面；请优先更新源代码/文档，并让 OpenWiki 重新生成。

## 另请参阅

- [CLAUDE.md](CLAUDE.md) — 适用于 Claude 的等效指令文件
- [快速入门](../quickstart.md) — 仓库快速入门