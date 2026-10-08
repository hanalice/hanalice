# Blog topic backlog（滚动选题）

> 单一事实源。由 **选题 Scout** 持续补充；**写稿 Writer** 只消费 `ready`；**审阅 Reviewer** 更新状态；**协调 Coordinator** 仅在审过之后标 `published` 并推送。  
> 准入门槛见 `docs/skills/agent_blog_writing.md` §2。  
> 本文件会不断变长/改状态——**不是**写死在规范里的固定菜单。

## 状态说明

`idea` → `ready` → `writing` → `in_review` → `published` | `rejected` | `parked`

优先级：`P0` > `P1` > `P2`

---

## Queue

### [ready] 2026-10-08 | P1 | subagent-delegation-envelope
- **工作标题：** 子代理一派生，父会话的权限没跟过去：Delegation Envelope 不是「继承」两个字
- **失败面（Host 委派 / 子会话权限包络层，非单会话工具来源装配顺序、非 OAuth）：** 父会话 Plan 只读 / deny Bash 生效 → 经 `task` / `Agent` 工具派生子代理 → 子会话按「替换」或「全新」权限集启动（`tools` 参数替换 session 权限、deny 未传递、ACP 孙会话丢 depth / child-cap / control scope）→ 子代理执行父会话被拒的写 / Bash。反向修复把父的**全部** deny 当后代天花板 → 受限 controller 无法委派给显式授权的 executor，流水线停摆（误判「模型越狱 / 再加一条 deny」或「子代理配置写错」）
- **为何够深（非科普）：** 主线锁 **委派时的权限代数**：`child_effective = f(parent_ceiling, child_declared)`。生产里出现过三种语义：replace（opencode #7474：`tools` 参数替换 session 权限）/ append + last-match-wins（#26597→#26700：父 deny 追加在子 allow 之后，`findLast` 让父的**自限**变成后代天花板）/ 交集 + 显式天花板（Plan 只读作为 descendant ceiling 下传，父自限不下传；Claude Code 文档：子代理声明 `bypassPermissions` 时保持主会话模式，不可借 frontmatter 升权）。再加**传递性**：孙会话必须持久化 envelope（depth、active-child cap、control scope、target-agent），否则一层修好、下一层逃逸（OpenClaw GHSA-q3jj）。不是「什么是 subagent」入门
- **拟用案例 / 对照：**
  1. **BAD#1 replace 语义（opencode）** #7474：`SessionPrompt.prompt()` 的 `tools` 参数**替换** session 权限、`ToolRegistry.tools()` 不按 agent 规则过滤 → 配了 `bash: {git*: allow, *: deny}` 的子代理可跑任意命令（fix PR #7473）；#26514：Plan 模式主代理 edit 被拒，经 `task` 派 `general` 子代理 edit 成功（fix PR #26597）
  2. **BAD#2 修复回归（天花板 vs 自限未建模）** #26700：`deriveSubagentSessionPermission()` 把父**全部** deny 追加进子会话，`Permission.merge(subagent, session)` + last-match-wins → executor 自己的 `read` / `task` / `bash` allow 被父 `* deny` 覆盖，controller→executor→worker 停在 executor；#27201 只修了一部分，edit-class 仍在后续 PR 里拉锯——说明不区分「后代天花板」与「父自限」会两头出错
  3. **BAD#3 传递性丢失（OpenClaw）** GHSA-q3jj-46pq-826r：受限 subagent 派生 ACP child session 时没有带上 depth、child-count、control scope、target-agent 这些约束；≤2026.4.21，修复版 2026.4.22 改为把 child envelope 字段持久化，并强制执行 max depth 和 active-child cap
  4. **旁证（Claude Code）：** #25000 Task 子代理绕过 `settings.local.json` 的 Bash deny，跑了 22+ 条没有逐条审批的命令（已按 #21460 的 dup 关闭）；#27099 agent frontmatter 把 `tools:` 误写成 `allowed-tools:` 被静默忽略 → 子代理继承全部工具（次要，讲 fail-open 解析）
  5. **GOOD：** 显式 envelope 对象 `{ceiling, self_restrictions, depth, max_children, control_scope}` 随 spawn 落盘 | `child = declared ∩ parent.ceiling`（只下传标记为 descendant 的约束）| 未知 / 拼错的 frontmatter 字段 fail-closed 或告警 | deny 规则与策略 hook 在子代理内同样生效（Claude Code 文档：deny 规则作用于主会话和子代理，hook 输入带 `agent_id`）| 子代理声明的权限不能高于父模式
- **§4 业务线：** 同一张发版评审工单 `REL-2041`（父会话在 Plan 只读）。**BAD v1**：父会话 edit 被拒 → 派 `general` 子代理「顺手改 CHANGELOG」→ 写入成功（replace 语义；回扣 §3.1 交集代数）。**BAD v2**：修成「父 deny 全下传」后，`REL-2041` 的 controller（只有 task）→ executor（read/bash）→ worker（edit）在 executor 处因继承来的 `read * deny` 停摆（回扣 §3.2 天花板 vs 自限）。**BAD v3**：executor 为 `REL-2041` 再派 ACP 孙会话，depth / child-cap 丢失，扇出无界（回扣 §3.3 envelope 持久化）。**GOOD**：spawn 时生成 `envelope{ceiling: plan-readonly, depth≤2, max_children: 3}`，随 `REL-2041` 每一层子会话落盘；每层 effective = declared ∩ ceiling；审计日志记录每层过滤前后的工具集合差（回扣 §3.4 可观测）
- **§5 可注入失败点：**
  1. **注入：** 父会话 Plan / 只读，诱导模型经 `task` 派子代理执行 edit / write / 写类 bash → **期望：** 子代理工具清单里没有写工具，或调用被拒；审计记 `denied_by: parent_ceiling`
  2. **注入：** deny-by-default 的 controller 委派给显式 allow 的 executor → **期望：** executor 保留自身 read / task / bash；父自限（`read * deny`）不下传
  3. **注入：** 子代理再 spawn ACP / 孙会话，超 depth 或超 active-child cap；或 agent frontmatter 写未知字段 `allowed-tools:` → **期望：** spawn 被拒，或启动失败并告警；不静默回落为全量继承
- **领域标签：** Agent Host Runtime / Subagent Delegation / Permission Inheritance
- **专题归属：** **MCP/Host Tool-Policy Assembly**（续篇 #2：跨委派边界。#1 `host-tool-policy-merge-after-filter` 讲单会话内工具来源与 policy pass 的先后；本篇讲父→子→孙之间约束如何传递）
- **相关已发文 / 边界：**
  - vs `host-tool-policy-merge-after-filter`：**必须划界**——那篇 = 同一会话内 core / MCP / LSP 工具在过滤之后才拼入；本文 = 会话**之间**的约束传递语义（replace / append / intersect）+ 天花板建模 + 传递性。禁止复述 GHSA-qrp5 装配顺序
  - vs `multi-agent-closed-loop-handoff`：那篇 = 转交路由的终止性（环 / handoff budget）；本文 = 被委派者的权限包络；depth / child-cap 只作安全上限，不讲环检测
  - vs `mcp-auth-identity-not-intent` / `mcp-consent-binding-confused-deputy`：远程 token / consent；本文 = 本地进程内权限
  - vs `agent-memory-poisoning`：跨会话 LTM 特权；本文 = 派生会话特权
- **参考线索：**
  - https://github.com/openclaw/openclaw/security/advisories/GHSA-q3jj-46pq-826r — **主证据（advisory）**；Moderate；≤2026.4.21，修复 2026.4.22（advisory 列出 fix commit `31160dc`）
  - https://github.com/anomalyco/opencode/issues/7474 — **主证据（issue）**；`tools` 参数替换 session 权限；fix PR #7473
  - https://github.com/anomalyco/opencode/issues/26700 — **主证据（issue）**；#26597 回归：父 deny 追加 + last-match-wins 覆盖子 allow；#27201 部分修复
  - https://github.com/anomalyco/opencode/issues/26514 — 旁证：Plan 只读被子代理绕过；fix PR #26597
  - https://github.com/anthropics/claude-code/issues/25000 — 旁证：子代理绕过 Bash deny（dup → #21460）
  - https://github.com/anthropics/claude-code/issues/27099 — 次要：`allowed-tools:` 静默忽略 → 全量继承
  - https://code.claude.com/docs/en/sub-agents — GOOD 文档：deny 规则作用于子代理；子代理声明 `bypassPermissions` 时保持主会话模式
- **备注：** Gate PASS ready — Thu light refill 2026-10-08。**Fri 首推。** 写稿禁令：OpenClaw fix commit 只引用 advisory 原文写到的修复内容，不杜撰函数名；#27099 不复述凭据搜刮步骤，只讲「字段被静默忽略 → 全量继承」的机制；#25000 是 dup 关闭，引用时注明。P1。

### [ready] 2026-10-08 | P1 | orphan-tool-call-session-wedge
- **工作标题：** 一次中断，整个会话永久 400：tool_use / tool_result 配对不变量
- **失败面（Host 会话转录 / conversation-state 持久化层，非结果内容保真、非 checkpoint 副作用重放）：** 用户 Esc / 关 tab / 网络断 / 语音插话打断 / 流式响应被 salvage / 并行工具结果非原子写 / compaction 窗口从 `tool_result` 起切 → 持久化历史里留下没有输出的 `function_call` / `tool_use`（或没有前驱的 `tool_result`）→ 之后每次请求都带着同一段毒历史 → Anthropic `tool_use ids were found without tool_result blocks` / OpenAI `No tool output found for function call` 400，几小时后重试照样失败；有的路径还把 400 包装成「Connection error」（误判「API 抖动 / 网络问题 / 再加 retry」）
- **为何够深（非科普）：** 主线锁 **配对不变量必须在写入侧闭合**：provider 把 call↔output 配对当作请求合法性的硬约束，而 Host 的 interrupt / abort / salvage / compaction / 并发写入路径各自都可能只写下半对。半对一旦落进持久层（server-side conversation store / `previous_response_id` 链 / 本地 JSONL），重试就是**确定性失败**——这是毒历史，不是瞬时错误。解法分三层：(1) 失败点闭合：abort 时为每个已流出的 call 合成 output；(2) 发送前校验与修复：反向扫描双向孤儿，compaction 切点对齐配对边界；(3) 链式复用守卫：pending call 没完成就不复用 `previous_response_id`。再深一层：合成 output 的**语义诚实**——「aborted_before_exec」和「outcome_unknown」必须区分，后者要和幂等键联动，否则模型以为没执行，就会重做副作用
- **拟用案例 / 对照：**
  1. **BAD#1 Claude Code** 元 issue #6836：汇总 150+ 条重复报告（中断 / 网络 / hook 后 / 并行工具）；维护者回复称原因多样、很难完全消除。#45286：并发工具执行时 JSONL 非原子写，3 个 `tool_use` 只落下 2 个 `tool_result`。#6836 评论还记录了 `/compact` 窗口从 `tool_result` 起切 → `messages.0.content.0: unexpected tool_use_id`（反向孤儿）
  2. **BAD#2 OpenAI Agents JS** #1190：streamed `run()` + `conversationId`，在 `function_call` 流出后 abort → server store 已持久化 call，SDK 的 abort 分支直接 return、不生成 output → 同一 conversation 后续 run 全部 400；修复方向：为孤儿 call 合成 `function_call_output`（issue 已关闭，关联 PR #1241）
  3. **BAD#3 LiveKit Agents** #5092：语音用户在长工具调用期间插话 → Responses API 400，会话余下全部失败；websocket 路径把 400 包装成 `APIConnectionError`，掩盖真实错误；fix PR #5094：只在 pending tool calls 完成后才复用 `previous_response_id`
  4. **旁证：** microsoft/amplifier #353：非 completed 的流式响应被 salvage，留下参数截断成 `{}` 的 call 和没有 output 的 call → 会话日志 14 次失败，包括 7 小时后的重试；建议丢弃不可解析的 call，并为未执行的 call 合成 error output。Azure SDK #46092：失败的 turn 以 `store=true` 持久化半对
  5. **GOOD：** abort / interrupt / salvage 分支合成 output（status incomplete）| 发送前 invariant 校验 + 修复（双向孤儿）| compaction / trim 切点回退到配对边界 | 并行结果原子批写 | 链式复用守卫 | 合成内容区分 `aborted_before_exec` 与 `outcome_unknown`，后者带幂等键、下一轮先查状态 | 400 invalid_request 归类为不可重试的历史损坏，而不是网络错
- **§4 业务线：** 同一退款会话 `conv_RF-7731`，模型并行发出 `lookup_order` 和 `issue_refund(call_9f2)`。**BAD v1**：用户关 tab，abort 分支直接 return，`call_9f2` 已进 server store 但没有 output → 用户回来问「好了吗」→ 400，重试全挂，只能新开会话、丢上下文（回扣 §3.1 失败点闭合）。**BAD v2**：补丁合成 `"aborted"` → 模型以为没退款，再发一次 `issue_refund` → 双退款（回扣 §3.4 语义诚实 + 幂等键）。**BAD v3**：`conv_RF-7731` 变长后 compaction 从 `lookup_order` 的 `tool_result` 起切 → 反向孤儿 400（回扣 §3.2 切点对齐）。**GOOD**：abort 时为 `call_9f2` 写入 `{status: outcome_unknown, idempotency_key: RF-7731-1}`，下一轮先 `get_refund_status(RF-7731-1)` 再决定；发送前 validator 保证双向配对；compaction 切点回退到配对边界
- **§5 可注入失败点：**
  1. **注入：** `function_call` 流出之后、工具执行之前 abort（取消信号 / 断连接）→ **期望：** 持久化历史中每个 call 都有 output（incomplete），下一轮请求 200
  2. **注入：** 并行 3 个工具时丢掉一条结果写入，或让 compaction 窗口从 `tool_result` 处开始 → **期望：** 发送前 validator 检出孤儿，修复或拒绝发送；日志记 `transcript_invariant_repaired`，不进入 400 重试循环
  3. **注入：** provider 返回 400 invalid_request 后让 retry 策略生效；被标为 `outcome_unknown` 的写工具进入下一轮 → **期望：** 归类为不可重试、不重放同一段历史；写工具先查状态再执行，不双写
- **领域标签：** Agent Host Runtime / Conversation State / Tool-Call Protocol
- **专题归属：** **Agent Session-State Integrity**（新建。#1 结构不变量 = 本文；#2 语义保真 = `compaction-drops-pinned-instructions`）
- **相关已发文 / 边界：**
  - vs `durable-agent-execution`：那篇 = 进程死后从 checkpoint 重入导致副作用重放；本文 = 会话**消息历史**结构非法导致永久 400。交点只在「合成 output 的语义诚实」一节，引用不复述
  - vs `agent-write-idempotency`：那篇 = 超时后凭什么敢重试；本文只把幂等键当作 `outcome_unknown` 的落地手段，不重讲幂等
  - vs `silent-tool-result-truncation`：那篇 = 结果内容被裁切但结构仍「合法」（静默）；本文 = 结构配对断裂被 provider 直接拒绝（有声，但不能自愈）
  - vs `mcp-progressive-disclosure`：那篇 = 改 `tools` 数组破 prompt cache；本文 = `messages` 数组的配对
- **参考线索：**
  - https://github.com/anthropics/claude-code/issues/6836 — **主证据（issue）**；150+ 重复报告的汇总；评论含 compaction 反向孤儿复现
  - https://github.com/openai/openai-agents-js/issues/1190 — **主证据（issue）**；abort + `conversationId` 留下孤儿 `function_call`；根因代码段与合成 output 修复方向
  - https://github.com/livekit/agents/pull/5094 — **主证据（fix PR）**；pending tool calls 未完成时不复用 `previous_response_id`（issue #5092）
  - https://github.com/anthropics/claude-code/issues/45286 — 旁证：并发工具执行时 JSONL 非原子写丢 `tool_result`
  - https://github.com/livekit/agents/issues/5092 — 旁证：语音插话打断工具调用；400 被包装成连接错误
  - https://github.com/microsoft/amplifier/issues/353 — 旁证：salvage 不完整流式响应留下未配对的 call
  - https://github.com/Azure/azure-sdk-for-python/issues/46092 — 次要：failed turn 以 store=true 持久化半对
- **备注：** Gate PASS ready — Thu light refill 2026-10-08。写稿禁令：#6836 评论里「1,571 sessions / 8,007 orphaned」是社区逆向统计（指向 #33949），引用必须注明非官方；不要声称 Anthropic 已彻底修复；合成 output 的 status 字段名以各 SDK 实际实现为准，正文用中性描述。P1。

### [ready] 2026-10-08 | P2 | compaction-drops-pinned-instructions
- **工作标题：** Compaction 之后 Agent 忘了「先给我看计划」：被摘要掉的不是历史，是约束
- **失败面（Host 上下文压缩层，非 LTM 写入、非单次工具结果裁切）：** 长会话触发 auto / manual compaction → summarizer 把 AGENTS.md / CLAUDE.md 项目规则、用户最近的**条件指令**（「先修订计划给我审，再实现」）、已完成动作当普通历史一起 paraphrase → 压缩后 agent 直接实现、违反项目规则、重做已完成步骤（进度 97% 掉回 42%）（误判「模型不听话 / 指令写得不够大声 / 再加一遍 IMPORTANT」）
- **为何够深（非科普）：** 主线锁 **约束 vs 叙事 vs 账本分层**：压缩是有损摘要，适合叙事（做过什么的大意），不适合约束（规则、条件门控、承诺），也不适合账本（已完成的副作用）。三类内容需要三种保留方式：pinned verbatim 重注入（规则源以快照形式，每个压缩边界恰好注入一次）、结构化门控状态（`awaiting_review` 这类状态不能交给摘要模型去「解释」）、外部进度账本（已完成步骤由 harness 写，不靠摘要记）。机制对照：Codex PR #29810 把 AGENTS.md 作为持久化 WorldState，初始上下文、每请求更新和 compaction 上下文同源构建，resume / fork 时指令变更只注入一次替换；Claude Code 在压缩边界有 `InstructionsLoaded`（load_reason=`compact`）和 SessionStart `compact` matcher。不是「context window 是什么」入门
- **拟用案例 / 对照：**
  1. **BAD#1 条件指令被压平（Claude Code）** #23776：plan-review 迭代中触发 compaction → 摘要保留了技术内容，丢掉「先审再实现」这个条件 → 压缩后直接改代码；摘要里的「Pending Tasks」反映的是模型的解读，而不是用户原话
  2. **BAD#2 规则源被摘要（Codex）** #2927 / #5772：`/compact`（含 auto）之后 AGENTS.md 不再注入；#25792：压缩后进度从约 97% 掉到约 42%，进度汇报规则失效，已完成的工作被重开；Claude Code #24460 同症（CLAUDE.md 被一起摘要）
  3. **BAD#3 执行账本丢失（Claude Code）** #75759：同一活跃会话内压缩后忘记已经执行过的动作 → 重做步骤（非幂等时有副作用风险）
  4. **GOOD：** Codex PR #29810（AGENTS.md 作为持久 WorldState；compaction 上下文与请求同源；resume / fork 指令变更恰好注入一次）| Codex #46186 提案：快照 verbatim、每个压缩边界恰好恢复一次，眼下可用 SessionStart `compact` hook 重放 | Claude Code hooks：`InstructionsLoaded`（`compact`）、`PreCompact` / `PostCompact`、SessionStart `compact` matcher | 门控状态与进度账本放到 harness 外部
- **§4 业务线：** 同一迁移任务 `MIG-318`（把 billing 表迁到新 schema；AGENTS.md 规定「禁止直连 prod DB；每阶段先出计划等审」）。**BAD v1**：第 3 轮用户说「把回滚方案改好再给我看」，这时 auto-compact → 摘要写成「下一步：实施迁移」→ agent 直接跑 `MIG-318` 迁移脚本，而且因为 AGENTS.md 被 paraphrase 掉，连的是 prod（回扣 §3.1 pinned 重注入 + §3.2 门控状态）。**BAD v2**：压缩后不记得 `MIG-318` step 2 `backfill` 已经跑过 → 再跑一遍（回扣 §3.3 外部账本）。**GOOD**：AGENTS.md 快照在压缩边界 verbatim 重注入一次；`MIG-318.state=awaiting_plan_review` 由 harness 状态机持有，压缩改不了它；`progress.jsonl` 记录 step 完成情况 + 幂等键，压缩后先读账本
- **§5 可注入失败点：**
  1. **注入：** 在「等待审阅」状态下强制触发 compaction（调低阈值或手动 `/compact`）→ **期望：** 下一轮不调用写工具，先输出修订后的计划；`awaiting_review` 状态不变
  2. **注入：** compaction 之后抓取实际发给模型的 prompt；会话中途修改规则文件后再 resume → **期望：** AGENTS.md / CLAUDE.md verbatim 出现且只出现一次；规则变更后替换注入一次，不重复、不丢失
  3. **注入：** 完成一个非幂等步骤后立刻压缩 → **期望：** agent 读外部账本跳过该步骤；即使重调也被幂等键拦截
- **领域标签：** Agent Host Runtime / Context Management / Instruction Persistence
- **专题归属：** **Agent Session-State Integrity**（新建系列 #2：语义保真；#1 = `orphan-tool-call-session-wedge` 结构不变量）
- **相关已发文 / 边界：**
  - vs `agent-memory-poisoning`：**必须划界**——那篇 = summarizer 把**不可信**内容写进 LTM 并抬权（跨会话）；本文 = summarizer 把**可信**约束降级或丢失（单会话内）。同一机制、方向相反，只用一句对照
  - vs `silent-tool-result-truncation`：那篇 = 单次工具结果被裁；本文 = 历史整体重写后约束 / 门控丢失
  - vs `durable-agent-execution` / `agent-write-idempotency`：重复步骤只是 BAD v2 的后果，引用幂等篇，不复述
  - vs `long-horizon-decisive-error`：那篇讲归因方法；本文可以算「决定性错误」的一类成因，但不讲归因
  - vs ready `orphan-tool-call-session-wedge`：同系列；那篇 = compaction 切点破坏结构；本文 = compaction 摘要丢失语义
- **参考线索：**
  - https://github.com/anthropics/claude-code/issues/23776 — **主证据（issue）**；条件指令「先审再实现」被压平成「实现」
  - https://github.com/openai/codex/issues/25792 — **主证据（issue）**；压缩后 AGENTS 规则失效、进度 97%→42%
  - https://github.com/openai/codex/pull/29810 — **主证据（fix PR，merged 2026-06-25）**；AGENTS.md 作为持久 WorldState，compaction 上下文同源，resume / fork 恰好注入一次（注：该 PR 的主要动机是 deferred executor 环境变更，compaction 同源只是其中一项，写稿时不要夸大）
  - https://github.com/openai/codex/issues/2927 — 旁证：`/compact` 后 AGENTS.md 被忽略
  - https://github.com/openai/codex/issues/46186 — 旁证：快照 verbatim、每个压缩边界恰好恢复一次；SessionStart `compact` hook 方案
  - https://github.com/anthropics/claude-code/issues/24460 — 旁证：CLAUDE.md 在 `/compact` 后丢失
  - https://github.com/anthropics/claude-code/issues/75759 — 旁证：压缩后遗忘本会话已执行的动作
  - https://code.claude.com/docs/en/hooks — GOOD 文档：`InstructionsLoaded` load_reason `compact`、SessionStart `compact` matcher、`PreCompact` / `PostCompact`
- **备注：** Gate PASS ready — Thu light refill 2026-10-08。写稿禁令：不要把各家压缩实现细节写成官方原理（多数只能从 issue 和文档推断）；97%→42% 是单个用户报告，引用时写「有用户报告」；不要写成「教你写 CLAUDE.md」的科普。P2（排在前两条之后）。

### [idea] 2026-10-08 | P2 | mcp-sampling-server-controlled-prompt
- **工作标题：** MCP Sampling：Server 借 Client 的模型说话
- **失败面（MCP Client sampling 信任边界，非 tool description 投毒）：** Server 通过 `sampling/createMessage` 控制 prompt 和 `systemPrompt` 并消费补全 → 隐藏指令消耗配额 / 劫持后续对话 / 诱发隐蔽工具调用
- **为何仍是 idea：** 目前只有 Unit 42 研究博文和第三方汇总，**缺 primary source**（advisory / fix commit / client issue）；需要找到真实 Client 实现在 sampling 审批 / 隔离上的缺陷再升 ready
- **专题归属：** 候选 MCP 协议信任边界（与 MCP-Auth 相邻）
- **参考线索：**
  - https://unit42.paloaltonetworks.com/model-context-protocol-attack-vectors/ — 三类攻击向量（研究，非 primary）
- **备注：** Scout 2026-10-08 留 idea；升级条件：≥1 条 Client 侧 advisory / issue + 修复对照。

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

### [published] 2026-09-25 | P1 | mcp-progressive-disclosure
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
- **已发文：** posts/mcp_progressive_disclosure.md
- **备注：** Reviewer approved; Coordinator auto-push 2026-09-25（新规则；六段对齐 durable_agent_execution）。系列下一坑：silent-tool-result-truncation。


### [published] 2026-09-28 | P1 | silent-tool-result-truncation
- **工作标题：** 静默截断：工具「成功返回」了半截，模型却自信答完
- **失败面（Host / runtime tool-result fidelity 层，非 Server schema、非 discovery）：** 工具已返回完整 payload → Host/runtime 按默认 byte/token/行上限静默裁切 → 模型只见前缀/head-tail → 仍输出高置信结论；trace/APM 常记「完整返回」因为埋点在裁切前。误判「模型忽略证据 / 又一次 hallucination」
- **为何够深（非科普）：** 主线锁 **信息保真契约**：limit 必须存在，但「drop overflow and continue」对概率推理器是错误默认——确定性解析器会炸，reasoner 会补洞。拆三层裁切（framework cap / transport buffer / display vs model view）+ observability 落在裁切错误侧 + eval 假绿。非「怎么设 context window」入门
- **拟用案例 / 对照：**
  1. **BAD#1 Codex in-place truncate** #14206：超 `tool_output_token_limit` 就地 head/tail + `…N tokens truncated…`，无 artifact/handle → 中段答案永久丢失；非幂等工具无法重跑补回；MCP 大 JSON/日志同症（#14466）
  2. **BAD#2 观测错位（LatentEval）**：wrapper 记工具完整返回，runtime 再裁 → 人看完整、模型看碎片；head-tail 保括号使残缺数组仍「合法 JSON」→ 聚合/计数错但结构对
  3. **BAD#3 旁证 description 静默截断** Claude Code #81268：tool `description`/`instructions` 客户端 2048 不可见裁切；`/mcp` 显示全文、模型收 truncated；#41593 code_executor 签名被砍后幻觉不存在函数（**次要**，划界：描述面 vs 结果面）
  4. **BAD#4 FastMCP ResponseLimitingMiddleware** #3717：裁切后丢 `structured_content` → 带 `outputSchema` 的工具协议违规（loud 变体；对照 silent）
  5. **GOOD：** 结构化 `result_truncated`/`original_size`/`returned_size` 字段（模型可读 + 指标可图）| 超限 **spill-to-artifact + handle**（Claude Code / Gemini CLI 文件引用路径）| 工具契约分页/`nextCursor`（模型显式续取）| harness 断言 runtime 截断 marker + 大响应 fixture（答案依赖 cap 之后证据）| per-tool truncation rate 告警
- **领域标签：** Agent Host Runtime / Tool-Result Fidelity
- **专题归属：** **MCP/Host Tool-Result Fidelity**（新建；与 Host Discovery 相邻但不同层——discovery=工具能否被找到；本文=找到后结果是否完整到达 reasoner）
- **相关已发文 / 边界：**
  - vs 已发文 `mcp-progressive-disclosure`：那篇 = Catalog/search/`list_changed`/cache；本文 = **调用结果路径**上的静默丢信息
  - vs `mcp-valid-but-wrong`：Server schema 合法错选；本文 Host 裁切导致证据不全
  - vs `trajectory-eval-false-green`：终答假绿评估面；本文提供一类 **假绿根因**（证据在进模型前被剪）但机制层不同
  - vs `agent-memory-poisoning`：跨会话 LTM 特权；本文单轮/同会话结果保真
- **参考线索：**
  - https://tianpan.co/blog/2026/05/10/silent-tool-truncation-8kb-default-agent-reasons-blind — 8KB/框架默认；reasoner vs parser 失败模式差
  - https://latenteval.ai/research/tool-output-truncation — 七 runtime 默认 cap 表；埋点错位；marker 断言
  - https://github.com/openai/codex/issues/14206 — auto-spill vs in-place truncate
  - https://github.com/openai/codex/issues/14466 — MCP 已完整返回仍显示 truncated
  - https://github.com/anthropics/claude-code/issues/81268 — description 2048 不可见截断（次要）
  - https://github.com/PrefectHQ/fastmcp/issues/3717 — ResponseLimitingMiddleware × outputSchema
  - https://www.anthropic.com/engineering/code-execution-with-mcp — 大结果改 code-exec 蒸馏（GOOD 形态之一）
- **已发文：** posts/silent_tool_result_truncation.md
- **备注：** Reviewer approved; Coordinator auto-push 2026-09-28（新规则；六段对齐 durable；Tool-Result Fidelity）。系列下一坑：host-tool-policy-merge-after-filter。

### [published] 2026-09-30 | P1 | host-tool-policy-merge-after-filter
- **工作标题：** 工具策略「滤完了」：MCP/LSP 却在过滤之后才拼进来
- **失败面（Host tool-policy 装配层，非 OAuth aud、非 consent binding）：** 运维配了 profile / allow-deny / sandbox / owner-only / subagent 策略 → core tools 过 pipeline → **bundled MCP/LSP tools 在过滤后 append** → 同名策略本该拒绝的 MCP 工具仍进 `effectiveTools`。误判「策略配错了 / 再加一层 deny list」
- **为何够深（非科普）：** 主线锁 **merge-after-filter 反模式**：策略正确性取决于「谁最后进集合」。修复不是再写一条 deny，而是 **final effective policy pass 覆盖全部来源**（含 compaction/re-run 路径）。与 Identity≠Audience（token 受众）、Consent Binding（浏览器会话）不同层——本文是 **本地 Host 授权装配顺序**
- **拟用案例 / 对照：**
  1. **BAD#1 OpenClaw** GHSA-qrp5-gfw2-gxv4：`bundleMcpRuntime?.tools` / `bundleLspRuntime?.tools` 在 core 过滤后 concat；affected `<2026.4.20`；需已配置 bundled MCP/LSP + 本应限制该工具的策略
  2. **机制对照：** policy(core) ⊕ unfiltered(bundled) ≠ policy(core ∪ bundled)；dashboard「策略已启用」双绿掩盖装配洞
  3. **GOOD：** `applyFinalEffectiveToolPolicy` 对合并后全集再跑 profile / provider / global·agent·group / owner-only / sandbox / subagent（fix commit `0e7a992`）；单测覆盖 allowlist、显式 deny、继承 subagent、bundle-mcp metadata
  4. **发版清单提纲：** 枚举所有 tool 注入点（core / MCP / LSP / plugin / compaction rebuild）| 每点后是否再过同一 policy 函数 | 集成测：deny `mcp__*` 后 bundled 不可见 | 审计日志记录过滤前后集合差
- **领域标签：** Agent Host Runtime / Tool Policy Enforcement
- **专题归属：** **MCP/Host Tool-Policy Assembly**（新建；Host 安全装配系列；MCP-Auth 专题已收官 Identity≠Audience + Consent Binding，本篇不复述 OAuth）
- **相关已发文 / 边界：**
  - vs `mcp-auth-identity-not-intent` / `mcp-consent-binding-confused-deputy`：**必须划界**——那两篇 = 远程 OAuth/consent；本文 = 进程内工具名单过滤顺序
  - vs `mcp-progressive-disclosure`：discovery/recall；本文 = 已进入 Host 的工具是否受策略约束
  - vs `mcp-valid-but-wrong`：选错工具；本文 = 不该出现的工具仍可选
- **参考线索：**
  - https://github.com/openclaw/openclaw/security/advisories/GHSA-qrp5-gfw2-gxv4 — Moderate；patched 2026.4.20
  - https://github.com/openclaw/openclaw/commit/0e7a992d3f3155199c1acc2dd9a53c5b3a4d3ada — `applyFinalEffectiveToolPolicy`
  - https://github.com/openclaw/openclaw/issues/65612 — 次要：per-agent MCP filtering 诉求（策略应覆盖 MCP）
- **已发文：** posts/host_tool_policy_merge_after_filter.md
- **备注：** Reviewer approved; Coordinator auto-push 2026-09-30（新规则；六段对齐 durable；Tool-Policy Assembly）。Ready 写后=0，需周四轻补。

### [published] 2026-09-23 | P1 | mcp-consent-binding-confused-deputy
- **工作标题：** MCP Consent Binding：Consent 绿了，IdP callback 没绑到同意过的浏览器（Confused Deputy）
- **失败面（OAuth Proxy consent→callback 绑定层，非 aud/resource）：** 攻击者在自己浏览器完成 MCP consent → 截获上游 IdP authorize URL → 诱骗已登录且曾授权过同 IdP client 的受害者打开 → IdP 因「已授权」跳过 consent → Proxy `_handle_idp_callback` 只验 `state`+`code`、不验「发 callback 的浏览器是否刚同意过」→ 受害者 token 落到攻击者 client。误判「再加一层 OAuth / 收紧 scope / 怪 IdP 跳过 consent」
- **为何够深（非科普）：** 主线锁 **consent approval ↔ IdP callback 的浏览器会话绑定**（signed `MCP_CONSENT_BINDING` / per-client consent registry），不是 Identity≠Audience 的 resource→aud。IdP 跳过 consent 本身合法；根因是 Proxy 当 confused deputy。`require_authorization_consent=False` 路径仍无 cookie 可绑——部署级残留坑。非 OAuth 入门、非复述 RFC 8707
- **拟用案例 / 对照：**
  1. **BAD#1 FastMCP OAuthProxy** GHSA-rww4-4w9c-7733 / CVE-2026-27124：`_handle_idp_callback` 不验同意浏览器；GitHubProvider 上 PoC（IdP skip consent + 截获 authorize URL）；fix ≥3.2.0
  2. **机制对照：** consent 页 CSRF/signed cookie 只证「用户点了同意」≠ 把同意绑到后续 IdP callback 的同一 UA；缺 binding → 跨浏览器完成流
  3. **GOOD：** 同意时发 signed `__Host-MCP_CONSENT_BINDING`（txn_id→token）| callback 校验 cookie 匹配否则 403 | per-client consent registry（MCP Security Best Practices）| 禁止在 consent 批准前写 state cookie | 生产勿关 `require_authorization_consent`
  4. **残留坑：** consent 关闭时 `authorize()` 返回 URL 字符串、无法 Set-Cookie → binding 检查跳过（PR #3201 明示）
- **相关已发文：** 与已发文 `mcp-auth-identity-not-intent`（Identity≠Audience / RFC 8707 aud）**必须划界**：那篇 = token 是否发给**这台** MCP；本文 = consent 是否绑到**完成 callback 的浏览器** / CWE-441。与 `agent-memory-poisoning`（LTM）、`mcp-progressive-disclosure`（Host discovery）不重叠。范文 mcp_tool_design_valid_but_wrong 不同层
- **参考线索：**
  - https://github.com/PrefectHQ/fastmcp/security/advisories/GHSA-rww4-4w9c-7733 — CVE-2026-27124；affected <3.2.0
  - https://www.cve.org/CVERecord?id=CVE-2026-27124
  - https://github.com/PrefectHQ/fastmcp/pull/3201 — `MCP_CONSENT_BINDING` cookie fix；consent-disabled 残留说明
  - https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices — Confused Deputy；per-client consent；consent cookie MUST bind `client_id`
  - https://nvd.nist.gov/vuln/detail/CVE-2026-27124 — CWE-441
- **已发文：** posts/mcp_consent_binding_confused_deputy.md
- **备注：** Reviewer approved; Coordinator auto-push 2026-09-23（新规则）。弱项标「周末 Alice 必改」。系列下一坑：mcp-progressive-disclosure。

### [published] 2026-09-21 | P0 | agent-memory-poisoning
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
- **已发文：** posts/agent_memory_poisoning.md
- **备注：** Reviewer approved; Alice 批准 push 2026-09-21。系列下一坑：multi-agent-closed-loop-handoff

### [published] 2026-09-22 | P1 | mcp-auth-identity-not-intent
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
- **已发文：** posts/mcp_auth_identity_not_intent.md
- **备注：** Reviewer approved; Coordinator auto-push 2026-09-22（新规则，不等 Alice「批准 push」）。系列下一坑：mcp-progressive-disclosure

### [published] 2026-09-22 | P0 | multi-agent-closed-loop-handoff
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
- **已发文：** posts/multi_agent_closed_loop_handoff.md
- **备注：** Reviewer approved; Alice 批准 push 2026-09-22。系列下一坑：mcp-auth-identity-not-intent / mcp-progressive-disclosure

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
- 2026-09-21 Coordinator: published `agent-memory-poisoning` → posts/agent_memory_poisoning.md (Alice 批准 push).
- 2026-09-22 Coordinator: published `multi-agent-closed-loop-handoff` → posts/multi_agent_closed_loop_handoff.md (Alice 批准 push).
- 2026-09-22 Coordinator: published `mcp-auth-identity-not-intent` → posts/mcp_auth_identity_not_intent.md (Reviewer Approve → immediate push).
- 2026-09-22 Scout: add ready mcp-consent-binding-confused-deputy (Tue light; FastMCP consent→callback confused deputy); PR #29
- 2026-09-22 Scout: rebase #29 onto main after mcp-auth published.
- 2026-09-23 Coordinator: published `mcp-consent-binding-confused-deputy` → posts/mcp_consent_binding_confused_deputy.md (Reviewer Approve → immediate push; 周末 Alice 必改).
- 2026-09-24 Scout: Thu light refill — add ready `silent-tool-result-truncation` (Host tool-result fidelity; Codex/LatentEval/Claude-Code BADs) + ready `host-tool-policy-merge-after-filter` (OpenClaw GHSA-qrp5 merge-after-filter); skip Claw-Chain/sandbox-escape (exploit-chain heavy) and false-success arxiv (overlaps trajectory-eval).
- 2026-09-25 Coordinator: published `mcp-progressive-disclosure` → posts/mcp_progressive_disclosure.md (Reviewer Approve → immediate push; six-section durable structure).
- 2026-09-28 Coordinator: published `silent-tool-result-truncation` → posts/silent_tool_result_truncation.md (Reviewer Approve → immediate push; Tool-Result Fidelity).
- 2026-09-30 Coordinator: published `host-tool-policy-merge-after-filter` → posts/host_tool_policy_merge_after_filter.md (Reviewer Approve → immediate push; Tool-Policy Assembly).
- 2026-10-08 Scout: Thu light refill — add ready `subagent-delegation-envelope` (P1, Tool-Policy Assembly #2; OpenClaw GHSA-q3jj + opencode #7474/#26700) + `orphan-tool-call-session-wedge` (P1, new Session-State Integrity; claude-code #6836 / openai-agents-js #1190 / livekit PR #5094) + `compaction-drops-pinned-instructions` (P2, Session-State Integrity #2; claude-code #23776 / codex #25792 / codex PR #29810); add idea `mcp-sampling-server-controlled-prompt` (no primary source yet); skipped streaming partial-JSON / retry-storm / computer-use grounding (not evidence-checked this round).
