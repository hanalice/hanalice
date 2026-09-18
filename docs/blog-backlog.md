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

### [published] 2026-09-18 | P1 | durable-agent-execution
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
- **已发文：** posts/durable_agent_execution.md
- **备注：** Reviewer approved; Alice 批准 push 2026-09-18。下一可写：等 Scout 升 ready（agent-memory-poisoning 等 idea）。

### [ready] 2026-09-18 | P1 | mcp-progressive-disclosure
- **工作标题：** Host 渐进发现：工具「搜不到」≠「没这个能力」
- **失败面（Host discovery 层，非 Server schema）：** search recall miss → 模型断定「没这个能力」；Catalog→Inspect 跳过（未 inspect 就 invoke）；mid-turn 改 `tools` 数组打断 prompt cache；search/get/invoke 元工具混淆；`notifications/tools/list_changed` 后 Host 目录陈旧
- **为何够深（非科普）：** 范文讲 **Server 工具设计**（Confusion+Bloat、V1–V4/`get_taxonomy`）。本文推进到 **Host 运行时发现层**：lazy/Tool Search 已上线后，失败从「塞太多」变成「检索漏召回 / 缓存失活 / 元工具路由错」。对照 retrieval@k vs selection accuracy，而非再画 dump-all vs lazy 入门图
- **拟用案例 / 对照：**
  1. **Recall miss（「没这个能力」）**：工具存在于 catalog，BM25/regex 未命中 → 模型放弃或瞎调邻居工具。Stacklok@2792 tools：Tool Search 选择准确率 ~34% / 召回 ~48% vs hybrid ~94%/~98%（同模型 Claude Sonnet 4.5）——根因是检索没把正确工具送进候选集
  2. **Inspect skip**：Catalog→Inspect→Execute 中跳过 Inspect，拿短摘要直接 invoke → schema/参数错；对照「先 get 全定义再 call」
  3. **Prompt-cache break**：会话中途把新工具塞进 `tools` 数组（重排/整表替换）→ 前缀缓存失效，省下的定义 token 被 cache miss 吃回；对照 `defer_loading` / 稳定 meta-`call_tool` / 只在 cache breakpoint 之后追加
  4. **Meta-tool 混淆**：把 `search_tools` 当业务工具、或 `invoke` 时带错 name；三层职责必须互斥写进 Host 系统提示
  5. **list_changed 陈旧 Host 缓存**：Server 已发 `notifications/tools/list_changed`，Host 只打日志不 refetch → 模型看不到新工具 / 仍持有已删工具 schema。Codex #33266（deferred 索引不重建）、#37417（会话内永不刷新；Desktop 长任务同症）；Zed 曾缺处理、PR #42453 补上（对照「通知≠刷新」）
  6. **Token 数字（背景，非主线）：** Anthropic Tool Search ~72K→~8.7K（~85%）、Opus 4 MCP eval 49%→74%；code-execution filesystem disclosure 150K→2K（98.7%）——用来说明「省 token 已解决」之后，坑转移到 discovery 正确性
- **相关已发文：** posts/mcp_tool_design_valid_but_wrong.md — **必须划界**：范文 = Server 面 Confusion+Bloat + AWS V4 `get_taxonomy`（作 prior art 一句带过，禁止复述 V1–V4 表）。本文 = Host 发现/缓存/元工具面。与 `mcp-auth-identity-not-intent`（授权受众）、`agent-memory-poisoning`（LTM）不重叠
- **参考线索：**
  - https://www.anthropic.com/engineering/advanced-tool-use — Tool Search / `defer_loading`；~72K→~8.7K；Opus 4 49%→74%；Opus 4.5 79.5%→88.1%；deferred 不破坏 prompt cache
  - https://www.anthropic.com/engineering/code-execution-with-mcp — filesystem progressive disclosure 150K→2K（98.7%）
  - https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool — `defer_loading`；发现后以 conversation 内 `tool_reference` 展开、前缀不变
  - https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-use-with-prompt-caching — 改 tools 定义使整段 cache 失效；`defer_loading` 保 cache
  - https://modelcontextprotocol.io/docs/2025-11-25/develop/clients/client-best-practices — Catalog→Inspect→Execute；`list_changed` 时重索引；mid-conversation 改 `tools` 数组废 cache（追加或稳定 `call_tool` meta）
  - https://aws.amazon.com/blogs/machine-learning/mcp-tool-design-practical-approaches-and-tradeoffs/ — V4 lazy `get_taxonomy`（**范文已覆盖，仅作 prior art**）
  - https://github.com/openai/codex/issues/33266 — `list_changed` 不 invalidate deferred tool cache / 不 refetch
  - https://github.com/openai/codex/issues/37417 — 会话内 tool-list 变更永不生效（handler 只打日志）；Desktop 长任务旁证
  - https://github.com/zed-industries/zed/pull/42453 — Host 补 `list_changed` → reload（历史缺口对照）
  - https://stacklok.com/blog/stackloks-mcp-optimizer-vs-anthropics-tool-search-tool-a-head-to-head-comparison/ — **次要**：2792 tools 上 recall/selection 鸿沟（34% vs 94%）
- **备注：** Gate PASS ready — 新失败面已锁定为 **Host discovery-layer**。写稿禁令：不要再写 dump-all vs lazy 入门、不要复述 Confusion+Bloat 主框架、不要重画 AWS V1–V4 表。开篇一句「范文已讲 Server/`get_taxonomy`」后立刻进入 Host 五坑。P1（有生产级 Host bug + 检索对照，但非安全 P0）。

### [ready] 2026-09-18 | P0 | agent-memory-poisoning
- **工作标题：** Agent 记得太久：Session Summarization 把间接注入写成跨会话「系统指令」
- **失败面：** 当天对话看起来正常；隔天/新 session 才静默改行为或外泄 → 误判为「又一次 prompt injection / 模型对齐失败」；根因是 untrusted tool/document output 经 summarization/memory-writer 写入 LTM，再以高特权（system / orchestration memory 槽）跨会话复活
- **为何够深：** 四段路径 (1) tool/doc 进会话 (2) summarizer / memory tool / 外部 manager 决定写什么 (3) LTM 无 provenance / 信任自抬 (4) 下一 session 拼进 system/orchestration；对照 ephemeral PI vs persistent memory privilege
- **拟用案例 / 对照（禁 exploit 复现）：**
  1. BAD auto-extract upsert（Unit 42）：summarizer 从含 tool result 的 transcript 抽 goals → upsert LTM → memory 进 orchestration system instructions
  2. BAD memory=system prompt（MemoryTrap）；GOOD：user memories 移出 system prompt（Cisco / Claude Code 修复线）
  3. BAD external manager 把观察写成用户事实（Sleeper）；GOOD：`source`/`trust`/`kind`；tool-derived→untrusted；procedural HITL/quarantine；高影响工具读路径 demote
  4. 对照表：写时门控 vs 仅读时过滤 | episodic vs procedural | memory→user/context vs system 槽 | 快照回滚 | promote vs auto-extract
- **相关已发文：** posts/mcp_tool_design_valid_but_wrong.md（推进到跨会话记忆特权）；idempotency / durable / long-horizon / trajectory 不同层
- **参考线索：**
  - https://unit42.paloaltonetworks.com/indirect-prompt-injection-poisons-ai-longterm-memory/
  - https://genai.owasp.org/2026/05/13/memory-is-a-feature-it-is-also-an-attack-surface/
  - https://blogs.cisco.com/ai/identifying-and-remediating-a-persistent-memory-compromise-in-claude-code
  - https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/ （ASI06）
  - https://arxiv.org/abs/2605.15338 — Sleeper Memory Poisoning
- **备注：** Gate PASS ready。写稿禁 exploit/payload 复现；只用架构 BAD/GOOD + checklist。下轮 Writer 可取。

### [ready] 2026-09-18 | P1 | mcp-auth-identity-not-intent
- **工作标题：** MCP Auth：Identity ≠ Audience（OAuth 绿了，token 没绑到这台 MCP）
- **失败面：** Consent / OAuth 看起来成功 → token 缺 `resource`/`aud` 绑定或校验被跳过 → 跨 MCP / 跨应用 / 跨部署重放；误判「再加一层 OAuth / 收紧 scope」
- **为何够深：** 主线锁 **RFC 8707 resource→aud 绑定 + 拒绝错受众 + MUST NOT passthrough**；OAuth 答的是「谁持有 token」，不是「token 是否发给**这台** MCP」。Intent / 参数策略只作短 coda；proxy consent-skip deputy 另文。非 OAuth 入门
- **拟用案例 / 对照：**
  1. **BAD#1 FastMCP OAuth Proxy** GHSA-5h2m-4q8j-pqpj / CVE-2025-69196：忽略 client `resource`，按 `base_url` 发 JWT aud → 同 AS 跨 MCP 重放；fix ≥2.14.2
  2. **BAD#2 Google mcp-toolbox** CVE-2026-14541：`mcpEnabled` 无 audience/clientId → opaque Google token 跳过 aud 校验 → 任意有效 Google access token 可进；fix ≥1.5.0
  3. **BAD#3 FrontMCP** GHSA-hvvp-67p3-j379：transparent JWT 校验 iss 恒真 + 不查 aud → 跨服务重用；fix ≥1.5.4
  4. **旁证 Registry** CVE-2026-44428：共享 OIDC audience `mcp-registry` → 跨部署重放（低危，讲「audience 必须部署级」）
  5. **对照 / GOOD：** 发 token 绑 canonical MCP URI | 每请求验 aud/resource | 拒错资源 | 禁止 client Bearer 原样转发上游（RFC 8693 换票）| passthrough 模式失败须闭（LiteLLM 脚注）| scopesRequired 全协议路径 | 高影响 draft-then-commit
  6. **短 coda（非主线）：** mcp-toolbox CVE-2026-11719 — aud 修好 ≠ 工具授权修好（旧协议路径跳过 scopesRequired）
- **相关已发文：** posts/mcp_tool_design_valid_but_wrong.md（工具选择层）；与 `agent-memory-poisoning` 划界：调用时 token 绑定，不是 LTM。consent-skip deputy（FastMCP CVE-2026-27124）另选题
- **参考线索：**
  - https://github.com/PrefectHQ/fastmcp/security/advisories/GHSA-5h2m-4q8j-pqpj
  - https://www.cve.org/CVERecord?id=CVE-2026-14541
  - https://github.com/agentfront/frontmcp/security/advisories/GHSA-hvvp-67p3-j379
  - https://github.com/modelcontextprotocol/registry/security/advisories/GHSA-95c3-6vvw-4mrq
  - https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
  - https://github.com/BerriAI/litellm/security/advisories/GHSA-7488-6r32-c95q — passthrough 脚注（auth bypass，非经典转发）
  - https://osv.dev/vulnerability/GHSA-5gf6-gc35-xjpc — coda scopesRequired
- **备注：** Gate PASS ready（主线 A：Identity≠Audience）。经典「client token 原样转发 GitHub」具名 CVE 仍缺——正文标 anti-pattern，勿捏造。slug 保留；标题勿再承诺满 Intent。

### [ready] 2026-09-18 | P0 | multi-agent-closed-loop-handoff
- **工作标题：** 专员互相转交都「成功」：Closed-Loop Escalation / 无终止谓词的 Handoff 环
- **失败面：** 局部 handoff 成功 → 全局环；双边 dashboard 双绿；账单先于刹车（bill before brake）
- **为何够深：** 把 multi-agent handoff 当 **routing fabric** 而非领域抽象——本地路由决策可合成全局环；「Verifier 满意 / 对方更合适」不是可判定终止谓词；observability ≠ enforcement。机制层：per-conversation handoff ledger、reject-and-explain、handoff budget（≠ token budget）、adversarial-seam eval（断言 **bounded termination**）。不是 MAS 入门、不是复述 MAST 14 模式清单
- **拟用案例 / 对照：**
  1. **Analyzer↔Verifier $47k（终止谓词缺失）**：Verifier「再分析一点」开环；11 天 / ~$47k；发现来自 billing，非 agent 内刹车（vectara case study）
  2. **support↔billing closed-loop（所有权 seam）**：「charged」→billing、「access restored」→support；两边「转交成功」双绿（tianpan）
  3. **对照表：** 局部 transfer-out 绿 vs 全局 progress/termination | handoff depth p99 | A↔B 对称热力格 | re-entry counter | structural-only vs hybrid cycle detect（F1 0.08→0.72）| token/cap vs handoff budget | 「Verifier satisfied」vs 可判定谓词
  4. **次要：** Mastra `finishReason: other` 零输出非 terminal → 同请求重发至 maxSteps（#21897）
- **相关已发文：** posts/trajectory_eval_false_green.md（终答假绿——评估面；本文是路由/转交指标假绿）；posts/durable_agent_execution.md；posts/long_horizon_decisive_error.md
- **参考线索：**
  - https://tianpan.co/blog/2026-05-02-closed-loop-escalation-bug-multi-agent-routing-cycles
  - https://github.com/vectara/awesome-agent-failures/blob/main/docs/case-studies/langchain-a2a-47k-infinite-loop.md
  - https://arxiv.org/abs/2503.13657 — MAST（一句锚定）
  - https://arxiv.org/abs/2511.10650 — cycle detection；hybrid F1 0.72
  - https://www.getmaxim.ai/articles/multi-agent-system-reliability-failure-patterns-root-causes-and-production-validation-strategies/
  - https://towardsai.com/p/machine-learning/we-gave-the-ai-supervisor-structured-tools-so-it-couldnt-hallucinate-it-still-made-the-wrong-call — 次要；全文抓取受限勿捏造引文
  - https://github.com/mastra-ai/mastra/issues/21897 — 次要
- **备注：** Gate PASS ready。大纲锁死：routing protocol primitives + termination predicate；两种拓扑同属 closed-loop。禁 MAS primer。Writer 勿整段翻译 tianpan。下轮可与 memory 并列 ready（优先仍由 Coordinator kick）。

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
- 2026-09-18 Scout: add 2 ideas — agent-memory-poisoning (P0), mcp-auth-identity-not-intent (P1); skip handoff/eval-gaming/sandbox; no upgrade mcp-progressive-disclosure.
- 2026-09-18 Coordinator: published `durable-agent-execution` → posts/durable_agent_execution.md (Alice 批准 push).
- 2026-09-18 Scout: upgraded `agent-memory-poisoning` idea→ready (Unit 42 / MemoryTrap / Sleeper BAD-GOOD); keep mcp-auth as idea.
- 2026-09-18 Scout: kept `mcp-auth-identity-not-intent` as idea (FastMCP GHSA-5h2m-4q8j-pqpj = BAD#1; still missing passthrough/intent production BADs).
- 2026-09-18 Scout: add idea `multi-agent-closed-loop-handoff` (P1); skip 2nd filler; no upgrade mcp-progressive-disclosure.
- 2026-09-18 Scout: upgraded `multi-agent-closed-loop-handoff` idea→ready P0 (closed-loop + termination predicate; tianpan/vectara/MAST/cycle-detect).
- 2026-09-18 Scout: upgraded `mcp-auth-identity-not-intent` idea→ready P1 (narrowed Identity≠Audience; FastMCP+Toolbox+FrontMCP BADs).
- 2026-09-18 Scout: upgraded `mcp-progressive-disclosure` idea→ready P1 (Host discovery reframed: recall miss / list_changed / cache; ≠ Server Confusion+Bloat).
