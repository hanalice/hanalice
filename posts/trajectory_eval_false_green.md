---
title: Trajectory Eval：答对了为什么还是假绿
date: 2026-09-15
tags: Agent, Evaluation, Trajectory, Observability, Tool-Calling
description: 终答对了仍可能假绿：乱调工具、空转重试、成本爆炸。用轨迹级指标（tool correctness、step budget、禁区副作用）补上只评 outcome 的盲区。
---

## 1. 问题现象 (Problem Symptoms)

上一篇讲工具面：schema 绿灯、业务却错。评估面有对称的坑——**final answer 绿了，轨迹其实在空转**。

CI 只比最终字符串或一个 LLM-as-judge 的「答案对不对」。合并门打开，成本曲线、工具误用、重试风暴都还在生产里。这种绿灯叫 **false green（假绿）**：outcome 过了，path 没过。

### 现象 A：同一答案，两条轨迹

任务：「查 INV-1024 的可退税额，用一句话回复」。

| | Trajectory Good | Trajectory Bad |
| --- | --- | --- |
| 终答 | 「可退 128.40 EUR」 | 「可退 128.40 EUR」 |
| 工具序列 | `get_invoice` → `calc_refund` | `list_invoices` → `search_docs` → `get_invoice`（timeout）→ `get_invoice` → `calc_refund` → 再调一次 `search_docs` |
| 工具调用数 | 2 | 6 |
| 延迟 / token | ~1.8s / ~3k | ~14s / ~18k |
| final-answer eval | ✅ | ✅ |

答案相同，成本差一个数量级。只评终答，Bad 和 Good 一样绿。

### 现象 B：乱调工具，答案碰巧对

用户问退款政策。Agent 先调了 `update_ticket`（写操作），再 `get_policy`，最后从 policy 文本里抄出正确答案。终答判对；轨迹里多了一次不该发生的写。假绿掩盖了 **wrong tool / side-effect on the path**。

### 现象 C：空转重试被当成「努力」

上游 `get_inventory` 连续返回可行动的 `isError`（SKU 不存在）。Agent 改参数重试 5 次，最后靠另一条旁路工具碰巧拿到了库存结论。终答绿；trace 上是 **retry loop without progress**。没有 step budget / loop detector，这类轨迹永远进不了红灯。

```mermaid
flowchart LR
  A[只评 final answer] --> B[答案正确]
  B --> C[CI 绿灯]
  C --> D[漏掉: 错工具 / 空转 / 成本爆炸]
  D --> E[生产里才爆]
```

---

## 2. 根因分析 (Root Cause Analysis)

假绿不是「评测太严」，而是 **评估表面积（evaluation surface）选错了**：把 Agent 当成单轮 LLM——只看 input → final output——而 Agent 的失败大半发生在中间的 tool calls、retries、handoffs。

用三层诊断栈（Confident AI / DeepEval 与 Langfuse 的常见分法一致）：

| 层级 | 问什么 | 假绿时的误判 |
| --- | --- | --- |
| End-to-end（黑盒终态） | 任务有没有完成？ | 完成了 → 全绿；路径再烂也看不见 |
| Trajectory（玻璃盒路径） | 路径是否合理、够省、无禁区动作？ | **缺这一层就会假绿** |
| Component / span | 哪一次选工具、哪次参数、哪次检索坏了？ | 只有「坏了」没有「坏在哪」 |

根因可以收成两句：

1. **Outcome ≠ Path**：Task completion / answer match 不蕴含 tool correctness、step efficiency、无副作用。
2. **路径非唯一，但可接受集合有界**：同一任务允许多条合理轨迹（可接受路径多样性）；不等于「任意轨迹只要答案对都算过」。过严的序列断言会制造假红；过宽的终答断言会制造假绿。

| 失败形态 | 终答信号 | 轨迹信号 | 根因杠杆 |
| --- | --- | --- | --- |
| 乱调工具但答案碰巧对 | 绿 | wrong tool / 禁区写操作 | 工具正确性 + 禁区断言 |
| 空转重试后碰巧成功 | 绿 | 重复 span、无进度重试 | step budget / loop 检测 |
| 多查无关工具「凑答案」 | 绿 | 多余 tool calls、成本尖刺 | step efficiency + 成本阈值 |
| 合理换序（先 B 后 A） | 绿 | strict 序列红、unordered 绿 | 匹配模式选错 → 假红 |

---

## 3. 机制要点：评路径，不只评终点 (Mechanism)

### Trace 是评估的原料

没有结构化 trace（messages / tool calls / spans），trajectory eval 无处挂载。实践上至少要留下：

- 有序的 tool call 名与参数（可对敏感字段脱敏）
- 每步 latency、token、error / `isError`
- 可选：计划文本、子 Agent handoff

Langfuse 把 trajectory 拆成可判定的一半（step count、loop、required steps、budget）和需阅读的一半（LLM-as-a-judge / 人工看图）；Agent graph 的 Aggregated 视图能把 `retrieve_docs (3/3)` 和环边一眼标成病态路径。

### 匹配模式：多样性 vs 过严断言

LangChain `agentevals` 的 trajectory match 把「和参考轨迹比」收成四种模式——这正是「可接受路径多样性」的工程旋钮：

| `trajectory_match_mode` | 含义 | 适合 | 误用代价 |
| --- | --- | --- | --- |
| `strict` | 消息结构与工具调用顺序完全一致 | 合规前置（先查政策再授权） | 合理换序 → **假红** |
| `unordered` | 同一组工具，顺序不限 | 多路只读检索 | 仍要求集合一致 |
| `subset` | 实际 ⊆ 参考（不许多调） | 控 scope / 防乱调 | 漏掉「少调了关键步」 |
| `superset` | 实际 ⊇ 参考（允许多调） | 最小必做集 | 多调垃圾工具仍绿 → **假绿风险** |

经验法则：

- **安全 / 副作用边界**用 `subset` 或显式 denylist（禁止的写工具一次都不能出现）。
- **最小必做**用 `superset`（必须 `get_invoice`，允许一次无害的 `get_taxonomy`）。
- **顺序真正有业务约束**才上 `strict`；其余先 `unordered` 或 LLM judge。
- 参数是否逐字相等，用 `tool_args_match_mode` / overrides 单独放宽（时间戳、idempotency key 常要忽略或规范化）。

### 指标不要合成一个分数糊弄自己

Trajectory 不是一个魔法 score。生产里我们拆开看（名称跟 DeepEval / Confident AI 2026 指南对齐，便于对照实现）：

| 指标 | 抓什么 | 典型实现 |
| --- | --- | --- |
| Tool Correctness | 该调的调了、不该调的没调 | 确定性集合 / 多重集比较 |
| Argument Correctness | 参数语义对不对 | 规范化后比对或局部 judge |
| Step Efficiency | 有没有多余步、空转、回环 | budget、重复检测、judge |
| Task Completion | 目标是否达成 | 终态 / 轨迹级 judge |
| Cost & Latency | 路径的经济性 | 从 trace 聚合，设分位阈值 |

**假绿的操作定义**：Task Completion（或 answer match）= pass，且下列任一 = fail：Tool Correctness、禁区副作用、Step Efficiency / budget、成本分位。

---

## 4. BAD / GOOD：同一任务的评估设计 (BAD / GOOD)

任务仍是：「查 INV-1024 可退税额，一句话回复」。允许的只读路径：`get_invoice` → `calc_refund`；允许先 `get_taxonomy` 再查；禁止任何 `update_*` / `send_*`。

### BAD：只钉终答 + 过严金轨迹

```python
# ❌ 假绿 + 假红两头不讨好
def eval_refund_agent(run):
    # 1) 只看终答
    answer_ok = "128.40" in run.final_text  # Bad 轨迹也过

    # 2) 又用唯一金轨迹做 strict（合理换序直接挂）
    gold = ["get_invoice", "calc_refund"]
    traj_ok = run.tool_names == gold  # ["calc_refund","get_invoice"] → 假红
    # 空转重试、禁区写操作：完全没断言
    return answer_ok and traj_ok
```

问题：

- Bad 轨迹答案对 → `answer_ok` 绿（假绿）。
- Good 但先 `calc` 再被框架重排/或先拉 taxonomy → strict 红（假红）。
- `update_ticket` 混进路径 → 无人报警。

### GOOD：终态 + 有界路径集合 + 预算

```python
# ✅ outcome 与 path 拆开；多样性用集合约束，不用唯一序列神化
REQUIRED = {"get_invoice", "calc_refund"}
ALLOWED = REQUIRED | {"get_taxonomy"}  # 可接受路径多样性
FORBIDDEN = {"update_ticket", "update_invoice", "send_invoice"}
MAX_TOOL_CALLS = 4

def eval_refund_agent(run):
    tools = run.tool_names  # 有序列表；可含重复

    outcome = answer_match(run.final_text, expected_amount="128.40")

    tool_set = set(tools)
    required_ok = REQUIRED.issubset(tool_set)          # ~superset of required
    scope_ok = tool_set.issubset(ALLOWED)              # ~subset of allowed
    safety_ok = tool_set.isdisjoint(FORBIDDEN)
    budget_ok = len(tools) <= MAX_TOOL_CALLS
    no_loop = max(tools.count(t) for t in tool_set) <= 2

    path_ok = required_ok and scope_ok and safety_ok and budget_ok and no_loop
    return {
        "task_completion": outcome,
        "path_ok": path_ok,
        "pass": outcome and path_ok,  # 假绿定义：outcome∧¬path → fail
        "tool_calls": len(tools),
        "cost_tokens": run.total_tokens,
    }
```

对照现象 A：Good（2 步）过；Bad（6 步含无关检索与重复 get）在 budget / scope 挂掉——即使终答相同。

需要「先政策后动作」的合规步时，再对**那一段**加 `strict` 子序列，而不是整条轨迹全局 strict。更模糊的「是否在兜圈子」交给 `create_trajectory_llm_as_judge`（或等价 rubric），与确定性闸门串联：便宜的 code check 先筛，judge 抽检或只打可疑 trace。

---

## 5. 发版前清单 (Pre-Ship Checklist)

把评估面补齐再让 final-answer 门禁单独说了算：

**Instrumentation**

- [ ] 每条评测 run 都能拿到有序 tool call 列表（名 + 规范化参数）与 token / latency
- [ ] 写操作、外发副作用在 trace 上可识别（或 annotations + Server 侧事实一致）
- [ ] 失败重试保留原错误码 / `isError` 文案，避免「吞掉错误再假成功」

**Assertions（防假绿）**

- [ ] Task Completion / answer match **不能**单独作为合并门；必须与 path 门 AND
- [ ] 明确 REQUIRED / ALLOWED / FORBIDDEN 三类工具集合
- [ ] step budget 与「同工具无进度重复」上限
- [ ] 成本 / 延迟分位阈值（P95），防「答对但烧穿」

**Matching（防假红）**

- [ ] 仅在真实顺序约束处用 `strict`；默认 `unordered` / 集合约束 / LLM judge
- [ ] 参数比对做规范化（case、ID 格式、时间戳、idempotency key）
- [ ] 金轨迹是「可接受集合的生成器」，不是唯一圣经

**分层**

- [ ] CI：确定性 path 闸门 + 小样本终态
- [ ] 夜间 / pre-release：LLM trajectory judge + 成本回归
- [ ] 线上：采样 trace 跑 budget / forbidden tool；尖刺回灌数据集

---

## 6. 小结 (Takeaways)

假绿的本质是：**用单轮答案评估，去给多步 Agent 发通行证**。

- **Outcome ≠ Path**；答对仍可能乱调工具、空转重试、成本爆炸。
- **Trace 级指标**（tool correctness、step efficiency、budget、禁区副作用）才是破假绿的杠杆。
- **可接受路径多样性**要用 `unordered` / subset / superset / 集合约束表达；全局 `strict` 制造假红，单终答制造假绿。
- 和上一篇的关系：工具面把非法状态挤出 schema；评估面把「路径非法但答案合法」挤出合并门。

下一坑更偏写路径运行时：**Agent 写操作的幂等**——超时之后凭什么敢重试，如何避免双写（接现象 C 与工具 annotations 的边界）。

---

## 参考 (References)

1. LangChain Docs — [How to evaluate your agent with trajectory evaluations](https://docs.langchain.com/langsmith/trajectory-evals)（`agentevals`：`strict` / `unordered` / `subset` / `superset`；trajectory LLM-as-judge）。
2. LangChain — [Agent Evals](https://docs.langchain.com/oss/python/langchain/test/evals)；[`langchain-ai/agentevals`](https://github.com/langchain-ai/agentevals)。
3. Langfuse — [AI Agent Evaluation](https://langfuse.com/resources/engineering/ai-agent-evaluation)（trajectory / tool use / task completion；code evaluator 与 step budget）；[Code evaluator examples](https://langfuse.com/resources/engineering/code-evaluator-examples)（`tool_sequence` / `within_step_budget`）。
4. Confident AI — [LLM Agent Evaluation Metrics in 2026](https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide)（end-to-end / trajectory / component；Tool Correctness、Step Efficiency、Task Completion；答对仍可能路径失败）。
5. DeepEval — [AI Agent Evaluation](https://deepeval.com/guides/guides-ai-agent-evaluation)（trajectory vs end-to-end vs component；tracing 要求）。
