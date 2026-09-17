# Blog topic backlog（滚动选题）

> 单一事实源。由 **选题 Scout** 持续补充；**写稿 Writer** 只消费 `ready`；**审阅 Reviewer** 更新状态；**协调 Coordinator** 仅在审过之后标 `published` 并推送。  
> 准入门槛见 `docs/skills/agent_blog_writing.md` §2。  
> 本文件会不断变长/改状态——**不是**写死在规范里的固定菜单。

## 状态说明

`idea` → `ready` → `writing` → `in_review` → `published` | `rejected` | `parked`

优先级：`P0` > `P1` > `P2`

---

## Queue

### [published] 2026-09-15 | P0 | trajectory-eval-false-green
- **工作标题：** Trajectory Eval：答对了为什么还是假绿
- **失败面：** 只测 final answer，漏掉乱调工具 / 空转重试
- **为何够深：** 需要 trace 级指标与「可接受路径多样性」vs 过严序列断言
- **拟用案例 / 对照：** 同一任务两条轨迹，答案相同、成本与工具调用不同
- **相关已发文：** posts/mcp_tool_design_valid_but_wrong.md（工具面）；本文接评估面
- **参考线索：** LangChain agent evals；Langfuse trajectory；Confident AI agent eval 2026
- **已发文：** posts/trajectory_eval_false_green.md
- **备注：** Reviewer approved; Alice 批准 push 2026-09-15。系列下一坑：agent-write-idempotency

### [published] 2026-09-16 | P0 | agent-write-idempotency
- **工作标题：** Agent 写操作的幂等：超时之后凭什么敢重试
- **失败面：** timeout 后二次 create 导致双写
- **为何够深：** idempotency key、错误码分支、与 MCP annotations 的关系
- **拟用案例 / 对照：** create_order 超时 vs 带 key 的安全重试
- **相关已发文：** mcp_tool_design_valid_but_wrong.md 现象 C
- **参考线索：** MCP tool annotations；分布式系统幂等惯例
- **已发文：** posts/agent_write_idempotency.md
- **备注：** Reviewer approved; Alice 批准 push 2026-09-16。系列下一坑：long-horizon-decisive-error

### [published] 2026-09-17 | P1 | long-horizon-decisive-error
- **工作标题：** 长程 Agent：第一个错 vs 决定性错误
- **失败面：** 步数拉长后错误级联；日志上的「第一个异常」或「最后失败动作」≠ 决定性步；修错归因点救不了终局
- **为何够深：** 需要轨迹归因协议（反事实可修复性 / 依赖分型 / commitment-point），而非再讲 plan-and-execute；对照 Who&When / FALAT / HORIZON History Error Accumulation
- **拟用案例 / 对照：**
  1. **HORIZON History Error Accumulation（DB）**：早期中间表漏 `is_deleted = false`，下游分析全部复用 → 上游小错放大为系统性虚高结果；OS：静默失败命令被当成功，依赖命令继续执行
  2. **Who&When 实验对照**：decisive step =「最早、修正后可使失败→成功」的一步；但 step-by-step（停在第一个局部错）与 all-at-once 在 agent/step 准确率上反向权衡；最佳方法 agent≈53.5%、step≈14.2%——说明「找第一个错」启发式不可用
  3. **归因角色对照表（写稿用）**：Chronological first / Terminal symptom / Butterfly early ablation / Counterfactual-decisive（Who&When·FALAT）/ Point-of-Commitment latest rescue step（Causal Agent Replay）
- **相关已发文：** posts/mcp_tool_design_valid_but_wrong.md（工具 schema 合法但错——不同层）；与 ready `trajectory-eval-false-green`（只评终答假绿）、`agent-write-idempotency`（超时双写）不重叠：本文是过程归因层
- **参考线索：**
  - https://arxiv.org/abs/2604.11978 — HORIZON；History Error Accumulation + early planning 级联；3100+ trajectories
  - https://xwang2775.github.io/horizon-leaderboard/ — 7 类失败 taxonomy + LLM-judge 归因 prompt
  - https://arxiv.org/abs/2505.00212 / https://ag2ai.github.io/Agents_Failure_Attribution/ — Who&When；decisive error 形式化 + 三种归因方法权衡
  - https://arxiv.org/abs/2606.00765 — FALAT：error-introducing vs propagation；反事实充分性；Root_Cause/Propagation/Symptom/Contributing
  - https://arxiv.org/abs/2606.08275 — Causal Agent Replay / Point-of-Commitment：最早高归因常是蝴蝶效应，真正承诺点是「仍可救援的最晚一步」
  - https://arxiv.org/abs/2608.06909 — Long-Horizon Agent Trajectory Attribution；primary vs attribution chain；long-range 更难
  - https://arxiv.org/abs/2609.06783 — AURA-Eval（次要）：安全关键决策点，非任务级联归因
- **已发文：** posts/long_horizon_decisive_error.md
- **备注：** Reviewer approved; Alice 批准 push 2026-09-17。系列下一坑：durable-agent-execution

### [ready] 2026-09-15 | P1 | durable-agent-execution
- **工作标题：** 长跑 Agent 挂了：Checkpoint 不等于 Durable Execution
- **失败面：** 以为「有 checkpointer / 能 resume」就抗杀进程；HITL 审批在内存里等 → 宕机丢门控或恢复后重复副作用（双发邮件 / 双扣款 / 审计日志翻倍）
- **为何够深：** 拆清三层边界——(1) 图状态快照（super-step / node boundary）vs (2) 事件历史回放（Workflow Event History / Activity 结果落盘）vs (3) 工具层幂等键；LangGraph 官方明示 resume 从**含 interrupt 的节点开头重跑**，`durability=exit|async` 与 InMemorySaver 的恢复窗口不同；Temporal Approval 用 Signal + 零算力等待，不占进程。不是「怎么写 Temporal Hello World」
- **拟用案例 / 对照：**
  1. **误判演示：** Postgres checkpointer + 手动 restart「看起来活了」→ 节点中途已副作用未返回 → resume 整节点重入 → 二次 charge/email（边界粒度坑）
  2. **HITL 重跑：** `interrupt()` 前 `create_audit_log` / 发通知 → 审批回来节点从头跑 → 官方文档点名的重复副作用（对照：副作用放到 interrupt 后或独立节点 / `@task`）
  3. **丢审批等待：** `while not approved: sleep` 或进程内 flag → redeploy / `kill -9` → 门控蒸发（重跑危险动作或工作蒸发无人知）；对照 Temporal Signal wait / 事件源 `ToolApprovalRequired` 落盘后再停工
  4. **对照表（写稿用）：** 恢复粒度（节点边界 vs Activity）| 副作用去重谁负责 | 并发 resume 同 `thread_id` | 多日 HITL 是否占 Worker | 需要的确定性约束
- **相关已发文：** posts/mcp_tool_design_valid_but_wrong.md（工具面）；ready `agent-write-idempotency`（超时双写 / idempotency key——**相关但不同层**：那是 MCP 重试语义；本文是进程死亡 + 工作流历史 vs 框架内 checkpoint）；ready `trajectory-eval-false-green` / `long-horizon-decisive-error`（评估与归因，不重叠）
- **参考线索：**
  - https://docs.temporal.io/ai — Temporal Durable AI / Approval & Entity 模式入口
  - https://docs.temporal.io/design-patterns/approval — Signal + wait_condition；等待不占算力
  - https://docs.temporal.io/ai-cookbook/human-in-the-loop-python — HITL AI agent cookbook
  - https://docs.langchain.com/oss/python/langgraph/interrupts — resume 从节点开头重跑；副作用须幂等或放 interrupt 后
  - https://docs.langchain.com/oss/python/langgraph/checkpointers — durability `exit|async|sync`；`exit` 无中途崩溃恢复
  - https://dreaming.press/posts/langgraph-checkpointing-vs-temporal-durable-execution.html — Checkpoint ≠ Durable Execution 对照表
  - https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows — 检查点不负责崩溃检测/工人协调/副作用去重
  - https://render.com/articles/human-in-the-loop-without-the-hacks-pausing-an-agent-mid-run-for-approval-workfl — 内存等待三失败面；resume-as-restart
  - https://jamjet.dev/blog/approvals-that-survive-kill-9/ — 审批状态必须事件化，否则 kill -9 丢门控
  - https://zylos.ai/research/2026-04-24-durable-execution-agent-runtimes/ — 会话记忆 ≠ durable execution；journal + 故意 crash 测试
  - https://learn.temporal.io/tutorials/ai/durable-ai-agent/ — Activity 结果进 Event History（机制引用，勿写成教程正文）
- **备注：** Gate PASS。写稿禁令：Temporal 入门教程、框架选购清单。优先用 LangGraph 官方 interrupt 重入规则 + durability 模式作「看起来合理的 BAD」；Temporal/事件源作对照修复；结尾 checklist 指向「崩溃注入点」。与 idempotency 文交叉引用一句即可，勿合并成一篇。

### [idea] 2026-09-15 | P2 | mcp-progressive-disclosure
- **工作标题：** 工具一多就选错：渐进发现 vs 一次灌进全部 MCP
- **失败面：** context bloat → 错工具 → 重试再污染（当前仍等于范文 Confusion+Bloat）
- **为何够深：** 尚未过门槛——需要 Host discovery 层失败面（search recall miss / taxonomy skip / 中途注入打断 prompt cache），而非再讲 dump-all vs lazy
- **拟用案例 / 对照：** 待重框：retrieval@k vs selection accuracy；defer_loading / catalog→inspect→execute；非 V1–V4 复述
- **相关已发文：** posts/mcp_tool_design_valid_but_wrong.md（已含 V4 get_taxonomy + Tool Search 数字）
- **参考线索：**
  - https://www.anthropic.com/engineering/advanced-tool-use — Tool Search ~77K→8.7K；Opus 4 49%→74%
  - https://www.anthropic.com/engineering/code-execution-with-mcp — filesystem disclosure 150K→2K
  - https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool — defer_loading；≥10 tools / >10K def tokens
  - https://aws.amazon.com/blogs/machine-learning/mcp-tool-design-practical-approaches-and-tradeoffs/ — V4 lazy get_taxonomy（范文已用）
  - https://modelcontextprotocol.io/docs/2024-11-05/develop/clients/client-best-practices — Catalog→Inspect→Execute；mid-turn tools 变数组打断 cache
- **备注：** Gate FAIL for ready — 失败面仍 = Confusion+Bloat / V4 已在范文。保持 idea。升 ready 条件：重框为 discovery-miss / runtime disclosure（recall miss、taxonomy skip、cache break），并有 retrieval@k 对照。不强行升。

### [published] 2026-09-15 | P0 | mcp-valid-but-wrong
- **工作标题：** MCP 工具设计：合法但错误的调用
- **失败面：** well-formed wrong
- **已发文：** posts/mcp_tool_design_valid_but_wrong.md
- **备注：** 标杆范文

---

## Scout 工作日志（可选，追加在下方）

<!-- Scout 每次补充选题后可在此留一行日期与摘要 -->

- 2026-09-15 Scout: upgraded `long-horizon-decisive-error` idea→ready (HORIZON / Who&When / FALAT / Point-of-Commitment); AURA-Eval secondary.
- 2026-09-15 Scout: upgraded `durable-agent-execution` idea→ready (checkpoint ≠ durable execution; LangGraph interrupt reentry + Temporal Signal HITL); distinct from agent-write-idempotency.
- 2026-09-15 Coordinator: published `trajectory-eval-false-green` → posts/trajectory_eval_false_green.md (Alice 批准 push).
- 2026-09-15 Scout: kept `mcp-progressive-disclosure` as idea (gate FAIL — duplicates published Confusion+Bloat; wait for discovery-layer pit).
- 2026-09-16 Coordinator: published `agent-write-idempotency` → posts/agent_write_idempotency.md (Alice 批准 push).
- 2026-09-17 Coordinator: published `long-horizon-decisive-error` → posts/long_horizon_decisive_error.md (Alice 批准 push).
