# 触发关键词与激活模式

本文档为支持基于关键词或模式激活 skill 的 agent 平台提供结构化触发定义。

## 主要触发词（高置信度）

以下短语应始终激活 `grill-me`：

| 模式 | 示例用户输入 |
|---------|-------------------|
| `grill me` | "grill me on this plan" |
| `grill-me` | "run grill-me on this design" |
| `grill me pro` | "use grill-me" |
| `interrogate` + `plan\|design\|architecture` | "interrogate this architecture" |
| `challenge my` + `design\|plan\|approach` | "challenge my design" |
| `stress test` + `plan\|design\|architecture` | "stress test this plan" |
| `帮我审视` | "帮我审视一下这个架构" |
| `先别写代码` + `厘清\|明确\|讨论` | "先别写代码，先帮我把需求厘清" |
| `拷问我` | "拷问我这个方案" |

## 次要触发词（依赖上下文）

当上下文涉及规划或设计决策时，以下短语应激活 `grill-me`：

| 模式 | 上下文线索 |
|---------|-------------|
| `设计` + `方案\|架构\|数据库\|API` | "我想设计一个支付系统的API" |
| `plan` + `architecture\|design\|refactor` | "plan this refactor" |
| `decide` + `technology\|framework\|database` | "decide which database to use" |
| `compare` + `options\|approaches\|solutions` | "compare these two approaches" |
| `trade-off` / `tradeoff` | "what are the trade-offs here?" |
| `assumptions` | "what assumptions am I making?" |

## 否定触发词（不应激活）

| 模式 | 原因 |
|---------|---------|
| `grill`（烹饪语境） | "how to grill steak" — 烹饪，非规划 |
| `interrogate`（数据语境） | "interrogate this dataset" — 数据分析，非设计评审 |
| 单独 `plan`（日程安排） | "plan my day" — 个人日程，非技术设计 |
| 单独 `design`（视觉） | "design a logo" — 视觉/平面设计，非架构 |
| `review code` | 代码评审与计划评审不同 |
| `debug` / `fix` | 故障排查不是规划 |

## 激活置信度等级

对于支持置信度评分的平台：

| 等级 | 条件 | 分数 |
|-------|-----------|-------|
| **Certain** | 精确提到 skill 名称（`grill-me`、`grill me pro`） | 1.0 |
| **High** | 主要触发词 + 设计/计划上下文 | 0.9 |
| **Medium** | 次要触发词 + 清晰规划上下文 | 0.7 |
| **Low** | 仅单个关键词匹配，无上下文 | 0.4 |
| **None** | 匹配否定触发词 | 0.0 |

## 平台特定说明

### evolve-agent
- 无自动触发系统
- 通过用户显式请求或 GENE/SOUL 集成激活
- 参见 README.md "安装到你的 Agent" 章节

### Claude Code / Claude.ai
- 使用 SKILL.md frontmatter 中的 `description` 字段触发
- 描述已针对覆盖度优化

### Cursor / Windsurf / Codex
- 通常使用 `.cursorrules` 或 skill 目录激活
- 将 SKILL.md 内容复制到 agent 的 rules/skills 目录

### 通用（system prompt 注入）
- 将 SKILL.md 主体注入 system prompt
- 触发词变得不重要 — skill 始终处于激活状态
