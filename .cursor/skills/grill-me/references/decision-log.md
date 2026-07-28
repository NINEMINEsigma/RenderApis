# 决策日志格式

决策日志是 `grill-me` 会话产生的持久产物。它以下游 skill（`to-prd`、`to-issues`）可直接消费的格式，捕获每一个已解决决策、其上下文及其下游影响。

## 文件位置

保存为项目 `docs/` 目录下的 `decision-log.md`（如果没有 `docs/` 则保存在项目根目录）。

## 模板

```markdown
# Decision Log — <会话标题>

**Date**: YYYY-MM-DD
**Topic**: <本次质询主题的简短描述>
**Depth**: light | medium | deep
**Status**: complete | partial（注明哪些分支仍开放）

---

## Decisions

### D1: <决策标题>

**Status**: [RESOLVED] | [DEFERRED] | [RISKY]
**Question**: <当时提出的精确问题>
**Answer**: <达成一致的答案>
**Trade-off accepted**: <用户接受的成本/风险/约束>
**Local evidence**: <代码库的发现，或“未发现”>
**External evidence**: <咨询的工程先例，或“未咨询”>
**Terms defined**: <本决策解决的任何词汇表术语>
**Downstream impact**: <哪些后续决策依赖于此>

---

## Risk Register

| ID | Risk | Severity | Mitigation | Owner |
|----|------|----------|------------|-------|
| R1 | <描述> | high/medium/low | <策略> | <负责人> |

---

## Terminology Updates

| Term | Definition | Alias/avoid |
|------|------------|-------------|
| <术语> | <一句话定义> | _Avoid_: <旧术语> |

---

## ADRs Created

- `docs/adr/XXXX-<slug>.md` — <标题>

---

## Open Questions (Deferred)

- <问题> — 推迟到 <触发条件>

---

## Handoff Notes

Recommended next step: `to-prd` | `to-issues` | `grill-me --light` | none
Key context for implementer: <下游 skill 需要了解的关键信息>
```

## 规则

- 每个决策分配稳定 ID（`D1`、`D2`、…），供下游引用
- 保留精确的问题和答案，而不是摘要——摘要会丢失细微差别
- 显式记录权衡——这是最重要的字段
- 标注哪些决策有下游依赖——这形成树状结构
- 风险与决策分离——决策可以正确但仍然有风险
- 推迟的决策必须有触发条件，而不是简单的“以后再说”
