# 下游 Skill — 概念规范

本文档定义了消费 `grill-me` 输出的规划中的下游 skill。这些 skill **尚未实现**；此处作为未来开发的契约。

## 概览

```
grill-me → decision-log.md → [to-prd | to-issues | grill-me --light]
```

决策日志是通用的交接产物。每个下游 skill 读取它并生成不同的输出格式。

---

## to-prd（规划中）

**目的**：将已解决的决策日志转换为产品需求文档。

**输入**：关键决策均标记为 [RESOLVED] 或 [RISKY] 的 `decision-log.md`。

**输出**：遵循标准模板的 `prd.md`。

**流程**：
1. 读取 decision-log.md 并提取所有决策
2. 按功能域分组（例如：认证、数据模型、API）
3. 对每组编写：
   - **概述**：该区域做什么、为什么
   - **需求**：从决策推导出的功能需求
   - **决策**：做出的具体选择及权衡
   - **开放问题**：影响该区域的任何 [DEFERRED] 决策
   - **风险**：风险登记中的相关条目
4. 包含决策日志中的术语词汇表
5. 添加“Out of Scope”章节，列出明确推迟的内容

**触发**：用户说“convert this to PRD”或决策日志的交接建议推荐使用 `to-prd`。

---

## to-issues（规划中）

**目的**：将已解决的决策日志拆分为可执行的 GitHub/GitLab issue。

**输入**：关键决策均标记为 [RESOLVED] 或 [RISKY] 的 `decision-log.md`。

**输出**：一组 issue 文件或直接通过 API 创建的 issue。

**流程**：
1. 读取 decision-log.md 并构建决策树
2. 识别叶子决策（无下游依赖）—— 这些成为实现任务
3. 将相关叶子决策分组为 epic
4. 对每个 issue：
   - 标题：以行动为导向（例如 "Implement idempotency keys for PaymentIntent"）
   - 描述：链接到父决策，包含权衡上下文
   - 标签：从决策域和风险等级推导
   - 依赖：引用必须先解决的上游决策
5. 创建按依赖顺序排列的“实现顺序”章节

**触发**：用户说“break this into issues”或决策日志的交接建议推荐使用 `to-issues`。

---

## grill-me --light

**目的**：针对决策子集运行更短的后续会话。

**输入**：包含部分 [OPEN] 或 [DEFERRED] 决策的现有 `decision-log.md`。

**流程**：
1. 读取现有决策日志
2. 识别开放边界（[OPEN] 决策及其依赖）
3. 运行压缩版质询会话（轻度深度：3–7 个问题）
4. 就地更新同一个 decision-log.md

**触发**：用户说“follow up on the deferred decisions”或“grill me on the remaining open questions”。

---

## 决策日志作为通用接口

关键设计原则：决策日志是 skill 之间的**单一真相源**。

| Skill | 读取 | 产出 |
|-------|-------|----------|
| grill-me | 用户输入、代码库、外部证据 | decision-log.md |
| to-prd | decision-log.md | prd.md |
| to-issues | decision-log.md | issues/ |
| grill-me --light | decision-log.md | 更新的 decision-log.md |

没有 skill 直接与其他 skill 通信。所有通信都通过决策日志进行。这让每个 skill 可以独立测试和替换。
