# Blog topic backlog（滚动选题）

> 单一事实源。由 **选题 Scout** 持续补充；**写稿 Writer** 只消费 `ready`；**审阅 Reviewer** 更新状态；**协调 Coordinator** 仅在审过之后标 `published` 并推送。  
> 准入门槛见 `docs/skills/agent_blog_writing.md` §2。  
> 本文件会不断变长/改状态——**不是**写死在规范里的固定菜单。

## 状态说明

`idea` → `ready` → `writing` → `in_review` → `published` | `rejected` | `parked`

优先级：`P0` > `P1` > `P2`

---

## Queue

### [published] 2026-10-09 | P1 | subagent-delegation-envelope
- **工作标题：** 子代理一派生，父会话的权限没跟过去：Delegation Envelope 不是「继承」两个字
- **失败面（Host 委派 / 子会话权限包络层，非单会话工具来源装配顺序、非 OAuth）：** 父会话 Plan 只读 / deny Bash 生效 → 经 `task` / `Agent` 工具派生子代理 → 子会话按「替换」或「全新」权限集启动（`tools` 参数替换 session 权限、deny 未传递、ACP 孙会话丢 depth / child-cap / control scope）→ 子代理执行父会话被拒的写 / Bash。反向修复把父的**全部** deny 当后代天花板 → 受限 controller 无法委派给显式授权的 executor，流水线停摆（误判「模型越狱 / 再加一条 deny」或「子代理配置写错」）
- **为何够深（非科普）：** 主线锁 **委派时的权限代数**：`child_effective = f(parent_ceiling, child_declared)`。生产里出现过的语义：replace（opencode #7474：`tools` 参数替换 session 权限；该 issue 以 not planned 关闭、fix PR #7473 未合，**只用来讲机制**）/ append + last-match-wins（#26514 的修复 PR #26597 已合，却引入回归 #26700：父 deny 追加在子 allow 之后，`findLast` 让父的**自限**变成后代天花板；已合 PR #27201 只部分修复）。GOOD = 交集 + 显式天花板（本文的设计主张：只下传标记为 descendant ceiling 的约束，父自限不下传）。Claude Code 文档只作对照、不作天花板范例：主会话在 `bypassPermissions` / `acceptEdits` / auto 时子代理跟随主会话模式；主会话在 `default` / `dontAsk` / `plan` 时子代理按自己声明的 `permissionMode` 运行（Plan **不是**后代天花板），只有声明 `bypassPermissions`（或 auto 不可用）时保持主会话模式。再加**传递性**：孙会话必须持久化 envelope（depth、active-child cap、control scope、target-agent），否则一层修好、下一层逃逸（OpenClaw GHSA-q3jj）。不是「什么是 subagent」入门
- **拟用案例 / 对照：**
  1. **BAD#1 replace 语义（opencode）** #7474：`SessionPrompt.prompt()` 的 `tools` 参数**替换** session 权限、`ToolRegistry.tools()` 不按 agent 规则过滤 → 配了 `bash: {git*: allow, *: deny}` 的子代理可跑任意命令（issue 2026-02-02 以 not planned 关闭；fix PR #7473 2026-03-11 关闭、**未合并**——只作机制示例，不能写成「已修复」）；#26514：Plan 模式主代理 edit 被拒，经 `task` 派 `general` 子代理 edit 成功（fix PR #26597，已合 2026-05-09）
  2. **BAD#2 修复回归（天花板 vs 自限未建模）** #26700：已合 PR #26597 新增的 `deriveSubagentSessionPermission()` 把父**全部** deny 追加进子会话，`Permission.merge(subagent, session)` + last-match-wins → executor 自己的 `read` / `task` / `bash` allow 被父 `* deny` 覆盖，controller→executor→worker 停在 executor。已合 PR #27201（2026-05-13，关闭 #26700）**只修了一部分**：保留 Plan 的 edit 限制、不再下传 `read` / `bash` / `task` 自限，但 edit-class deny 仍无条件下传；后续 PR #27654 未合（2026-06-18 关闭），issue 关闭后仍有用户在 1.15.6 报告同类问题——说明不区分「后代天花板」与「父自限」会两头出错
  3. **BAD#3 传递性丢失（OpenClaw）** GHSA-q3jj-46pq-826r：受限 subagent 派生 ACP child session 时没有带上 depth、child-count、control scope、target-agent 这些约束；≤2026.4.21，修复版 2026.4.22 改为把 child envelope 字段持久化，并强制执行 max depth 和 active-child cap
  4. **旁证（Claude Code）：** #25000 Task 子代理绕过 `settings.local.json` 的 Bash deny，跑了 22+ 条没有逐条审批的命令（已按 #21460 的 dup 关闭）；#27099 agent frontmatter 把 `tools:` 误写成 `allowed-tools:` 被静默忽略 → 子代理继承全部工具（以 not planned 关闭；次要，讲 fail-open 解析）
  5. **GOOD：** 显式 envelope 对象 `{ceiling, self_restrictions, depth, max_children, control_scope}` 随 spawn 落盘 | `child = declared ∩ parent.ceiling`（只下传标记为 descendant 的约束）| 未知 / 拼错的 frontmatter 字段 fail-closed 或告警 | deny 规则在子代理内同样生效（Claude Code sub-agents 文档：`permissions.deny` 里的 Bash deny 规则作用于主会话和子代理）| 子代理声明的模式要经天花板裁剪（这是本文主张；Claude Code 现行语义并非如此，见上）
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
  - https://github.com/anomalyco/opencode/issues/7474 — **主证据（issue，仅机制）**；`tools` 参数替换 session 权限；closed **not planned**；fix PR #7473 **未合并**
  - https://github.com/anomalyco/opencode/issues/26700 — **主证据（issue）**；已合 PR #26597 引入的回归：父 deny 追加 + last-match-wins 覆盖子 allow；由已合 PR #27201 关闭，但只部分修复
  - https://github.com/anomalyco/opencode/pull/26597 — 旁证：fix PR（merged 2026-05-09），修 #26514，同时引入 #26700 回归
  - https://github.com/anomalyco/opencode/pull/27201 — 旁证：部分修复（merged 2026-05-13）；edit-class deny 仍下传
  - https://github.com/anomalyco/opencode/issues/26514 — 旁证：Plan 只读被子代理绕过；fix PR #26597
  - https://github.com/anthropics/claude-code/issues/25000 — 旁证：子代理绕过 Bash deny（dup → #21460）
  - https://github.com/anthropics/claude-code/issues/27099 — 次要：`allowed-tools:` 静默忽略 → 全量继承（closed not planned）
  - https://code.claude.com/docs/en/sub-agents — 对照文档：Bash deny 规则作用于主会话和子代理；主会话在 default / dontAsk / plan 时子代理按自身声明的 `permissionMode` 运行（非天花板），声明 `bypassPermissions` 时保持主会话模式；默认最多三层嵌套，到深度上限时收回 `Agent` 工具
- **备注：** Gate PASS ready — Thu light refill 2026-10-08。**Fri 首推。** 写稿禁令：OpenClaw fix commit 只引用 advisory 原文写到的修复内容，不杜撰函数名；#27099 不复述凭据搜刮步骤，只讲「字段被静默忽略 → 全量继承」的机制；#25000 是 dup 关闭，引用时注明。P1。
- **已发文：** posts/subagent_delegation_envelope.md
- **发布备注：** Reviewer approved; Coordinator auto-push 2026-10-09（六段对齐 durable；Tool-Policy Assembly #2）。Writer 核源与本条目不一致的 4 处（#7474 not planned / #7473 未合；#27201 部分修复；Claude Code Plan 模式下子代理按自身声明模式运行、非天花板；hook 输入 `agent_id` 无文档依据）以正文为准，Scout 周二 PR 更正条目。
- **Scout 更正（2026-10-10，逐条对源复核后改入条目正文）：** (1) #7474 closed not_planned（2026-02-02），PR #7473 closed 未合（2026-03-11）→ 改为只讲机制；(2) #26700 的回归来自已合 PR #26597（2026-05-09）；PR #27201（merged 2026-05-13）只部分修复，后续 PR #27654 未合 → 已改；(3) Claude Code sub-agents 文档「Permission modes」原文：主会话在 `default` / `dontAsk` / `plan` 时子代理按自身声明模式运行 → 删除「Plan 作为 descendant ceiling 下传」「子代理声明的权限不能高于父模式」两处表述；(4) 删除「hook 输入带 `agent_id`」。复核补充：sub-agents 文档确实没有这句，但 hooks 文档（https://code.claude.com/docs/en/hooks ，Common input fields）写明 hook 在子代理内触发时输入带 `agent_id` / `agent_type`——原条目的错误是**来源挂错**，不是事实错误；已发文没用这条，条目也不再引用。另补：#27099 closed not_planned。

### [published] 2026-10-12 | P1 | orphan-tool-call-session-wedge
- **工作标题：** 一次中断，整个会话永久 400：tool_use / tool_result 配对不变量
- **失败面（Host 会话转录 / conversation-state 持久化层，非结果内容保真、非 checkpoint 副作用重放）：** 用户 Esc / 关 tab / 网络断 / 语音插话打断 / 流式响应被 salvage / 并行工具结果非原子写 / compaction 窗口从 `tool_result` 起切 → 持久化历史里留下没有输出的 `function_call` / `tool_use`（或没有前驱的 `tool_result`）→ 之后每次请求都带着同一段毒历史 → Anthropic `tool_use` ids were found without `tool_result` blocks immediately after: … / OpenAI `No tool output found for function call call_XXX.` 400，几小时后重试照样失败；有的路径还把 400 包装成「Connection error」（误判「API 抖动 / 网络问题 / 再加 retry」）
- **为何够深（非科普）：** 主线锁 **配对不变量必须在写入侧闭合**：provider 把 call↔output 配对当作请求合法性的硬约束，而 Host 的 interrupt / abort / salvage / compaction / 并发写入路径各自都可能只写下半对。半对一旦落进持久层（server-side conversation store / `previous_response_id` 链 / 本地 JSONL），重试就是**确定性失败**——这是毒历史，不是瞬时错误。解法分三层：(1) 失败点闭合：abort 时为每个已流出的 call 合成 output；(2) 发送前校验与修复：反向扫描双向孤儿，compaction 切点对齐配对边界；(3) 链式复用守卫：pending call 没完成就不复用 `previous_response_id`。再深一层：合成 output 的**语义诚实**——「aborted_before_exec」和「outcome_unknown」必须区分，后者要和幂等键联动，否则模型以为没执行，就会重做副作用
- **拟用案例 / 对照：**
  1. **BAD#1 Claude Code** 元 issue #6836：汇总 150+ 条重复报告（中断 / 网络 / hook 后 / 并行工具）；维护者回复称原因多样、很难完全消除。#45286：并发工具执行时 JSONL 非原子写，3 个 `tool_use` 只落下 2 个 `tool_result`（根因为报告者推断，标题注明 “Inference”；该 issue 被 github-actions[bot] 于 2026-04-12 按 #31328 的 duplicate 自动关闭，**而 #31328 本身 2026-04-03 被 stale bot 以 not planned 关闭——两条都没有修复**；#31328 的形态是反向孤儿：assistant 的 `tool_use` 条目没写入、`tool_result` 写入了）。#6836 评论还记录了 `/compact` 窗口从 `tool_result` 起切 → `messages.0.content.0: unexpected tool_use_id`（反向孤儿）
  2. **BAD#2 OpenAI Agents JS** #1190：streamed `run()` + `conversationId`，在 `function_call` 流出后 abort → server store 已持久化 call，SDK 的 abort 分支直接 return、不生成 output → 同一 conversation 后续 run 全部 400；fix PR #1241（merged 2026-05-05，关闭 #1190）：跟踪流式事件，为 pending function call 构造 incomplete 的合成结果项，在 abort / 消费方取消时提交，`conversationId` 和 `previousResponseId` 两条续接路径都覆盖
  3. **BAD#3 LiveKit Agents** #5092：语音用户在长工具调用期间插话 → Responses API 400，会话余下全部失败；websocket 路径把 400 包装成 `APIConnectionError`，掩盖真实错误；fix PR #5094（merged 2026-03-13，关闭 #5092）：只在 pending tool calls 完成后才复用 `previous_response_id`（PR 标题只覆盖这一项，不要写成同时修了 websocket 错误包装）
  4. **旁证：** microsoft/amplifier #353：非 completed 的流式响应被 salvage，留下参数截断成 `{}` 的 call 和没有 output 的 call → 会话日志 14 次失败，包括 7 小时后的重试；issue 作者建议丢弃不可解析的 call，并为未执行的 call 合成 error output（仍 open，无修复）。
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
  - https://github.com/anthropics/claude-code/issues/6836 — **主证据（issue，open）**；150+ 重复报告的汇总；COLLABORATOR 回复（2025-09-18）称原因多样、不太可能完全消除；评论含 compaction 反向孤儿复现
  - https://github.com/openai/openai-agents-js/issues/1190 — **主证据（issue，closed completed 2026-05-05）**；abort + `conversationId` 留下孤儿 `function_call`；根因代码段；由已合 PR #1241 修复
  - https://github.com/openai/openai-agents-js/pull/1241 — 旁证：fix PR（merged 2026-05-05），为 pending call 合成 incomplete 结果项
  - https://github.com/livekit/agents/pull/5094 — **主证据（fix PR，merged 2026-03-13）**；pending tool calls 未完成时不复用 `previous_response_id`（关闭 issue #5092）
  - https://github.com/anthropics/claude-code/issues/45286 — 旁证：并发工具执行时 JSONL 非原子写丢 `tool_result`（bot 按 #31328 duplicate 关闭；#31328 not planned 关闭，均**未修复**）
  - https://github.com/livekit/agents/issues/5092 — 旁证：语音插话打断工具调用；400 被包装成连接错误
  - https://github.com/microsoft/amplifier/issues/353 — 旁证（open）：salvage 不完整流式响应留下未配对的 call
- **备注：** Gate PASS ready — Thu light refill 2026-10-08。写稿禁令：#6836 评论里「1,571 sessions / 8,007 orphaned」是社区逆向统计（指向 #33949），引用必须注明非官方；不要声称 Anthropic 已彻底修复；合成 output 的 status 字段名以各 SDK 实际实现为准，正文用中性描述（openai-agents-js PR #1241 原文叫 incomplete synthetic `function_call_result` item）。P1。**Sat 2026-10-10 严格复核：PASS 保持 ready**——3 条主证据都成立：#6836 open（COLLABORATOR 回复原话已核）；#1190 closed completed，修复 PR #1241 已合；PR #5094 已合并关闭 #5092。补记关闭状态：#45286 是 bot duplicate 关闭（→ #31328），amplifier #353 仍 open、无修复；#5092 里的 websocket 错误包装是报告中的次要 bug，#5094 未声称修复它。**周一首推。**
- **已发文：** posts/orphan_tool_call_session_wedge.md
- **发布备注：** Reviewer approved; Coordinator auto-push 2026-10-12（六段对齐 durable；Agent Session-State Integrity #1）。Writer 核源与本条目不一致的 3 处（#45286 duplicate → #31328 not planned，未写成已修；Azure #46092 原报告是配对完整却被拒，未引用；Anthropic 错误原文改引 #6836 中的报错）以正文为准，Scout 周二 PR 更正条目。
- **Scout 更正（2026-10-16，逐条对源复核后改入条目正文）：** (1) #45286 closed 的原因是 github-actions[bot] 按 duplicate 关闭 → #31328；#31328 closed **not planned**（2026-04-03，stale bot），所以两条都**未修复**——条目原文只写了「被 bot 按 duplicate 关闭」，没写目标未修；(2) Azure SDK #46092 的原报告是：完整的 function_call / function_call_output 配对已在 conversation 里，Azure 端仍报 `No tool output found for function call`（OpenAI 端不复现，约 7–8/10 出现，open，label question）——是**配对完整却被拒**，不是「失败 turn 持久化半对」→ 引用错误，已从旁证和参考线索删除；(3) 条目原先给 Anthropic 错误写成无反引号的 `tool_use ids were found without tool_result blocks`，该串在 #6836 **正文**里没有（正文只有搜索短语 “Each tool_use block must have a corresponding tool_result block in the next message”）；逐字原文在 #6836 评论（soaringk，2026-02-05）：`messages.1: \`tool_use\` ids were found without \`tool_result\` blocks immediately after: toolu_…. Each \`tool_use\` block must have a corresponding \`tool_result\` block in the next message.`；反向孤儿原文在评论（TweedBeetle，2026-02-20）：`messages.0.content.0: unexpected \`tool_use_id\` found in \`tool_result\` blocks: toolu_…. Each \`tool_result\` block must have a corresponding \`tool_use\` block in the previous message.`；OpenAI 侧原文在 openai-agents-js #1190 / livekit #5092：`No tool output found for function call call_XXX.`——引用错误串只用这些逐字文本。复核通过项：#6836 open、COLLABORATOR 回复（2025-09-18）原话属实；#1190 closed completed（2026-05-05，PR #1241 已合）；livekit PR #5094 已合并并关闭 #5092（websocket 错误包装是 #5092 里的次要 bug，#5094 未声称修复）。

### [published] 2026-10-16 | P2 | compaction-drops-pinned-instructions

- **发布备注（2026-10-16）：** Reviewer Approve 后发布为 `posts/compaction_drops_pinned_instructions.md`（Session-State Integrity #2）。正文按原始来源写：#28736 仅写报告人感谢修复、未找到关联 PR；#75759「重复执行」标为推断；#14941 引用的是第二句 continuation 提示。
- **工作标题：** Compaction 之后 Agent 忘了「先给我看计划」：被摘要掉的不是历史，是约束
- **失败面（Host 上下文压缩层，非 LTM 写入、非单次工具结果裁切）：** 长会话触发 auto / manual compaction → summarizer 把 AGENTS.md / CLAUDE.md 项目规则、用户最近的**条件指令**（「先修订计划给我审，再实现」）、已完成动作当普通历史一起 paraphrase → 压缩后 agent 直接实现、违反项目规则、重做已完成步骤（进度 97% 掉回 42%）（误判「模型不听话 / 指令写得不够大声 / 再加一遍 IMPORTANT」）
- **为何够深（非科普）：** 主线锁 **约束 vs 叙事 vs 账本分层**：压缩是有损摘要，适合叙事（做过什么的大意），不适合约束（规则、条件门控、承诺），也不适合账本（已完成的副作用）。三类内容需要三种保留方式：pinned verbatim 重注入（规则源以快照形式，每个压缩边界恰好注入一次）、结构化门控状态（`awaiting_review` 这类状态不能交给摘要模型去「解释」）、外部进度账本（已完成步骤由 harness 写，不靠摘要记）。机制对照：Codex PR #29810 把 AGENTS.md 作为持久化 WorldState，初始上下文、每请求更新和 compaction 上下文同源构建，resume / fork 时指令变更只注入一次替换；Claude Code 在压缩边界有 `InstructionsLoaded`（load_reason=`compact`）和 SessionStart `compact` matcher。不是「context window 是什么」入门
- **拟用案例 / 对照：**
  1. **BAD#1 条件指令被压平（Claude Code）** #23776：plan-review 迭代中触发 compaction → 摘要保留了技术内容，丢掉「先审再实现」这个条件 → 压缩后直接改代码；摘要里的「Pending Tasks」反映的是模型的解读，而不是用户原话——以上是报告者的根因推断，非维护者确认。场景是 bypass permissions 下对话式迭代计划，**不是** Claude Code 的正式 plan mode。#23776 由报告者自己按 #14941 的 duplicate 关闭（2026-02-06；GitHub 显示 completed 只是自关，不代表修复）。#14941 的症状**不完全相同**：压缩前最后一条用户消息是「目录结构选 A 还是 B」的问句，压缩后收到的 continuation prompt 在 issue 里是两句（第一句 “Please continue the conversation from where we left it off without asking the user any further questions.”，第二句 “Continue with the last task that you were asked to work on.”）；本条目只引用 “Continue with the last task…” 一句（即报告者标为根因的那句），不要写成 prompt 只有这一句，也不要展开未引用的内容，agent 直接开始实现（同样是报告者的推断）；#14941 于 2026-03-09 被 github-actions[bot] 以不活跃关闭（not planned）——**未修复**。关闭方式汇总（2026-10-16 对 API 复核）：#23776 = 报告者本人自关（state_reason=completed，不是修复，无关联 PR）；#14941 与 #24460 = stale bot 以 not_planned 关闭
  2. **BAD#2 规则源被摘要（Codex）** #2927 / #5772：`/compact`（含 auto）之后 AGENTS.md 不再注入（两条都被 contributor 以「stale / old issue」关闭，未说明修复）；#25792（open）：有用户报告压缩后模型自报进度从约 97% 掉到约 42%，并怀疑 AGENTS.md 进度规则丢失、已完成的工作可能被重开（原文是「appeared to restart or regress」「may repeat」，是报告者的怀疑，不是已证实的丢规则；该 issue 下 CONTRIBUTOR 评论认为自报进度本身就是任意的、建议用 ExecPlan 文件）；Claude Code #24460 是 enhancement 请求（CLAUDE.md 压缩后可能丢；bot 因不活跃以 not planned 关闭，**不是**对丢失的复现）。**Codex 现版本是否仍会丢 AGENTS.md 并未证实**：#46186 正文明说该提案「does not establish that compaction removed the original instructions」，且指出 `compact.rs` 已有初始上下文重注入路径；#2927（0.27.0）/ #5772（0.49）是旧版本报告
  3. **BAD#3 执行账本丢失（Claude Code）** #75759（open）：同一活跃会话内压缩后，agent 否认 / 找不到自己早先写过的备份文件，用户得把早前对话贴回去证明（报告原话是 “denies doing it, or says it cannot find evidence”）。报告里**没有**说它重跑了步骤（正文只泛泛提到「Time is wasted re-doing or re-verifying completed steps」，没有指出哪一步被重跑），所以「重复执行」仍是我们的推断；「重做 → 非幂等副作用」是本文的推论（一条评论称会重试已完成步骤，无数据），写稿时要标成推论
  4. **GOOD：** Codex PR #29810（AGENTS.md 作为持久 WorldState；compaction 上下文与请求同源；resume / fork 指令变更恰好注入一次）| Codex #46186 提案（open）：快照 verbatim、每个压缩边界恰好恢复一次；该 issue 下有非维护者评论称眼下可用 SessionStart `compact` hook 重放（社区说法；Codex #28736 曾报告 mid-turn 自动压缩后该 hook 被推迟到后续 turn；2026-07-20 由 maintainer 关闭（completed），报告者在末条评论感谢修复，时间线未找到关联 PR——写稿只写「报告者感谢修复，未找到关联 PR」，不描述修复内容，引用前需按当前版本复核）| Claude Code hooks：SessionStart `compact` matcher（可重注入）、`PreCompact`（可阻止压缩）/ `PostCompact`、`InstructionsLoaded`（`load_reason` = `compact`，压缩后重新加载指令文件时触发；**无 decision control**，只能做观测 / 审计）| 门控状态与进度账本放到 harness 外部
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
  - https://github.com/anthropics/claude-code/issues/23776 — **主证据（issue；报告者自关为 #14941 的 dup，#14941 被 stale bot 以 not planned 关闭，未修复）**；条件指令「先审再实现」被压平成「实现」（根因为报告者推断）
  - https://github.com/openai/codex/issues/25792 — **主证据（issue，open；弱：报告者怀疑 + 模型自报进度，评论有质疑）**；压缩后 AGENTS 规则可能失效、进度 97%→42%（PR #29810 合入后仍 open）
  - https://github.com/openai/codex/pull/29810 — **主证据（fix PR，merged 2026-06-25）**；AGENTS.md 作为持久 WorldState，compaction 上下文同源，resume / fork 恰好注入一次（注：该 PR 的主要动机是 deferred executor 环境变更，compaction 同源只是其中一项，写稿时不要夸大）
  - https://github.com/openai/codex/issues/2927 — 旁证：`/compact` 后 AGENTS.md 被忽略（以 stale 关闭，非修复）
  - https://github.com/openai/codex/issues/46186 — 旁证（open 提案）：快照 verbatim、每个压缩边界恰好恢复一次；SessionStart `compact` hook 方案来自社区评论
  - https://github.com/anthropics/claude-code/issues/24460 — 旁证：CLAUDE.md 在 `/compact` 后丢失（不活跃 not planned 关闭）
  - https://github.com/anthropics/claude-code/issues/75759 — 旁证（open）：压缩后否认 / 找不到本会话已执行的动作（未报告重跑）
  - https://code.claude.com/docs/en/hooks — GOOD 文档：SessionStart `compact` matcher、`PreCompact` / `PostCompact`、`InstructionsLoaded` load_reason `compact`（无 decision control，仅观测；Claude 经「Project instructions」设置直接读 `AGENTS.md` 时不触发）
- **备注：** Gate PASS ready — Thu light refill 2026-10-08。写稿禁令：不要把各家压缩实现细节写成官方原理（多数只能从 issue 和文档推断）；97%→42% 是单个用户报告，引用时写「有用户报告」；不要写成「教你写 CLAUDE.md」的科普。P2（排在前两条之后）。**Sat 2026-10-10 严格复核：PASS 保持 ready**——主证据中 PR #29810 已合（2026-06-25）；#25792 open；#23776 实为 dup 关闭（→ #14941 not planned），GitHub 显示的 completed 不代表修复。已在正文对应处更正：#2927 / #5772 是 stale 关闭、#24460 是不活跃关闭、#46186 的 hook 方案是社区评论、`InstructionsLoaded` 只能观测不能重注入。新增写稿禁令：97%→42% 是模型**自报**的进度数（#25792 下有 contributor 质疑其意义），只能当症状，不能当量化证据；不要说 Claude Code / Codex「已修复」压缩丢约束。**Fri 2026-10-16 严格复核（读 issue 正文 + 评论 + 关闭状态）：PASS 保持 ready，但证据偏弱，列为三条 ready 里最需要谨慎措辞的一条**——#23776 是清晰复现（但根因为报告者推断）；#25792 只是怀疑 + 自报进度；PR #29810 已合（2026-06-25）但主要动机是 deferred executor 环境变更，不是修「压缩丢约束」。新增写稿禁令：(a) 不得写「Codex 压缩后会丢 AGENTS.md」为现状——#46186 自己声明未证实，#2927 / #5772 是 0.27 / 0.49 旧版本、stale 关闭、GitHub 的 completed 不代表修复；(b) #23776 与 #14941 症状不完全相同（条件指令被压平 vs 问句后被「继续任务」推去实现），别写成同一个 bug；(c) #75759 报告的是「否认 / 找不到」，不是「重跑」；(d) #24460 是 enhancement 请求、不是复现；(e) 文档引文（hooks：SessionStart `compact` matcher、`PreCompact` 可阻止压缩、`InstructionsLoaded` 的 `load_reason=compact` 且无 decision control、经 Project instructions 直读 `AGENTS.md` 时不触发）已对照 code.claude.com/docs/en/hooks 原文核对，只作旁证。

### [published] 2026-10-14 | P1 | layered-retry-amplification
- **工作标题：** 一个 429 打出 12 个请求：Agent 的重试没有唯一 owner
- **失败面（Provider client / Agent loop 重试策略层，非幂等重放、非 handoff 环）：** Agent 外层 loop 已有重试（尊重 `Retry-After`、有 backoff）→ 底下的 provider SDK 客户端用默认 `max_retries` 再静默重试一遍（自带短 backoff）→ 一次 429 被放大成「外层次数 × 内层次数」个上游请求，全部打在同一个限流桶上；终态错误（如 `403 ai_credits_limit_exceeded`）也被内层重复打；外层把 `Retry-After` 截到比真实 reset 窗口还短 → 提前重试再次触发限流 → Agent 看起来挂住（误判「provider 抖动 / 把 retry 次数调大 / 加并发」）
- **为何够深（非科普）：** 主线锁 **重试所有权 + 错误分类**：(1) 放大是乘法，不是加法：每层各自「合理」的 1+N 次相乘；nanobot 在恒返回 429 的 mock 端点上实测外层 1+3 次叠加 SDK 默认重试 = 12 个请求，关掉 SDK 重试后 = 4 个（3.0x）。(2) 两层 backoff 语义不同：外层按 `Retry-After` 等，内层按自己的短 backoff 打，消耗的是同一个令牌桶；外层 `Retry-After` cap 低于 reset 窗口时，「尊重 Retry-After」形同虚设。(3) 分类缺失：429 至少有 WAIT（等）/ CAP（降并发）/ STOP（额度耗尽，不重试）三种语义（nanobot #2760 讨论），终态错误不该进任何一层重试。修法不是「调小次数」，而是**每条调用链只有一个 retry owner** + owner 处做错误分类 + 跨层共享的 retry budget。「唯一 owner」也不等于「处处设 0」：hermes 修复刻意保留了不被外层 loop 包裹的 `auxiliary_client` 的 SDK 重试。不是「指数退避 + jitter」入门
- **拟用案例 / 对照：**
  1. **BAD#1 nanobot（乘法放大）** issue #2760 + fix PR #2759：`LLMProvider._run_with_retry`（`retry_mode="standard"`）叠加 `AsyncOpenAI` / `AsyncAnthropic` 默认 `max_retries=2`；mock 恒 429 下 12 vs 4 个请求；修复为 SDK 构造处 `max_retries=0`（OpenAI-compat、Anthropic；合入 diff 也覆盖 Azure OpenAI provider，并带回归测试）。#2760 评论里的 WAIT / CAP / STOP 分类出自**社区评论者**（SirBrenton，无项目关联），不是维护者的方案，也不是这次修复的内容；#2762（2026-04-06 合入）做的是结构化重试判定（408 / 409 / timeout / connection、`x-should-retry`、`retry-after`），并非 WAIT / CAP / STOP
  2. **BAD#2 hermes-agent（Retry-After 被截断 + 内层双发）** issue #26293 → fix PR #53918：SDK 默认重试在外层 rate-limit loop 内部双发；外层 `Retry-After` cap 120s（代码在 `agent/conversation_loop.py`；issue 里写的是 `run_agent.py:14462`），而报告者的 Anthropic Tier-1 input-token bucket 约 171s 才 reset → 软限流升级成请求次数耗尽，Agent 看起来挂住。修复：三个 Anthropic 客户端构造器 + OpenAI/aggregator 的 `create_openai_client` 统一 `max_retries=0`，cap 120s→600s；`auxiliary_client` 不被外层 loop 包裹，刻意保留 SDK 重试
  3. **BAD#3 gh-aw（终态错误被重试）** fix PR #47237：Claude Code CLI 内的 Anthropic SDK 在终态 `403 ai_credits_limit_exceeded` 上每次 harness attempt 最多发 11 次无效请求（`attempt 1/11`）；修复：合入 diff 只在 agent 阶段通过 `ANTHROPIC_MAX_RETRIES` 关掉 SDK 内层重试，detection 路径没有外层 retry 包裹故保留默认；另加 3 个 `harness_retry_guard` 回归测试（只改测试文件）。PR 描述仍写「adds the explicit pattern」，但合入 diff **没有**改 `harness_retry_guard.cjs`、没有新增匹配模式（评审时删掉，原有更宽的模式已能匹配）
  4. **GOOD：** 每条调用链一个 retry owner（在客户端构造处显式关掉内层，或外层不重试，二选一并写进代码注释与测试）| owner 处分类：WAIT（按 `Retry-After`，cap 不低于观测到的 reset 窗口，超出预算就放弃并上报）/ CAP（降并发再试）/ STOP（额度、鉴权、`400 invalid_request` 等终态，0 次重试直接上报）| retry budget 按作业 / 会话共享，子调用不各自重新计数 | 指标 `upstream_requests / logical_calls`（放大比）告警
- **§4 业务线：** 同一夜间批处理作业 `NIGHTLY-OPS-0917`（Agent 逐条分析告警，每条一次 LLM 调用，并发若干）。**BAD v1**：外层 1+3 次 + SDK 默认 2 次内层 → 限流开始后每个逻辑调用打出 12 个上游请求，并发一乘，限流桶永远回不满（回扣 §3.1 唯一 owner）。**BAD v2**：关掉 SDK 重试，外层也尊重 `Retry-After`，但 cap 截在 120s，而桶约 171s 才 reset → `NIGHTLY-OPS-0917` 的每次重试都落在 reset 之前，继续 429（回扣 §3.2 cap 不低于 reset 窗口）。**BAD v3**：额度耗尽返回 403 → 外层仍按可重试处理，作业跑满全部重试才失败、零产出（回扣 §3.3 STOP 分类）。**GOOD**：`NIGHTLY-OPS-0917` 的 client 构造处 `max_retries=0`；外层 owner 分类 WAIT / CAP / STOP，403 额度立刻终止作业并告警；作业级 retry budget；`upstream_requests / logical_calls` 指标记录每次运行的放大比（回扣 §3.4 预算 + 可观测）
- **§5 可注入失败点：**
  1. **注入：** mock provider 恒返回 429 → **期望：** 每个逻辑调用的上游请求数 = 外层上限（不是乘积）；放大比指标 ≤ 外层上限
  2. **注入：** 429 带 `Retry-After: 180` → **期望：** 下一次请求间隔 ≥180s，或超出预算即放弃并上报；不被截断到更短
  3. **注入：** 返回 `403` 额度耗尽 / `400 invalid_request` → **期望：** 0 次重试，首个 attempt 即上报终态错误；作业停止派发新调用
- **领域标签：** Agent Host Runtime / Provider Client / Retry Policy & Backpressure
- **专题归属：** **Agent Runtime Failure Handling**（新建 #1：重试所有权与错误分类。理由：现有系列都不覆盖「调用失败之后谁来重试、按什么分类」这一层；后续可接 retry budget 跨子代理传递 / circuit breaker）
- **相关已发文 / 边界：**
  - vs `agent-write-idempotency`：那篇 = 一次重试是否安全（双写）；本文 = 重试有几层、谁拥有、按什么分类。不重讲幂等键
  - vs `multi-agent-closed-loop-handoff`：那篇 = 路由环缺终止谓词；本文 = 单条调用链内的重试乘法；「bill before brake」只一句互链
  - vs `durable-agent-execution`：那篇 = 进程死后重放副作用；本文 = 进程活着时的重复上游请求
  - vs ready `orphan-tool-call-session-wedge`：那篇已主张 `400 invalid_request` 属于不可重试的历史损坏；本文只把它归入 STOP，不复述毒历史
- **参考线索：**
  - https://github.com/HKUDS/nanobot/pull/2759 — **主证据（fix PR，merged 2026-04-04）**；SDK `max_retries=0`；mock 429 下 12→4 请求
  - https://github.com/NousResearch/hermes-agent/pull/53918 — **主证据（fix PR，merged 2026-06-28；Fixes #26293）**；SDK 重试归零 + `Retry-After` cap 120s→600s；保留 `auxiliary_client` 重试
  - https://github.com/github/gh-aw/pull/47237 — **主证据（fix PR，merged 2026-07-22；Fixes #47217）**；终态 403 上的 `attempt 1/11` 重试风暴；合入 diff = agent 阶段 `ANTHROPIC_MAX_RETRIES` + 3 个回归测试，无新增 guard 模式（Copilot 代理作者，pelikhan 合入）
  - https://github.com/HKUDS/nanobot/issues/2760 — 旁证（closed completed 2026-04-14）：429 WAIT / CAP / STOP 分类讨论（出自社区评论者，非维护者）
  - https://github.com/NousResearch/hermes-agent/issues/26293 — 旁证（closed completed，经 PR #53918；另两条 PR #26311 / #35955 已关未合）：根因报告，含 Tier-1 约 171s reset（报告者观察值）
- **备注：** Gate PASS ready — Sat round 2026-10-10（Alice 触发）。写稿禁令：「SDK 内层 backoff 忽略 `Retry-After`」是 hermes issue / PR 的原话，只能写成「该项目当时的版本里」，不要写成各 SDK 的普遍事实；12→4 是 nanobot 在 mock 429 端点上的实测，不是生产数据；约 171s 是报告者账户的观测值，不是官方限额；gh-aw 合入代码的注释写「limit … to 1」而赋值是 `"0"`，评审回复又说 lock 文件里是 1——**正文不要引用具体数值**，只写「agent 阶段关闭或限制 SDK 内层重试，detection 路径保留默认」；§4 不要编具体请求数 / 时长，写成相对量；不写成「指数退避 + jitter」科普。P1。
- **已发文：** posts/layered_retry_amplification.md
- **发布备注：** Reviewer approved; Coordinator auto-push 2026-10-14（六段对齐 durable；Agent Runtime Failure Handling #1）。Writer 核源与本条目不一致的 4 处（gh-aw #47237 未新增 harness 匹配模式、仅加 3 个回归测试；nanobot #2760 WAIT/CAP/STOP 拆分出自社区评论者；#2759 无 Azure 在 review 中加入的证据；hermes 120s 上限改在 `agent/conversation_loop.py`，#47217 为自动生成报告）以正文为准，Scout 10/14 更正 PR 处理。
- **Scout 更正（2026-10-16，逐条对源复核后改入条目正文）：** (1) gh-aw #47237：合入 diff 只在 agent 阶段设 `ANTHROPIC_MAX_RETRIES`（`pkg/workflow/claude_engine.go`，代码注释写 “limit … to 1”，赋值是 `"0"`）+ `harness_retry_guard.test.cjs` 加 3 个测试；PR 描述里「adds the explicit pattern to `AI_CREDITS_EXCEEDED_PATTERNS`」没有落进合入 diff（`harness_retry_guard.cjs` 未改）→ 删掉条目里「补上匹配模式」；另外 issue 与 PR 对「11」口径不一致（issue：引擎重发同一请求至多 11 次；PR：每次 harness attempt 至多 11 个 HTTP 请求），正文不引；(2) nanobot #2760 的 WAIT / CAP / STOP 出自社区评论者 SirBrenton（NONE）；pikaxinge 的 PR-B 计划只有 WAIT / STOP，已合的 #2762 是结构化判定；(3) nanobot #2759：合入 diff 含 `azure_openai_provider.py` + Azure 回归测试，来自合并前（2026-04-04）的提交 65f9ee8「fix(providers): disable Azure SDK retries by default」（作者 Xubin Ren；PR 由 Re-bin 合入），PR 描述只列 OpenAI-compat / Anthropic；是否在评审讨论中加入无记录 → 条目原写的「评审时扩到 Azure」改为只写「也覆盖 Azure OpenAI provider」；(4) hermes 120s cap 的修改在 `agent/conversation_loop.py`（issue 写的 `run_agent.py:14462` 是旧位置）；PR #53918 是对 @konsisumer 的 #35955 的 salvage，另加 OpenAI / aggregator 的 `create_openai_client` 同类修复；`auxiliary_client` 保留 SDK 重试；(5) gh-aw #47217 是 github-actions[bot] 的 `[agentrx-optimizer]` 每日自动生成的失败分析报告，不是人写的 bug 报告（证据为其引用的 run，引用时写明）；(6) 复核通过项：nanobot 12→4 为 PR / issue 里 mock 恒 429 的实测；hermes 的「SDK 退避忽略 Retry-After」是 issue / PR 原话；171s 是报告者观察值。

### [published] 2026-10-19 | P2 | streaming-tool-call-index-collision

- **发布备注（2026-10-19）：** Reviewer Approve 后发布为 `posts/streaming_tool_call_index_collision.md`（Session-State Integrity #3）。正文以原始来源为准，与本条目的出入待 Scout 周二 PR 更正：「name 加第一段参数」出自 #3203 复现评论而非 #3232；#3203 由报告人 2026-05-12 自行关闭并入 #3201（API state_reason=duplicate，正文只写自行关闭并入）；#3201 模型名为 "Kimi 2.6"；LiteLLM #21331 不写关闭日期；#21337 合入 staging 分支，后续发布版本未核；#33678 仅确认 #37792 仍 open；unsloth #10059 的粘连工具名来自 PR 描述，不写 call 数。
- **Scout 更正（2026-10-21，按发布备注的 7 处逐条对 API / 页面复核后改入条目正文）：** (1) **确认并改出处**：「name 加第一段参数在同一个 SSE event」出自 #3203 正文「To Reproduce」脚本的代码注释 `# (e.g. tool name + first argument fragment in one SSE event)`（2026-05-06），#3201 的首块数据是同一形状；PR #3232（closed 未合，2026-09-10 UTC 关闭）的描述里也有近似句 “a tool-call name and its first argument fragment in one SSE event”——条目原引语在 #3232 里确实存在，但 #3232 是晚于 #3203 的未合竞争 PR，出处改为 #3203；Writer 说的「复现评论」准确说是 issue 正文复现脚本的注释，不在评论区。(2) **#3203 是 duplicate**：API `state_reason=duplicate`，closed_at 2026-05-12T04:38:08Z（北京时间同日 12:38），`closed_by` = 报告人 hrolfurinn；页面状态徽标显示 “Closed as duplicate”，页面数据 duplicateOf = #3201；报告人关闭时留言 “added this extra context to #3201. attempted fixes had made tracking messy.” → 条目写成「报告人自行以 duplicate 关闭、并入 #3201」。发布备注里「页面上没有 duplicate 标记」不成立；正文只写「自行关闭并并入」仍然正确，不用改。#3201 本身 closed completed（2026-09-10，经已合 PR #3425）。(3) **确认**：#3201 原文是 “Kimi 2.6”（所附 recipe 链接指向 `moonshotai/Kimi-K2.6`），条目原写的 “Kimi K2.6” 已改。(4) **LiteLLM #21331**：API 确认 closed、state_reason=completed、closed_at 2026-03-02T22:05:04Z、closed_by_pull_requests → #21337（MERGED）——关闭日期其实可由 API 确认，条目按 UTC 写；正文不写日期也不算错。(5) **确认**：#21337 的 base = `litellm_oss_staging_02_27_2026`，merged_at 2026-02-27T20:54:19Z；之后进入哪个正式发布版本未核，条目已注明。(6) **#33678 关联 PR**：#37792 open、未合（确认）；#33682（closed 未合，2026-10-03T22:32Z）与 #39012（closed 未合，2026-10-03T22:41Z）这次经 API 读到，且都列在 #33678 的 closed_by_pull_requests 里，不是只在时间线里出现——条目原写的「已关未合」是对的，Writer 那边是没核到，不是事实冲突；正文不引用这两条也没问题。(7) **unsloth #10059，四点都确认**：`web_fetchweb_searchweb_fetch` 和「server 复用同一个 slot」只出现在 PR 描述里（issue 正文只说多个调用解析到同一个 slot，讲的是客户端）；PR 描述写 “the four calls … the three tool names”，它自己的复现输出又列出 4 个名字，口径不一致 → 条目删掉「4 个调用」，不写 call 数；PR 原文 “No live vLLM or LiteLLM endpoint was involved; the reporter's stream is replayed from the issue verbatim.”；issue 环境是 LiteLLM 代理后的 vLLM，issue 只泛称 “(vLLM does)”，没有说明本例中无 id 增量是哪一层发出的。
- **工作标题：** 两个并行工具调用拼成一个 `{"path":"a.rs"}{"path":"b.rs"}`：流式 tool_call 组装的身份键坍缩
- **失败面（流式响应 → tool_call 组装层，非结果截断、非历史配对缺失）：** 模型一轮并行发出 2+ 个工具调用 → 上游某一层（Responses→Chat 流式桥、`ollama_chat` 转换、推理服务）给不同调用发同一个 `index`，或首个 chunk 里同一 `index` 出现两条 → 客户端累加器按 `index` / 物理位置拼 `arguments` → 得到串接的 `{...}{...}`、拼在一起的工具名（`web_fetchweb_searchweb_fetch`，匹配不到任何工具，静默不执行——出自 unsloth PR #10059 描述，不在 issue 正文）、或丢了前缀的 `: "London"}` → 坏 call 被写进历史，之后每一轮都重放，provider 端 `json.loads` 抛 `Extra data`，表面报成 `APIConnectionError`（误判「模型吐了坏 JSON / 网络问题 / 再加一层 JSON repair」）
- **为何够深（非科普）：** 主线锁 **流式组装的身份键**：Chat Completions 风格的流式 tool_call 靠 `index` 把后续 delta 归到同一个调用上，任何一层把它压成常量、重算、或按物理位置合并，两个调用的身份就坍缩成一个。三处失效点各有一个已合修复：(1) **生产方**——桥接层硬编码 `index=0`，修复改为映射源协议的 `output_index`（LiteLLM PR #21337）；(2) **消费方**——SDK 累加器的首片快路径不按逻辑 `index` 合并（openai-python #3201 → PR #3425）；(3) **持久化**——坏 arguments 进了历史，下一轮才爆，线程只能新开（unsloth #9807 正文 + PR #10059 描述）。GOOD 不是 JSON repair 启发式（在 `}{` 边界切分只能救串接形态，救不了丢前缀形态），而是：身份冲突当协议错误检出、执行前逐个 call 校验 arguments、不可解析的 call 不执行也不以「正常 call」形态写进历史、错误分类为协议错误而非连接错误
- **拟用案例 / 对照：**
  1. **BAD#1 消费方累加器（openai-python）** #3201：首个 chunk 中两条 `index: 0` 的 `tool_calls` 被原样存成两个物理元素，后续片段只合进 `[0]` → `arguments` 残缺、不可解析；#3201 的报告者是在 vLLM OpenAI 兼容服务 + speculative decoding 下跑 "Kimi 2.6"（issue 原文写法；所附 vLLM recipe 链接指向 `moonshotai/Kimi-K2.6`，正文按原文写 "Kimi 2.6"）。同类报告 #3203 的报告者在 vLLM 开启 speculative decoding 时观察到；#3203 于 2026-05-12 由**报告人自行以 duplicate 关闭、并入 #3201**（API `state_reason=duplicate`、`closed_by` = 报告人；页面显示 “Closed as duplicate”，duplicateOf = #3201；报告人留言 “added this extra context to #3201”）。**注意：这两条 `index: 0` 是同一个调用的片段**（一条带 id / name，一条带首段 arguments）——「name 与首段 arguments 在同一个 SSE event」这一描述出自 #3203 正文复现脚本里的代码注释（`# (e.g. tool name + first argument fragment in one SSE event)`），#3201 的首块数据也是同一形状；未合的竞争 PR #3232 描述里复述了近似句，**不以 #3232 为出处**。不是两个并行调用——这是消费方累加器没按逻辑 index 合并，不是「身份冲突」。fix PR #3425（2026-09-10 合入，关闭 #3201）让 indexed list 的首片也走合并逻辑，同时修 `_assistants.py` 和 chat completion snapshot 初始化路径
  2. **BAD#2 生产方桥接（LiteLLM）** #21331：Responses API → Chat Completions 流式桥把所有并行调用都发成 `index=0`；fix PR #21337 改用 `output_index`（该 PR 合入的是 staging 分支 `litellm_oss_staging_02_27_2026`，2026-02-27 UTC；之后进入哪个正式发布版本**未核**）；#21331 closed completed（API：closed_at 2026-03-02 UTC，closed_by_pull_requests 指向已合的 #21337）。同类未修：#33678（open，带 stale 标签；关联修复 PR #37792 仍 open；#33682 / #39012 经 API 核实均为 closed 未合并（2026-10-03 UTC 关闭），二者都列在 #33678 的 closed_by_pull_requests 里；`ollama_chat` 流式每个调用都发 `index=0`；Ollama 本身在 `function.index` 给对了 0/1，LiteLLM 丢弃后重算）→ 客户端拼出 `{"path": "a.rs"}{"path": "b.rs"}` 写进历史 → 下一轮 `transform_request` 的 `json.loads` 抛 `Extra data`，被报成 `litellm.APIConnectionError`
  3. **BAD#3 持久化后反复重放（unsloth Studio）** fix PR #10059（2026-08-31 合入，Fixes #9807）：#9807 自己定位的根因在**客户端** Studio 的流式累加（`chat-adapter.ts` 按 id、无 id 时回落 index 取 slot，再字符串拼接；issue 原文是「多个调用解析到同一个 slot（无 id、按 index 的 delta）」），非流式请求同一后端返回的是干净的分开调用；issue 存下的 `argsText` 是多段 JSON 对象串接成一个不可解析的 arguments。以下两点出自 **PR 描述**、不在 issue 正文：「服务端以无 id、按 index 的 delta 流式发并行调用，复用同一个 slot」的概括，以及「工具名拼成 `web_fetchweb_searchweb_fetch`、匹配不到工具、静默不执行」。**不写 call 数**：PR 描述先写 “the four calls … the three tool names”，它自己的复现输出又列出 4 个名字，口径不一致。PR 的复现不是线上端点，而是逐字重放 issue 里的流（PR 原文：“No live vLLM or LiteLLM endpoint was involved; the reporter's stream is replayed from the issue verbatim.”）。issue 的环境是 LiteLLM 代理后面的远程 vLLM，issue 只泛称 vLLM 会发无 id、按 index 的增量（“(vLLM does)”），**没有说明本例中无 id 增量是哪一层上游发出的**。坏 blob 被持久化并在之后每一轮重放，直到后端以 HTTP 400 `Extra data: line 1 column 51 (char 50)` 拒绝，线程只能新开（issue 另注明：同一端点上 gpt-oss-120b 能容忍这种历史，即 400 里有后端严格性的成分）。修复在 JSON 对象边界切分（启发式，PR 自述已知限制：名字后缀跨 delta 到达时无法区分、相邻的顶层数组仍算一个调用；讲 tradeoff）
  4. **GOOD：** 累加器按逻辑 `index` 合并（含首片），并检测「同 `index` 不同 `id`」→ 报 `stream_protocol_error` | bridge 从源协议的唯一身份（`output_index` / `function.index` / item id）映射，不重算 | 执行前每个 call 做 `json.loads` + schema 校验，失败则不执行，回填结构化错误 output（与 `orphan-tool-call-session-wedge` 的配对不变量一致）| 历史里不以正常 call 形态持久化不可解析的 arguments | 解析 / 协议错误单独归类，不并入连接错误、不进重试 | 指标：按 provider 统计 `tool_args_parse_fail_rate`
- **§4 业务线：** 同一代码重构会话 `sess_RFX-552`，模型一轮并行发出 `read_file(a.rs)` 和 `read_file(b.rs)`，经代理转到自托管模型。**BAD v1**：桥接层两个调用都发 `index=0` → 客户端拼成一个 call，arguments = `{"path":"a.rs"}{"path":"b.rs"}` → 解析失败但坏 call 照样写进 `sess_RFX-552` 的历史 → 下一轮 `Extra data`，被报成连接错误，重试无效，会话报废（回扣 §3.1 身份键 + §3.3 坏 call 不入历史）。**BAD v2**：补丁加了「按 `}{` 切分」的 JSON repair；`sess_RFX-552` 换到另一个推理后端后首片出现重复 `index`，arguments 变成丢前缀的 `: "b.rs"}`，repair 无从下手（回扣 §3.2 不靠启发式）。**GOOD**：累加器按 (`index`, `id`) 检出身份冲突即报 `stream_protocol_error`；每个 call 执行前 parse + schema；不可解析的 call 不执行，回填错误 output 保持配对；该错误不进重试（回扣 §3.4 错误分类）
- **§5 可注入失败点：**
  1. **注入：** 回放一段录制的 SSE，首个 chunk 含两条 `index: 0`（一条带 name，一条带首段 arguments）→ **期望：** 组装出的 arguments 与非流式结果逐字节一致
  2. **注入：** 桥接层把两个并行调用都标为 `index=0`、`id` 不同（或无 `id`）→ **期望：** 检出身份冲突，按 id 拆开或整轮报 `stream_protocol_error`；绝不产出 `}{` 串接的单个 call
  3. **注入：** 某个 call 的 arguments 不可解析 → **期望：** 不执行该工具；历史里该 call 配有结构化错误 output；下一轮请求正常，不出现 `Extra data` / 连接错误重试
- **领域标签：** Agent Host Runtime / Streaming / Tool-Call Protocol
- **专题归属：** **Agent Session-State Integrity**（续篇 #3：组装不变量——call 在进历史之前就已经坏了。#1 `orphan-tool-call-session-wedge` = 配对不变量；#2 `compaction-drops-pinned-instructions` = 语义保真）
- **相关已发文 / 边界：**
  - vs `orphan-tool-call-session-wedge`：同系列；那篇 = call↔output 配对缺失；本文 = 单个 call 的身份 / 参数在流式组装时被拼坏。交点只有「坏 call 也要配 output」一句
  - vs `silent-tool-result-truncation`：那篇 = 工具**结果**进模型前被裁；本文 = 模型发出的**调用参数**进工具前被拼坏（方向相反）
  - vs `mcp-valid-but-wrong`：那篇 = 参数合法但语义错；本文 = 参数因传输层组装而不合法或张冠李戴
  - vs `layered-retry-amplification`：协议错误被包装成连接错误后会被重试，一句互链
- **参考线索：**
  - https://github.com/openai/openai-python/pull/3425 — **主证据（fix PR，merged 2026-09-10；Fixes #3201）**
  - https://github.com/BerriAI/litellm/pull/21337 — **主证据（fix PR，merged 2026-02-27 into staging 分支；Fixes #21331）**；桥接改用 `output_index`
  - https://github.com/unslothai/unsloth/pull/10059 — **主证据（fix PR，merged 2026-08-31；Fixes #9807）**；坏 blob 持久化重放；拼接工具名静默不执行与「server 复用 slot」只出自 PR 描述；复现是重放 issue 里的流
  - https://github.com/openai/openai-python/issues/3201 — 旁证（closed completed，经 PR #3425）
  - https://github.com/openai/openai-python/issues/3203 — 旁证（closed，state_reason=duplicate；报告人 2026-05-12 自行以 duplicate 关闭、并入 #3201）；vLLM speculative decoding 下观察到；「name + 首段 arguments 同一 event」出自其复现脚本注释
  - https://github.com/BerriAI/litellm/issues/21331 — 旁证（closed completed 2026-03-02 UTC，经已合 PR #21337）
  - https://github.com/BerriAI/litellm/issues/33678 — 旁证（**open**，stale 标签；关联 PR #37792 open）：`ollama_chat` 同类问题（Ollama 自己在 `function.index` 给对 0 / 1，LiteLLM 丢弃后重算），下一轮报成 `APIConnectionError`（实为 `json.JSONDecodeError`）；#33682 / #39012 closed 未合
- **备注：** Gate PASS ready — Sat round 2026-10-10（Alice 触发）。写稿禁令：#33678 仍 open，不能写成已修；不要说 vLLM 普遍有这个 bug，只写「#3203 的报告者在开启 speculative decoding 时观察到」；openai-python 的修复只覆盖 Python SDK，不推断其他语言 SDK 的状态；「同 `index` 不同 `id` 即报错」是本文 GOOD 主张，不是任何 SDK 的现有行为；openai-python PR #3232 / #3508 是未合的竞争 PR，不要当修复引用；unsloth 的修复是启发式切分，正文要写它的边界，不要当 GOOD 范本。P2（排在 `compaction-drops-pinned-instructions` 之后，保持系列顺序）。**Fri 2026-10-16 严格复核（读 issue / PR 正文 + 关闭状态）：PASS 保持 ready，证据比 compaction 条扎实（三条主证据均已合并且逐条核过）**。新增写稿禁令：(a) #3201 / #3203 的同 `index` 两条是**同一个调用的片段**，不是两个并行调用；§5 注入 1 的 SSE 形态来自 #3201，注入 2（不同 `id` 同 `index`）才是 LiteLLM #21331 / #33678 那类生产方问题，两类要分开写；(b) PR #3232 与 #3508 已核实均为 closed 未合并（另有 #3204 / #3223 / #3245 也是 closed 的竞争 PR）；(c) #3201 / #3203 里「Go / Node SDK 没有这个问题」是报告者的说法（#3203 还称 Node 的 AssistantStream 有同样 bug），未核，不引；(d) unsloth #9807 的「3 个工具名拼成 …」「服务端复用 slot」来自 PR #10059 描述，且 PR 引用的 vllm#18412 未核；(e) 引用 LiteLLM #21337 时写明合入的是 staging 分支。

### [published] 2026-10-22 | P2 | mcp-server-instance-reuse-cross-client-leak

- **发布备注（2026-10-22）：** Reviewer Approve 后发布为 `posts/mcp_server_instance_reuse_cross_client_leak.md`（MCP Server Runtime Boundaries #1；周三写作日稿件，因审稿阻塞项顺延到周四推送）。正文以 advisory 的 What is affected 为准并点明其自相矛盾；§4 拆为 v1 共享 transport / v2 每请求 transport / v3 有状态会话共享 server；`500` 只归 PR #2918；GOOD 中 `transport.onclose` 只删 session、不调 `server.close()`（否则重入致栈溢出）。
- **工作标题：** 一个 `McpServer`、两个客户端：server 实例复用时 sampling / elicitation / progress 发给了别人
- **失败面（MCP Server 的连接作用域，非认证、非工具参数、非 prompt 注入）：** 服务端为省事把一个 `McpServer` / `Server`（或一个 stateless `StreamableHTTPServerTransport`）复用给多个并发客户端，而客户端 SDK 默认的 JSON-RPC id 都从 0 递增 → 两种复用、泄漏条件不同：(a) **transport 复用**：传输层的 `requestId → stream` 映射按 JSON-RPC id 键，id 碰撞时后到的请求覆盖前一个的映射项 → **所有请求类型**（`tools/call`、`resources/read` …）的响应都可能发到另一个客户端的 HTTP 流；(b) **server 复用**：`Protocol` 内部只有一个 `_transport` 引用，后一次 `connect()` 静默覆盖前一次 → ① **最终响应也会错路由**：响应走的是请求处理时捕获的 `this._transport`，覆盖发生后才到达旧 transport 的请求，其响应被发到新 transport，发起方超时（advisory 原文 “The requesting client will time out.”）；② handler 执行中经 `this._transport` 发出的 progress、sampling（`createMessage`）、elicitation 只有在新 transport 上 **JSON-RPC id 碰撞**时才**静默**发给另一个客户端，没有碰撞时 transport 抛错而不是错发；③ handler 之外的 spontaneous 通知不需要碰撞，**总是**发给最后连接的那个客户端。
- **为何够深（非科普）：** 主线锁 **「连接实例的所有权」这一条不变量**：一个 server 对象 = 一个连接，一个 stateless transport = 一个请求。违反它时，三类消息的泄漏条件各不相同，这正是排查难的地方：transport 复用 → 所有请求类型的响应都会串（靠 id 碰撞）；server 复用 → 最终响应在「覆盖之后才到达旧 transport」时被发到新 transport、发起方超时（表现为偶发超时，而不是泄漏）；handler 内的 progress / sampling / elicitation 只在 id 碰撞时静默串流，不碰撞时抛错（低并发测试里看到的是偶发报错）；spontaneous 通知总是发给最后连接者。所以同一个 bug 在测试环境是「偶发超时 / 偶发报错」，上线高并发后才变成静默跨租户泄漏。修复的选择也值得讲：官方没有加隔离层，而是把静默错路由改成**立即报错**——advisory「Patches」节列出 1.26.0 的三项 runtime guard：(1) `Protocol.connect()` 已连接则 throw（对应 Issue 2）；(2) stateless `StreamableHTTPServerTransport.handleRequest()` 第二次调用 throw（对应 Issue 1）；(3) `close()` 时清理 in-flight handler 的 abort controller，handler extras 里的 `sendNotification` / `sendRequest` 发送前检查 abort signal；主线 PR #2918 再把 README 示例改成每请求一个 server + transport。
- **拟用案例 / 对照：**
  1. **BAD#1 transport 复用（stateless 模式）** GHSA-345p-7cg4-v4c7 / CVE-2026-25536 Issue 1：单个 `StreamableHTTPServerTransport` 处理多个客户端请求，id 碰撞 → 第二个请求覆盖第一个的映射项，响应发到错误的 HTTP 流；所有请求类型都受影响，不需要 server-initiated 功能。
  2. **BAD#2 server 复用（含 stateful 模式）** 同 advisory Issue 2：一个 `McpServer` 被 `connect()` 到多个 transport → `_transport` 被覆盖；最终响应在「请求于覆盖之后才到达旧 transport」时错发到新 transport、发起方超时（已在途的请求捕获的是旧引用，不受影响）；handler 内的 progress、sampling（`createMessage`）、elicitation 在新 transport 上 id 碰撞时静默发到错误客户端，无碰撞时 transport 抛错；spontaneous 通知总是发给最后连接的客户端。advisory 明确：即使用了 `sessionIdGenerator`，只要共享 server 就仍受 Issue 2 影响。
  3. **BAD#3 官方示例 / 常见写法本身就是复用** 早期 issue #204（「server.connect(transport) 会覆盖已有 transport，SSE 怎么支持多个客户端？」，closed completed 2025-12-05）里的示例就是一个 server 配多个 SSE transport；修复 PR #2918（2026-10-02 合入）同步把 express / fastify / hono / node 的 README 示例改成每请求新建 server + transport（PR 自述）。
  4. **GOOD：** 每请求（stateless）或每 session（stateful）新建 server + transport | `connect()` 在已连接时 fail-fast，把静默错路由变成可观测错误 | stateless transport 第二次 `handleRequest()` 拒绝（Node 包装返回 500）| close 时取消 in-flight handler，handler extras 在发送前检查 abort signal | 注册逻辑抽成工厂函数，复用的是**注册表 / 工具定义**而不是**连接对象**。
- **§4 业务线：** 同一个多租户代码审查 agent 服务 `svc_review-bot`：租户 A 的会话 `sess_A-17` 和租户 B 的会话 `sess_B-04` 同时在跑，两边客户端都用 SDK 默认、从 0 递增的 JSON-RPC id，都调用同一个工具 `review_diff`，该工具在执行中会向客户端发起 elicitation（「是否把这个文件发给外部 linter？」）并发 progress。**BAD v1**：服务启动时建了一个全局 `McpServer`，每个 HTTP 请求新建 transport 并 `connect()` 到它 → `_transport` 被最后连上的 B 覆盖；A 的 `review_diff` 还在执行，而 B 的 transport 上正好有一个与 A 这次请求**同 id**（例如两边都是 `id: 3`）的在途请求 → A 的 elicitation 被发进 B 的流，B 回答「是」，A 的 diff 被发出去；progress 带着 A 的文件名落到 B 的流里 → 没有任何报错，日志里两边都「成功」。同一时段，覆盖之后才到达 A 旧 transport 的另一个请求，其最终响应被发到 B 的 transport，`sess_A-17` 只看到超时（回扣 §3 的「连接实例所有权」不变量：数据面错路由）。id 没撞上的时候，同样的写法只会让 handler 抛错——所以它在低并发测试里是偶发报错，上线后才变成静默泄漏（回扣 §3 三类消息的泄漏条件）。**GOOD v2**：每请求 `createServer()` 工厂 + 新 transport；升级到 1.26.0 后第二次 `connect()` 直接抛错（advisory Patches 第 1 项）→ 把 BAD v1 的写法在第一个并发请求就暴露；`close()` 之后 handler 不再往被替换的 transport 发消息（Patches 第 3 项）；每个修复映射回 §3 的「连接实例所有权」不变量。
- **§5 可注入失败点：**
  1. **注入：** 两个客户端并发调用同一个 stateless transport / server，使 JSON-RPC id 都从 0 起 → **期望：** 第二个请求被拒，不出现响应串流（1.26.0：`connect()` / stateless `handleRequest()` throw；主线 PR #2918：错误码 `SdkErrorCode.AlreadyConnected`（`ALREADY_CONNECTED`），Node transport 对第二个请求回 `500`）
  2. **注入：** 共享一个 `McpServer` 连两个 transport，让第二个客户端上有一个与第一个客户端在途请求同 id 的请求，handler 执行中发起 elicitation；另在覆盖之后向旧 transport 发一个新请求 → **期望：** `connect()` 第二次直接失败；（对旧版做回归对照）elicitation 只发给发起请求的那个客户端，覆盖后的请求不会把响应发到新 transport
  3. **注入：** 连接中途 `close()` transport，handler 随后发 progress → **期望：** 不再发送（abort signal 已触发），没有消息泄漏到替换后的 transport
- **领域标签：** MCP Server Runtime / Session & Transport Isolation
- **专题归属：** **MCP Server Runtime Boundaries**（新开，#1；与已发的 mcp-auth / consent-binding 区别：那些是认证与授权边界，本篇是连接实例的隔离边界）
- **相关已发文 / 边界：**
  - vs `mcp-consent-binding-confused-deputy` / `mcp-auth`：那些 = OAuth / 授权层的绑定与委托；本篇 = 授权通过之后，实例复用造成的 payload 错路由，不涉及 token
  - vs `streaming-tool-call-index-collision`（已发，Session-State Integrity #3）：同属「按 id / index 键的映射被碰撞」，但那篇 = 流式 delta 的组装键；本篇 = 请求 id 到连接的路由键，只一句互链
  - vs idea `mcp-sampling-server-controlled-prompt`：sampling 在这里只是被错路由的一类消息，不讲 prompt 控制权
- **参考线索：**
  - https://github.com/advisories/GHSA-345p-7cg4-v4c7 — **主证据（官方 advisory，CVE-2026-25536，high，CVSS 7.1，2026-02-04 发布；影响 `@modelcontextprotocol/sdk` >= 1.10.0, <= 1.25.3，1.26.0 修复）**；机制以 Impact 节为准（最终响应错路由 / in-request 消息静默泄漏需 id 碰撞 / spontaneous 通知总发最后连接者），守卫细节以 Patches 节三项为准
  - https://github.com/modelcontextprotocol/typescript-sdk/releases/tag/v1.26.0 — **主证据（release，2026-02-04）**；release notes 只写 “Addresses … GHSA-345p-7cg4-v4c7”，未单列修复 PR / guard 细节——guard 细节引 advisory Patches 节
  - https://github.com/modelcontextprotocol/typescript-sdk/pull/2918 — **主证据（fix PR，merged 2026-10-02；主线 `packages/server` 拒绝第二次 connect / stateless transport 复用，并改 README 示例）**；PR 自述 “The 1.x line has had the first two checks since 1.26.0.”——abort 清理（Patches 第 3 项）不在本 PR 描述里，不要归到它
  - https://github.com/modelcontextprotocol/typescript-sdk/issues/204 — 旁证（closed completed 2025-12-05）：单 server 多 SSE transport 的困惑
  - https://github.com/modelcontextprotocol/typescript-sdk/issues/243 — 旁证（closed completed 2025-12-05）：多用户 Web 应用里该如何复用 client / transport
- **备注：** Gate PASS ready — Fri light refill 2026-10-16（逐条读 advisory JSON、v1.26.0 release notes、PR #2918 正文与 issue 正文）。写稿禁令：只讲 TypeScript SDK；advisory 只覆盖该 SDK，不推断 Python / Rust / Go SDK 是否有同类问题（rmcp 线索只见聚合页，未证实）；不要写「MCP 协议有漏洞」——这是实现层的实例复用；1.26.0 的修复是**报错**而不是隔离，复用实例的服务升级后会开始报错，要写成预期行为；#204 / #243 是提问类 issue（不是漏洞报告），只作为「写法常见」的旁证；§4 的 elicitation 场景是设计示例（advisory 确认 sampling / elicitation 会错路由，但没有真实受害案例）。P2。**Wed 2026-10-21 复核（经 API 重读 advisory 全文、v1.26.0 release、PR #2918）：PASS 保持 ready。** 机制句按 advisory Impact 节更正三处：(1) server 复用时**最终响应也会错路由**——覆盖之后才到达旧 transport 的请求，响应发到新 transport，发起方超时；原句「server 复用只泄漏 handler 执行中的 server→client 消息」错误，已删；(2) handler 内的 progress / sampling / elicitation 只有在 JSON-RPC id 碰撞时才静默泄漏，否则 transport 抛错；(3) spontaneous 通知不需要碰撞、总是发给最后连接的客户端。§4 BAD v1 已写明两边 id 从 0 递增并撞上同一个 id；GOOD 的守卫细节改为引 advisory Patches 节（connect throw / stateless handleRequest throw / close 时 abort 清理 + 发送前检查 abort signal）。新增写稿禁令：不要写「共享 server 就一定静默泄漏」——in-request 消息静默泄漏要 id 碰撞，最终响应错路由的表现是发起方超时；abort 清理只出自 advisory，不归到 PR #2918；1.x 的报错文案未核，`AlreadyConnected` / `ALREADY_CONNECTED` / `500` 只用于主线 PR #2918。 **Scout 更正（2026-10-22 → 重建于 2026-10-25，条目已 published）：** Writer/Reviewer 10-21～22 指出、原 PR #80 对 ready 条目做的五处更正，发布后折叠进本备注，供周末人工复核（正文已按审稿结论定稿，不回改 posts/）：(1) §4 BAD v1 不能用「全局 server + 每请求新建 stateless transport」演示最终响应超时——advisory「How to tell」判该写法工具只返回结果时 safe；应演示 stateful session + 共享 server（Issue 2），另用共享 stateless transport 演示 Issue 1；(2) GOOD 的 `500` / `-32603` 只归 PR #2918 原文，1.x Node transport 状态码未核；(3) advisory Issue 2「What happens」与「What is affected」对最终响应自相矛盾，正文以后者条件句为准并点明矛盾；(4) PR #2918 随 v2.3.0 / `@modelcontextprotocol/server@2.3.0` 等 v2 包发布，1.x 守卫来自 1.26.0；(5) `transport.onclose` 里不要调 `server.close()`（v1.26.0 源码调用顺序会重入至栈溢出；正文 GOOD / §5 已写）。1.x 报错文案已在 v1.26.0 源码逐字核到。


### [published] 2026-10-23 | P2 | mcp-cancellation-not-propagated

- **发布备注（2026-10-23）：** Reviewer Approve 后发布为 `posts/mcp_cancellation_not_propagated.md`（Agent Runtime Failure Handling #2）。正文按是否已发 `notifications/cancelled` 拆成 A/B/C；#2480 写清关闭评论归因 #3188 与 API 仅挂未合 #2481/#2493 的分歧，未写成「已由 #3188 关闭」。**Scout 2026-10-25：** 条目保持 `published`；上述 A/B/C 拆分与 #2480 评论-vs-API 分歧写入本发布备注，作为 Writer/Reviewer 10-23 验收口径的 backlog 对齐（不回改 posts/）。
- **工作标题：** 客户端超时了，工具还在跑：MCP 取消没过线，迟到的取消又把连接打断
- **失败面（MCP 请求生命周期 / 取消语义层，非重试层数、非历史配对、非进程崩溃后重放）：** Agent Host 给工具调用设超时（或用户中断、外层 `asyncio.wait_for`）→ MCP 客户端只在本地放弃等待，没有发 `notifications/cancelled` → server 端 handler 照常跑完，期间一直占着 DB 连接 / 锁 / 文件句柄，结果送回时没人收（python-sdk #2507：50 次被取消的 `call_tool` → server 端多出 50 个协程，直到会话结束；报告者在自己的 Databricks server 上：连接池 10 + 10 次取消 = 池耗尽）→ Agent 把超时当失败、重试，后面的调用排在泄漏的连接后面。反方向也会坏：取消发出去了，server 却仍回一个 `{"code": 0, "message": "Request cancelled"}` 响应（#2480），严格客户端把它当未知 id、关掉 stdio transport 重连（报告里 Claude Code 日志 `Received a response for an unknown message ID`）；或者取消在 handler 返回之后、`respond()` 之前到达，v1 的断言触发 `AssertionError: Request already responded to`，整个 server 进程退出，带走所有在途请求（#2416）（误判「工具太慢 / 把超时调大 / MCP server 不稳定」）
- **为何够深（非科普）：** 主线锁 **取消是一条协议消息，不是本地异常**：一次调用有三个各自独立的终态视角——调用方放弃等待、被调方停止执行、线上出现（或不出现）响应——取消协议的工作是把三者对齐，而每个方向都可能漏：(1) **本地放弃 ≠ 远端停止**：SDK 内部超时（`anyio.fail_after`）和调用方外部取消两条路径都只清理客户端自己的 response stream（#2507），server 不知道请求已经没人等；(2) **取消之后不该再有响应**：规范要求 receiver 不再应答、sender 忽略之后到达的响应，两边只要一边不守，就变成「未知 id」→ 断连；(3) **取消与完成的竞态要在响应边界收口**：「一个 request id 至多一个终态」，否则「取消到得晚了一点」会被当成程序错误把进程打崩（#2416）。(4) **取消是 advisory 的**：规范允许 receiver 在已完成或不可取消时忽略取消，所以——写工具被取消后结果是**未知**，不是「没做」，要和幂等键 / `outcome_unknown` 联动。修复对照：python-sdk v2 主线 PR #2838 让被放弃的请求发 courtesy `notifications/cancelled`（`initialize` 和带 resumption hints 的请求除外），取消路径上的 shielded 写入限时 5s；PR #3188 让收到取消的请求不再应答。不是「怎么设超时」入门
- **拟用案例 / 对照：**
  1. **BAD#1 本地放弃、远端照跑（python-sdk v1 客户端）** #2507：`ClientSession.send_request()` 的两条放弃路径（`except TimeoutError` 只抛 `McpError`；外部 `CancelledError` 只走 `finally` 清理本地 stream）都不发 `notifications/cancelled`；报告者复现：对一个 `await asyncio.sleep(300)` 的工具做 50 次 0.1s 超时调用，server 端任务数 4 → 54（mcp 1.29.0，stdio 与 streamable_http 相同）；server 侧收到取消时本来就会取消协程，缺的只是客户端发送。#2507 于 2026-06-15 以 completed 关闭，关闭它的是已合 PR #2838（v2 主线把 `ClientSession` 改到 `JSONRPCDispatcher` 上、删掉 `BaseSession`）；竞争 fix PR #2514 / #2518 均 closed 未合。更早的同题 #1458 于 2025-10-10 以 duplicate 关闭，duplicate 目标是规范仓库的 SEP-1627 Conformance Testing 追踪 issue（modelcontextprotocol#1627），**不是修复**
  2. **BAD#2 取消之后还回响应（python-sdk v1 server）** #2480：`RequestResponder.cancel` 收到取消后发回 `{"code": 0, "message": "Request cancelled"}`；报告称 Claude Code 把它当未知 id，日志 `Received a response for an unknown message ID`，关闭 stdio transport 并重连 → 长工具每取消一次就重连一次。2026-08-14 以 completed 关闭，关闭者（maxisbey，CONTRIBUTOR）说明：v2 由 PR #3188 修复（已合 2026-07-27，v2.0.0 release notes 写 “cancelled requests are no longer answered”），**1.x 仍是旧行为**，只接收关键修复，可用 issue 里的 monkey-patch
  3. **BAD#3 取消晚到把 server 打崩（python-sdk v1 server）** #2416（open，label `fix proposed`；fix PR #2417 closed 未合）：取消在 handler 返回之后、`respond()` 之前到达 → `cancel()` 先把 `_completed` 置真并发错误响应 → `respond()` 里 `assert not self._completed` 触发 `AssertionError: Request already responded to`，整个 server 进程退出、所有在途请求丢失（报告环境 mcp 1.27.0 + Claude Code 2.1.92，stdio）；评论里有社区用户称 sync（`def`）handler 下这是确定性触发而非竞态，并在 1.30.0 上复现（社区评论，非维护者确认）
  4. **旁证（TypeScript SDK）** #2018（open，`potentially close` 标签；fix PR #2019 open）：`handleAutomaticTaskPolling` 的轮询循环不检查 `ctx.mcpReq.signal.aborted`，被取消的请求无限轮询——同一类「取消没传到执行体」
  5. **GOOD：** 调用方放弃（超时 / 用户中断 / 外部取消）时 best-effort 发 `notifications/cancelled`，发送限时，传输卡死时不挂住调用方（PR #2838）| 收到取消：停止执行、释放资源、不再应答（PR #3188；规范 SHOULD）| 调用方忽略取消之后到达的响应和未知 id，不断连 | 响应边界保证「一个 request id 至多一个终态」，`respond()` / `cancel()` 对已终态的请求都幂等（本文主张，#2416 评论区的社区提议，非 SDK 现有行为）| handler 在副作用前检查 abort signal；server 侧每工具超时兜底 | 写工具被取消或断连后记 `outcome_unknown` + 幂等键，下一轮先查状态 | 指标：server 在途 handler 数 vs 客户端 pending 请求数
- **§4 业务线：** 同一夜间对账作业 `RECON-2210`：Agent 逐个商户调用 MCP 工具 `run_ledger_query`（server 从 10 个连接的池里取 DB 连接）和 `post_adjustment`（写调账单）。**BAD v1**：Host 用 `asyncio.wait_for(call_tool(...), 30)` 给每次调用设超时，v1 客户端放弃时不发取消 → 慢查询在 server 端继续占连接；Agent 把超时当失败重试，`RECON-2210` 累计 10 次超时后连接池被占满，之后所有商户的查询都在排队，直到作业超时（回扣 §3.1 本地放弃 ≠ 远端停止）。**BAD v2**：客户端补上取消通知，但 server 仍是「取消后回错误响应」的实现 → 严格客户端遇到未知 id 断开重连，`RECON-2210` 同一连接上的其他在途调用一起丢（回扣 §3.2 取消后不应答 / 忽略迟到响应）。**BAD v3**：`post_adjustment` 在 handler 返回后、响应写出前收到取消 → server 断言崩溃、进程重启；调账其实已写入，Agent 只看到连接断开，按失败重做 → 重复调账（回扣 §3.3 单一终态 + §3.4 取消后结果未知）。**GOOD**：放弃即发 `notifications/cancelled`（限时）；server 收到后停止、释放连接、不应答；响应边界对已终态幂等；`post_adjustment` 被取消或断连时记 `outcome_unknown`，带幂等键 `RECON-2210-adj-<merchant>`，下一轮先 `get_adjustment_status` 再决定；监控 server 在途 handler 数与客户端 pending 数之差（回扣 §3.1–§3.4）
- **§5 可注入失败点：**
  1. **注入：** 对一个永不返回的工具做 N 次短超时调用（#2507 的探针：0.1s × 50），再调一个返回 server 任务数的工具 → **期望：** server 端在途任务数回到基线；每次放弃在线上都能看到一条 `notifications/cancelled`
  2. **注入：** handler 执行中发 `notifications/cancelled` → **期望：** 线上不出现该 id 的任何响应；客户端连接不断，同连接上其他在途调用正常返回
  3. **注入：** 在 handler 返回与写响应之间注入延迟（或用 sync handler），期间发取消 → **期望：** server 不崩，该 id 至多一个终态；被取消的写工具在调用方侧落为 `outcome_unknown`，下一轮先查状态、不重复写
- **领域标签：** Agent Host Runtime / MCP Request Lifecycle / Cancellation & Timeout
- **专题归属：** **Agent Runtime Failure Handling**（续篇 #2：取消传播。#1 `layered-retry-amplification` = 调用失败后谁来重试、按什么分类；本篇 = 放弃一次调用时，对端是否真的停下、线上是否还会冒出响应）
- **相关已发文 / 边界：**
  - vs `layered-retry-amplification`：那篇 = 重试层数、归属与错误分类；本文 = 被放弃的那次调用在远端的生命周期。交点只有「泄漏的调用让重试排在后面」一句互链
  - vs `agent-write-idempotency`：那篇 = 超时后重试是否安全；本文只把幂等键当作「取消后结果未知」的落地手段，不重讲幂等
  - vs `orphan-tool-call-session-wedge`：那篇 = 中断后会话历史缺 output → 永久 400；本文 = 中断后 server 端执行与传输连接的状态；`outcome_unknown` 的语义直接引用那篇，不复述
  - vs `durable-agent-execution`：那篇 = 进程死后从 checkpoint 重放副作用；本文 = 进程活着时的取消竞态，BAD v3 的崩溃只当后果，不讲恢复
  - vs published `mcp-server-instance-reuse-cross-client-leak`：同属 MCP 运行时；那篇 = 连接实例复用造成错路由；本文 = 单个请求的取消生命周期。「未知 id 的响应」两篇都会出现，本文只讲它如何触发断连
- **参考线索：**
  - https://github.com/modelcontextprotocol/python-sdk/issues/2507 — **主证据（issue，closed completed 2026-06-15，经已合 PR #2838）**；两条放弃路径都不发取消；任务数 4 → 54 的泄漏复现
  - https://github.com/modelcontextprotocol/python-sdk/pull/2838 — **主证据（fix PR，merged 2026-06-15，v2 主线；Fixes #2489 / #2507）**；被放弃的请求发 courtesy `notifications/cancelled`，取消路径写入限时 5s；PR 自述解决 `protocol:timeout:sends-cancellation`、`protocol:cancel:late-response-ignored` 两项 divergence
  - https://github.com/modelcontextprotocol/python-sdk/issues/2416 — **主证据（issue，open，label `fix proposed`；fix PR #2417 closed 未合）**；取消晚到 → `AssertionError: Request already responded to` → server 进程退出
  - https://github.com/modelcontextprotocol/python-sdk/issues/2480 — 旁证（closed completed 2026-08-14；关闭说明：v2 由 PR #3188 修复，1.x 未修）：取消后仍回 code 0 响应 → 客户端断连重连
  - https://github.com/modelcontextprotocol/python-sdk/pull/3188 — 旁证：fix PR（merged 2026-07-27）；被取消的请求不再应答；v2.0.0（2026-07-28）release notes：“cancelled requests are no longer answered”
  - https://github.com/modelcontextprotocol/python-sdk/issues/1458 — 旁证（closed duplicate 2025-10-10 → modelcontextprotocol#1627 SEP-1627 Conformance Testing，非修复）
  - https://github.com/modelcontextprotocol/typescript-sdk/issues/2018 — 旁证（open；fix PR #2019 open）：任务轮询不检查 abort signal
  - https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation — 规范旁证（只引逐字句）：receivers SHOULD “Stop processing the cancelled request” / “Free associated resources” / “Not send a response for the cancelled request”；“The sender of the cancellation notification SHOULD ignore any response to the request that arrives afterward”；“Both parties MUST handle these race conditions gracefully”
- **备注：** Gate PASS ready — Wed 2026-10-21 refill（逐条读 issue / PR 正文、评论与 API 关闭状态；#1458 的 duplicate 目标从页面数据读出）。写稿禁令：只讲 python-sdk（TypeScript 只用 #2018 一条旁证），不推断 TS / C# / Go SDK 的取消行为（PR #3188 说 “matches typescript-sdk and csharp-sdk”，是该 PR 的说法，未核）；v1 与 v2 必须分开写——#2507 / #2480 的修复都在 v2 线，1.x 仍是旧行为，不要写「Python SDK 已修复」；#2838 合入早于 v2.0.0 发布，但本轮没有逐 commit 核它进了哪个版本；#2416 仍 open，sync handler「确定性触发」和 1.30.0 复现来自社区评论；v2 主线上 #2416 是否仍存在未核；4 → 54 是 #2507 报告者的探针结果、「池 10 + 10 次取消 = 耗尽」是报告者自己 server 上的观察，都不当基准；规范只引 2025-11-25 Cancellation 页的逐字句（PR #3188 称 2026-07-28 的 transport 规则写 MUST NOT、cancellation 页仍是 SHOULD——本轮未核，正文不引 MUST NOT）；Claude Code 的断连行为出自 #2480 报告者描述，未独立复现；「一个 request id 至多一个终态」是本文主张；§4 的重复调账是设计示例。P2。 **Scout 2026-10-25（published 后对齐）：** Writer/Reviewer 按「有没有发 `notifications/cancelled`」拆 A/B/C；#2480 关闭评论归 #3188、API `closed_by_pull_requests` 只挂未合 #2481/#2493——正文与发布备注已写清，条目不再把 A/B/C 折成同一种失败。


### [published] 2026-10-26 | P2 | tool-call-id-rewrite-cross-provider
- **工作标题：** 换了个模型，会话就 400 了：tool call id 在跨 provider 重放时被改写
- **失败面（Host / 代理的消息格式翻译层，非流式组装、非写入侧半对缺失）：** 工具调用历史每一轮都整段重放；会话中途切模型、或经代理转到另一家 provider → 翻译层要让 `tool_use.id` / `tool_call_id` 满足目的地的约束 → 三种坏法：(1) **不改写**：客户端或上一家 provider 留下的长 id / 带 `|` 的 id 原样发给 Bedrock → `Member must have length less than or equal to 64` 之类的校验 400，会话之后每一轮同样失败（LiteLLM #34239 → PR #40872）；(2) **一律改写**：为过 Anthropic 的 id 校验，把 `functions.Bash:0` 改成 `functions_Bash_0`，却不管目的地是不是 Anthropic → 报告称 vLLM 上 Kimi K2 的 `kimi_k2` 工具解析器靠原格式从历史里推下一个调用序号，改写后工具调用被当成纯文本、返回 `finish_reason: stop`，Claude Code 中途静默结束任务，任何地方都没有报错（#34522 / #32214，open）；(3) **不对称改写**：一个 call 被拆成 N 个 `toolUse`（`<id>`、`<id>_1` …）而 `toolResult` 只发一个 → 下一轮 `Expected toolResult blocks at messages.N.content for the following Ids: tooluse_<orig_id>_1` 400，重试无效（#26060）（误判「模型不兼容 / 换回原模型就好 / provider 抖动」）
- **为何够深（非科普）：** 主线锁 **配对键在翻译层的改写必须是「按目的地选择、确定性、单射、两侧同源」的同一个函数**：历史每轮重放，所以改写不是一次性迁移，而是每轮出站都要重新算、call 与 result 都要算出同一个值的函数。四个性质各对应一个坏法：(1) **目的地合法**：按目的地约束校验，不合法才改（不改 → 硬 400，属于 orphan 篇讲过的「确定性失败」）；(2) **单射**：只做字符替换 / 截断会让 `call|x` 与 `call_x`、只在截断位置之后不同的两个 id 撞成一个——PR #40872 对每个被改写的 id 追加原 id sha256 的前 8 位 hex，并在构造 `toolUse` 和 `toolResult` 的同一处应用（包括拆分后带 `_{idx}` 的 id），两侧仍能对上；它取代的 PR #34292 先拼 id 再截断，拆分后缀会把 id 推回 64 以上、截断后的 id 也可能碰撞；(3) **按目的地门控、不改模型自己的状态**：id 对某些模型不是不透明字符串（Kimi K2 例子里格式承载序号），LiteLLM 的 sanitize（PR #31094，2026-06-24 合入 `litellm_internal_staging`）对所有后端无条件执行——**同一个改写，对 Anthropic 目的地是修复，对 vLLM 目的地是回归**；两个 open 的修复 PR（#34523 按目的地是否 Anthropic 家族、#40132 按 `api_base` 是否 api.anthropic.com）都在补这道门；(4) **结构改写要对称**：只拆 call 不拆 result，等于翻译层自己造了 orphan。不是「各家 API 格式对照表」
- **拟用案例 / 对照：**
  1. **BAD#1 不改写 → 硬 400（LiteLLM × Bedrock）** #34239（closed completed 2026-09-15，经已合 PR #40872）：`bedrock/zai.glm-5` 多轮工具调用时，模型自己生成的长 id 原样进 `toolUse.toolUseId` / `toolResult.toolUseId`，超过 64 字符 → `Member must have length less than or equal to 64` 400，整个工具循环中断。PR #40872 的复现：OpenCode 会话里存着一个 82 字符、带 `|` 的 id（`opencode|call|9f2c…`），会话切到 Bedrock 模型后，每一轮都报 `Member must satisfy regular expression pattern: [a-zA-Z0-9_.:-]+` 与长度错误；修复后 200，会话继续
  2. **BAD#2 一律改写 → 静默停（LiteLLM `/v1/messages` × vLLM Kimi K2）** #34522（open；fix PR #34523 open）与 #32214（open；fix PR #40132 open）：`normalize_anthropic_tool_use_id()` / `sanitize_tool_use_ids_in_anthropic_messages` 把 `functions.Bash:0` 改成 `functions_Bash_0`，不区分目的地；报告称 Kimi K2 的 vLLM / SGLang 解析器与 chat template 依赖原格式推下一个工具调用序号 → 工具调用被当纯文本返回、`finish_reason: stop` → Claude Code 中途结束任务，客户端看不到错误。#32214 报告者称在约第 5～6 轮工具调用时出现，回滚到 v1.90.3、或把两个 sanitize 调用点改成 no-op 后恢复。引入这个改写的 PR #31094，目的正是让 kimi → Anthropic 的跨 provider 重放不再因 `functions.Bash:0` 这类 id 400
  3. **BAD#3 结构改写不对称 → 永久 400（LiteLLM × Bedrock）** #26060（2026-07-26 被 github-actions[bot] 以 not planned 关闭，**未修复**；fix PR #31258 open）：为兼容串接 JSON，`_convert_to_bedrock_tool_call_invoke` 把一个 tool_call 拆成 N 个 `toolUse`（`<id>`、`<id>_1` …），而 `_convert_to_bedrock_tool_call_result` 仍按原 `tool_call_id` 只发一个 `toolResult` → 下一轮 `Expected toolResult blocks at messages.N.content for the following Ids: tooluse_<orig_id>_1`，会话历史永久不对称，重试无效（报告环境 litellm 1.82.2 + openai-agents 0.12.4 + Bedrock 上的 Claude Opus 4.6）
  4. **旁证（id 不唯一）** #27078（stale bot 以 not planned 关闭；fix PR #27079 closed）：GoogleGenAI adapter 用 `f"call_{func_name}"` 生成 id，同一轮两次调用同一函数 → 两个 call、两个 result 都是 `call_get_weather`，无法区分哪条结果属于哪个调用
  5. **GOOD：** 规范历史里保存原始 id，线上 id 在每次出站时按目的地现算，不回写历史（本文主张）| 改写函数确定性 + 单射：只在不合法时改写，改写后追加原 id 的哈希后缀（PR #40872 做法）| 同一函数、同一处作用于 call id 与 result id（含拆分后缀）| 按目的地门控：目的地接受原 id 就原样转发（#34523 / #40132 的方向，均未合）| 不做结构改写；必须拆时 result 同步拆（#31258 的方向，未合）| 出站前 validator：call id 唯一、每个 result 都有对应 call、长度与字符集满足目的地——不满足就本地报错，不发出去 | 指标：按目的地统计 id 改写次数与改写后的碰撞数
- **§4 业务线：** 同一个运维排障会话 `case_OPS-4410`：前几轮跑在自托管 vLLM 的 Kimi K2 上（id 形如 `functions.read_log:0`），客户端存下的历史里还有更早一段由另一个客户端生成的 82 字符、带 `|` 的 id；第 6 轮因上下文变长，路由把 `case_OPS-4410` 切到 Bedrock 上的模型。**BAD v1**：翻译层原样转发 → Bedrock 以长度 / 字符集校验 400，`case_OPS-4410` 之后每一轮同样失败，只能新开会话（回扣 §3.1 目的地合法）。**BAD v2**：补丁改成「出站一律把 `[^a-zA-Z0-9_-]` 换成 `_`、超长截断到 64」→ 路由切回 Kimi 后端的那一轮，`functions.read_log:0` 变成 `functions_read_log_0`，工具调用被当文本、`finish_reason: stop`，Agent 静默收工（回扣 §3.3 按目的地门控）；同时两个只在第 64 位之后不同的旧 id 被截成同一个，线上两次调用再也分不清各自的结果（回扣 §3.2 单射）。**GOOD**：历史保存原始 id；出站时按目的地选改写函数，只改不合法的 id 并追加原 id 哈希后缀；call 与 result 在同一处改写；发给 Kimi 的请求 id 字节不变；出站 validator 检查唯一性与配对，不满足就本地报错（回扣 §3.1–§3.4）
- **§5 可注入失败点：**
  1. **注入：** 历史里放一个 82 字符、含 `|` 的 call id 及其 result，路由到 Bedrock → **期望：** 200；线上 call id 与 result id 相等、≤64 字符、字符集合法
  2. **注入：** 历史里同时放两个只在截断位置之后不同的 id（或 `call|x` 与 `call_x`）→ **期望：** 改写后仍是两个不同 id；validator 对改写后的 id 集合做唯一性断言
  3. **注入：** Kimi 格式 id `functions.X:0` 重放给非 Anthropic 目的地；另一个用例让翻译层拆分一个参数串接的 call → **期望：** 前者线上 id 字节不变；后者要么不拆，要么每个拆出的 `toolUse` 都有 `toolResult`，否则本地拒发、不进 400 重试
- **领域标签：** Agent Host Runtime / Provider Translation / Tool-Call Protocol
- **专题归属：** **Agent Session-State Integrity**（续篇 #4：重放不变量——两半都在，但键在翻译后不再相等、不再唯一、或不再是模型认得的格式。#1 `orphan-tool-call-session-wedge` = 配对缺失；#2 `compaction-drops-pinned-instructions` = 语义保真；#3 `streaming-tool-call-index-collision` = 流式组装时身份坍缩）
- **相关已发文 / 边界：**
  - vs `orphan-tool-call-session-wedge`：那篇 = 写入侧只留下半对；本文 = 两半都在，翻译层改写后配不上了。#26060 是翻译层自己造出的 orphan，只一句互链那篇的发送前 validator
  - vs `streaming-tool-call-index-collision`：那篇 = 一轮流式 delta 组装时身份键坍缩；本文 = 已组装好的 id 在跨 provider 重放时被改写。#26060 的拆分就是那篇讨论过的 JSON 切分启发式，本文只讲它造成的 id 不对称，不重讲切分
  - vs `layered-retry-amplification`：这类 400 属 STOP 类、重试无效，一句互链
  - vs `subagent-delegation-envelope` / `host-tool-policy-merge-after-filter`：那两篇是权限装配；本文不涉及权限
  - vs published `mcp-server-instance-reuse-cross-client-leak`：那篇是 MCP JSON-RPC 请求 id 的路由碰撞；本文是 LLM 消息历史里的 tool call id，不是同一层
- **参考线索：**
  - https://github.com/BerriAI/litellm/pull/40872 — **主证据（fix PR，merged 2026-09-15；Fixes #34239）**；Bedrock `toolUseId` 字符替换 + 64 截断 + 被改写 id 追加 sha256 前 8 位 hex；同一处作用于 `toolUse` / `toolResult`（含拆分后缀）；取代 #34292；响应侧不做反向映射
  - https://github.com/BerriAI/litellm/issues/34522 — **主证据（issue，open；fix PR #34523 open）**；无条件改写 Kimi K2 id → 静默 `finish_reason: stop`
  - https://github.com/BerriAI/litellm/issues/26060 — **主证据（issue，closed not_planned 2026-07-26 by stale bot，未修复；fix PR #31258 open）**；拆分 `toolUse` 不拆 `toolResult` → 永久 400
  - https://github.com/BerriAI/litellm/issues/32214 — 旁证（open；fix PR #40132 open）：同一改写在 v1.91.0 的回归报告，回滚 / no-op 后恢复
  - https://github.com/BerriAI/litellm/pull/31094 — 旁证：引入 `/v1/messages` id sanitize 的 PR（merged 2026-06-24 into `litellm_internal_staging`）
  - https://github.com/BerriAI/litellm/issues/34239 — 旁证（closed completed 2026-09-15，经 PR #40872）：Bedrock 64 字符上限 400
  - https://github.com/BerriAI/litellm/issues/27078 — 旁证（closed not_planned，stale；fix PR #27079 closed）：`call_{name}` 生成的 id 不唯一
- **已发文：** posts/tool_call_id_rewrite_cross_provider.md
- **备注：** Gate PASS ready — Wed 2026-10-21 refill（逐条读 issue / PR 正文与 API 状态）。写稿禁令：只讲 LiteLLM 的实现，不推断其他代理 / SDK；「Kimi K2 解析器靠 id 格式推序号」是 #34522 / PR #34523 引 vLLM 博客与 sglang#10600 的说法，本轮未核这两个外部来源，写成「报告称」；Anthropic 的 `^[a-zA-Z0-9_-]+$` 出自 #32214 / #34522 正文，Bedrock 的字符集与 ≤64 只引 PR #40872 / #34239 里逐字出现的错误串，不写成厂商文档原文（本轮未查厂商文档）；#34239 issue 里自己猜的 Bedrock 字符集 `[a-zA-Z0-9_-]+` 与 PR #40872 引的实际错误串 `[a-zA-Z0-9_.:-]+` 不同，以错误串为准；#32214「约第 5～6 轮」是报告者观察；#34522 / #32214 的修复 PR 都未合，#26060 是 stale 关闭、未修复，都不能写成已修；PR #31094 合入的是 `litellm_internal_staging` 分支，它随 v1.91.0 发布是 #32214 报告者的说法（“released in v1.91.0”），未核；PR #40872 的哈希后缀只用于 Bedrock（PR 原文：Anthropic sanitizer 仍只替换字符、不截断）；「历史保存原始 id、线上现算」是本文主张；§4 的会话切换路线是设计示例，「截断后碰撞」由 PR #40872 / #34292 的描述支撑，不对 Bedrock 收到重复 id 时的行为下断言。P2。

### [published] 2026-10-28 | P2 | mcp-output-schema-validation-swallows-tool-errors
- **工作标题：** 工具报了错，模型却只看到 -32602：MCP `outputSchema` 校验把 tool error 吞成协议错误
- **失败面（MCP 工具结果契约 / SDK 校验层，非 Host 截断、非工具参数设计、非传输错路由）：** 工具声明了 `outputSchema`（描述**成功**结果的形状），遇到业务错误时按规范返回 `isError: true` 的 tool execution error → SDK 的校验层仍拿成功 schema 去校验这个错误结果 → 错误内容被换掉：(1) **客户端侧（TypeScript SDK v1.x）**：错误结果里带了 `structuredContent`（例如 `{code: "AUTH_REQUIRED"}`），`Client.callTool()` 在 `listTools()` 缓存过该工具的 validator 之后会校验它，抛 `McpError -32602`（`Structured content does not match the tool's output schema: …`），调用方拿不到 payload；没先调 `listTools()` 的测试客户端看不到这个异常（#2748，open）。#2748 下有社区评论报告：模型因此始终看不到错误码和纠正提示，同一个无效调用换着参数重试了 8 次；(2) **服务端侧（Python SDK v1.x）**：low-level server 里，有 `outputSchema` 的工具用纯文本 content 报错时，错误被替换成 `Output validation error: outputSchema defined but no structured output returned`；FastMCP 里返回 `CallToolResult(isError=True)` 时，`convert_result()` 照样拿 output model 校验 `structuredContent`，pydantic 的校验错误替换掉原错误信息（#2429，open，`fix proposed`；fix PR #2466 / #2467 open 未合）；(3) **schema 代际不一致**：`tools/list_changed` 刷新在调用在途时替换了 validator 缓存 → 按旧 schema 返回的正确结果被新 schema 判成 -32602（TS #2612，open）；或 server 自己产出的 `structuredContent` 违反自己发布的 schema（Python #3224：`NotRequired` 键被填 `null`），合规客户端拒收（误判「模型参数传错了 / 工具坏了 / 加重试」）
- **为何够深（非科普）：** 主线锁 **「校验的是哪种结果、用的是哪一代 schema」**：`outputSchema` 是成功结果的契约，不是错误结果的契约；规范把错误分成两类——Protocol Errors（JSON-RPC 错误）和 Tool Execution Errors（`isError: true`，原文 “contain actionable feedback that language models can use to self-correct”，“Clients **SHOULD** provide tool execution errors to language models to enable self-correction.”）。校验层一旦把第二类改写成第一类，模型就丢了自我纠错唯一的输入，Host 的重试分类也跟着错（-32602 看起来像「参数错」）。四个可拆的点：(1) **结果类型门控**：成功结果才对 `outputSchema` 校验——TS v2 主线客户端是 `result.structuredContent !== undefined && !result.isError`，v1.x（1.32.1 tag 与 v1.x 分支头）是 `if (result.structuredContent)`，两条线头上的注释一字不差（“Only validate structured content if present (not when there's an error)”），行为却相反；同一 SDK 的 v1.x server 端 `validateToolOutput` 对 `isError` 直接 return——**自己的 server 发出、自己的 client 拒收**；(2) **校验失败的降级方式**：校验失败该变成模型可见的 tool error（带工具名、原内容），而不是让整个 `callTool` 抛异常（本文主张）；(3) **schema 代际**：validator 要在发出请求时取快照，而不是收到响应后再查缓存（#2612 的提议，未合）；(4) **server 自检**：每个成功结果都应通过自己发布的 schema——#3224 说明 schema 生成和序列化是两条路径，会悄悄分叉。修复对照：TS 服务端早在 PR #655（2025-06-24 合入）就让 `isError` 结果跳过 server 校验；Python v2 主线 `func_metadata.py` 现已带 `not result.is_error` 守卫，v1.x 没有；#3224 由 PR #3331（merged 2026-08-20，`main`）修复。不是「什么是 structured output」入门
- **拟用案例 / 对照：**
  1. **BAD#1 客户端把错误结果当成功结果校验（TS SDK v1.x）** #2748（open，label `v1`）：`registerTool` 声明 `outputSchema: { score: z.number() }`，handler 返回 `isError: true` + `structuredContent: { code: "AUTH_REQUIRED" }`；报告者在 1.30.0 上的自包含复现：不先 `listTools()` → 拿到 `{"code":"AUTH_REQUIRED"}`；先 `listTools()` → `McpError: MCP error -32602: Structured content does not match the tool's output schema: data must have required property 'score'`。Scout 2026-10-22 在 1.32.1 tag 的 `src/client/index.ts` 核到同样的条件（validator 在 `await this.request(...)` 之后才从 `_cachedToolOutputValidators` 取）；一位 CONTRIBUTOR 在评论里说在 v1.x 头上复现。历史：同一修复已被提过多次且都没进 v1.x——PR #1428（base `v1.x`，2026-02-02 关闭未合）、PR #1690（2026-03-27 关闭未合）、#1943（2026-04-23 以 not_planned 关闭）、PR #1945（2026-10-05 关闭未合）；当前 PR #2836（open，base `v1.x`）只改注释与文档、**不改行为**
  2. **BAD#2 服务端校验替换掉错误信息（Python SDK v1.x）** #2429（open，labels `bug` / `ready for work` / `P2` / `fix proposed`）：low-level `call_tool` 先做 `outputSchema` 校验，handler 用纯文本报错时被替换成 `Output validation error: outputSchema defined but no structured output returned`（Scout 已在 v1.x 分支头 `src/mcp/server/lowlevel/server.py` 核到该字符串与 `isError=False` 硬编码）；评论区补充 FastMCP 路径：`convert_result()` 对 `CallToolResult` 无条件 `model_validate(result.structuredContent)`（v1.x `func_metadata.py` 已核），`"Division by zero"` 变成 pydantic 校验错误；社区给的 workaround 是抛异常（走 `ToolError`）而不是返回 `is_error=True`。fix PR #2466（base `main`）/ #2467（base `v1.x` backport）均 open 未合
  3. **BAD#3 schema 代际错配（TS SDK v1.x）** #2612（open，labels `bug` / `ready for work` / `P2` / `v1`）：`callTool()` 在 await 响应之后才取 validator，期间 `listTools()`（例如响应 `tools/list_changed`）清空并替换缓存 → 在途调用按旧 schema 返回的正确结果被新 schema 判 -32602；issue 给出「发请求前取 validator」的补丁，未合
  4. **旁证（server 违反自己发布的 schema，Python SDK v2）** #3224（closed completed 2026-08-20，经已合 PR #3331，base `main`）：返回 `TypedDict`、`NotRequired` 键缺省时，`structuredContent` 把缺的键填成 `null`，而发布的 schema 里这些属性不可为 null → SDK 自己的客户端 `RuntimeError: Invalid structured content returned by tool get_person: None is not of type 'string'`；同一次调用的 text block 是 `{"name": "Dave"}`，两份结果不一致
  5. **GOOD：** 只对成功结果（`!isError`）做 `outputSchema` 校验（TS v2 主线 / TS 服务端 PR #655 / Python v1.x 客户端 `if not result.isError` 的做法）| 跑在 v1.x TS 客户端上时，server 的错误结果不带 `structuredContent`、错误 payload 放 `content` 文本（#2748 报告者与评论者的 workaround）；Python v1.x FastMCP 上用抛异常报错（#2429 评论的 workaround）| Host 把校验失败降级为模型可见的 tool error（工具名 + 原 content + 「结果不符合 schema」），不当协议错误重试（本文主张）| validator 在发请求时取快照，`list_changed` 只影响之后的调用（#2612 提议）| server 侧契约测试：每个成功结果都用自己发布的 `outputSchema` 校验一遍，text 与 `structuredContent` 一致（#3224 的验收条件，来自评论区，社区说法）| 指标：按工具统计 `tools/call` 的 -32602 次数，与 `isError` 结果数对照
- **§4 业务线：** 同一个应付账款核对 agent，任务 `AP-7302`（逐张核对发票余额后发起付款）。MCP server 的工具 `get_invoice_balance` 声明 `outputSchema: { balance: number, currency: string }`；发票被财务锁定时返回 `isError: true` + `structuredContent: { code: "INVOICE_LOCKED", unlock_after: "…" }` + 同内容的 text。Host 用 TS SDK v1.x 客户端，启动时 `listTools()`。**BAD v1**：发票 `INV-5521` 被锁 → 客户端拿成功 schema 校验错误结果 → `-32602 Structured content does not match the tool's output schema: data must have required property 'balance'` → Host 当成协议错误交给 retry 层，模型只看到「参数不匹配 schema」，换着参数重调 `get_invoice_balance`，始终不知道是「已锁定、某时解锁」（回扣 §3.1 结果类型门控 + §3.2 降级方式）。集成测试用的是不调 `listTools()` 的测试客户端，所以 CI 全绿。**BAD v2**：server 团队「修」成错误时不带 `structuredContent`、只回 text——TS 客户端这条路通了；但同一工具的 Python v1.x 实现用 FastMCP 返回 `CallToolResult(isError=True)`，错误被 pydantic 校验信息替换，模型看到的仍然不是 `INVOICE_LOCKED`（回扣 §3.1，服务端侧）。**BAD v3**：财务把 schema 升级为 `{ balance, currency, as_of }` 并发 `tools/list_changed`，Host 刷新工具列表时 `INV-5521` 的另一次查询还在途 → 按旧 schema 返回的正确余额被判 -32602，`AP-7302` 这张发票被标成「查询失败」（回扣 §3.3 schema 代际）。**GOOD**：客户端只校验成功结果；校验失败降级为模型可见的 tool error；validator 在发请求时取快照；server 发版前对每个成功结果跑一遍「按自己发布的 schema 校验」；`INVOICE_LOCKED` 原样到达模型，模型改为先跳过 `INV-5521`、记下 `unlock_after`（回扣 §3.1–§3.4）
- **§5 可注入失败点：**
  1. **注入：** 有 `outputSchema` 的工具返回 `isError: true` + 不符合成功 schema 的 `structuredContent`；分别在调用前**调 / 不调** `listTools()` 各跑一次 → **期望：** 两种顺序结果一致，模型看到原错误内容，没有 -32602
  2. **注入：** Python v1.x server 上同一工具分别用纯文本 content 和 `CallToolResult(isError=True)` 报错 → **期望：** 客户端收到的错误文本与 handler 写的一致，不被 `Output validation error` 或 pydantic 信息替换
  3. **注入：** 让 `tools/call` 在途时触发 `tools/list_changed` 并换一版 `outputSchema` → **期望：** 在途调用按发出时的 schema 校验；之后的调用按新 schema
  4. **注入：** 契约测试遍历每个工具的成功路径（含可选字段缺省、`null`、嵌套）→ **期望：** 每个 `structuredContent` 都通过该工具发布的 `outputSchema`，text 与 `structuredContent` 语义一致
- **领域标签：** MCP Client / Server SDK · Tool-Result Contract · Error Semantics
- **专题归属：** **MCP/Host Tool-Result Fidelity**（续篇 #2：#1 `silent-tool-result-truncation` = 结果被裁成半截、模型自信答完；本篇 = 结果被 SDK 的契约校验整个换成别的错误，模型丢掉可纠错的信息）
- **相关已发文 / 边界：**
  - vs `silent-tool-result-truncation`（已发，同专题 #1）：那篇 = Host 按长度上限裁切 content；本篇 = SDK 按 schema 校验把结果替换掉，没有长度问题
  - vs `mcp-valid-but-wrong`（已发）：那篇 = 工具设计让调用「合法但错误」；本篇 = 工具正确报错，错误在返回路径上被吞
  - vs `layered-retry-amplification`（已发）：-32602 被 retry 层当成可重试 / 参数错是本篇的后果，只一句互链那篇的错误分类，不重讲重试层数
  - vs `streaming-tool-call-index-collision` / `tool-call-id-rewrite-cross-provider`：那两篇是 LLM 消息侧的 tool call 组装与 id；本篇是 MCP `tools/call` 结果的契约，不是同一层
  - vs published `mcp-server-instance-reuse-cross-client-leak` / published `mcp-cancellation-not-propagated`：同属 MCP SDK 运行时，但那两篇是连接路由与请求生命周期；本篇只讲结果内容的校验
- **参考线索：**
  - https://github.com/modelcontextprotocol/typescript-sdk/issues/2748 — **主证据（issue，open，label `v1`）**；v1.x 客户端校验 `isError` 结果的 `structuredContent` → -32602，依赖 `listTools()` 缓存；v1.x 与 v2 行为相反；修复历史表（#1428 / #1690 / #1945 关闭未合，#1943 not_planned）；PR #2836（open，base `v1.x`）只改注释与文档
  - https://github.com/modelcontextprotocol/python-sdk/issues/2429 — **主证据（issue，open，`fix proposed`；fix PR #2466 base `main` / #2467 base `v1.x` 均 open 未合）**；服务端校验把错误信息替换成 `Output validation error: outputSchema defined but no structured output returned` / pydantic 校验错误
  - https://github.com/modelcontextprotocol/typescript-sdk/issues/2612 — **主证据（issue，open，`bug` / `P2` / `v1`，无已合修复）**；在途调用被新一代 schema 校验
  - https://github.com/modelcontextprotocol/python-sdk/issues/3224 — 旁证（closed completed 2026-08-20，经已合 PR #3331，base `main`）：server 产出违反自己发布的 schema
  - https://github.com/modelcontextprotocol/typescript-sdk/pull/655 — 旁证（merged 2025-06-24，关闭 #654 completed）：TS 服务端对 `isError` 结果跳过校验
  - https://modelcontextprotocol.io/specification/2025-11-25/server/tools — 规范旁证（只引逐字句）：Output Schema 节 “Servers **MUST** provide structured results that conform to this schema.” / “Clients **SHOULD** validate structured results against this schema.”；Error Handling 节两类错误的定义与 “Clients **SHOULD** provide tool execution errors to language models to enable self-correction.”
  - 源码（Scout 2026-10-22 读）：TS `1.32.1` tag 与 `v1.x` 分支 `src/client/index.ts`（`if (result.structuredContent) {`）、`src/server/mcp.ts`（`if (result.isError) { return; }`）；TS `main` `packages/client/src/client/client.ts`（`result.structuredContent !== undefined && !result.isError`）；Python `v1.x` `src/mcp/server/lowlevel/server.py`、`src/mcp/server/fastmcp/utilities/func_metadata.py`、`src/mcp/client/session.py`（`if not result.isError:` 才校验）；Python `main` `src/mcp/server/mcpserver/utilities/func_metadata.py`（`not result.is_error`）
- **备注：** Gate PASS ready — Thu 2026-10-22 refill（逐条读 issue / PR 正文、评论、API 状态与 labels，并对照两个 SDK 的 tag / 分支源码）。写稿禁令：不要写「MCP 客户端都会这样」——Python v1.x 客户端和 TS v2 主线客户端都对 `isError` 跳过校验，问题限定在 TS v1.x 客户端（1.32.1 / v1.x 分支头）与 Python v1.x 服务端；「模型重试 8 次」出自 #2748 的社区评论（ynohat，非维护者），不当复现数据；#1428 的关闭理由（评审认为有 `structuredContent` 就应校验）是 #2748 正文与评论转述的，本轮未读 #1428 讨论原文，引用时写「据 #2748 所述」；规范没有规定错误结果能不能带 `structuredContent`（#2748 提到 SEP-2145 仍 open，本轮未核），不要写成规范禁止或允许；「校验失败降级为模型可见的 tool error」「validator 在发请求时取快照」分别是本文主张和 #2612 的提议，不是任何 SDK 的现有行为；Python v2 主线的 `not result.is_error` 守卫是哪个 commit 加的未核，只写「主线现已带该守卫」，并且 #2466 仍 open；#2429 评论区另一位评论者说 Python 客户端 `session.py` 不检查 `is_error`——v1.x 分支头源码显示会检查，不要引用这一句；#2748 里「`@modelcontextprotocol/client@2.0.0` 已带守卫」是报告者说法，本轮只核到 `main` 当前源码；§4 的 `AP-7302` 是设计示例。P2。

- **已发文：** posts/mcp_output_schema_validation_swallows_tool_errors.md

### [ready] 2026-10-27 | P1 | mcp-progress-same-chunk-unknown-token
- **工作标题：** 进度通知和结果同一包到了：客户端先删 handler，再把「未知 token」当成断连
- **失败面（MCP 客户端协议分发层 / progress handler 生命周期，非取消语义、非连接实例复用、非工具结果校验）：** Server 在返回 `tools/call` 结果之前（甚至同一 stdio 读缓冲里）写出 `notifications/progress` → Client 的 `_onresponse` **同步**删掉 `_progressHandlers`，而 `_onnotification` 把 progress **推到 microtask** 才跑 → 后到的（其实先写出的）progress 找不到 handler → `Received a progress notification for an unknown token: …` 进 `onerror`。Host 侧（Claude Code）再把这条协议错误当成 stdio transport 故障，打出 `STDIO connection dropped` / `Closing transport`，重连；同连接上其它在途 `tools/call` 被截断或丢参数（误判「MCP server 不稳 / 进度实现写错 / 网络抖」）
- **为何够深（非科普）：** 主线锁 **「wire 顺序 ≠ 客户端处理顺序」**：问题不是 server 违规迟到，而是客户端自己把同一次 read 里的通知排到响应之后。三层可拆：(1) **同 chunk 重排**：通知走 microtask、响应当场删 handler → 终端 `progress===total` 在 wire 上先于 result，却在客户端变成「未知 token」（#2580 + #2967 评论复现表：1.29.0 上 50 次调用里 43 次 `received=1`+3 errors）；(2) **真迟到**：响应处理完之后才到的 progress 仍应静默忽略，而不是 `onerror`（#2586 的 recently-completed FIFO）；(3) **Host 过激反应**：把未知 token 当成 transport 致命错误 → 断 stdio / 截断在途调用（Claude Code #102831 有线抓包；#64475 报告大参数 `body: expected string, received undefined`）。GOOD 对照：#2967 把 handler 删除推迟一个 microtask（同 tick 通知先送达）；#2586 对刚完成的 token 静默丢弃；Host 对未知 progress token 只 debug、不断连。不是「怎么发 progress」入门
- **拟用案例 / 对照：**
  1. **BAD#1 SDK 同 chunk 重排（TS SDK）** #2580（open，`bug` / `ready for work` / `P2` / `v1`+`v2`）：server 连发 N 条 progress 再回 result；客户端 `onerror` 刷 `Received a progress notification for an unknown token`；1.29.0 stdio 复现。#2967（open，base `main`，**未合**）评论给出 50 次统计与 deferred-delete 修复；报告者在真实 apple-photos-mcp `export` 上：基线 9/15 丢终端通知，#2967 预览 10/10 送达且零 `onerror`
  2. **BAD#2 Host 把未知 token 当断连（Claude Code）** #102831（open，`has repro`）：极简 Python stdio server，progress **紧挨** result 写出 → 每次 `STDIO connection dropped` + unknown token，工具仍显示成功；progress 提前 3s 则不触发。#64475（closed **not_planned**，stale bot，**未修复**）同日志下报告在途大字段被截成 `body: expected string, received undefined`；对照：同 SDK 独立客户端与 HTTP 直连均稳定
  3. **BAD#3 真迟到仍打协议错误（与 #2967 正交）** #2580 与 #2586（open，base `v1.x`，**未合**）：响应之后到达的同 token progress 仍走 `_onerror`；#2967 PR 正文写明它**不**覆盖真迟到，需 #2586 的 recently-completed 集合
  4. **旁证：** #47765（closed `duplicate` → #47378）正文是 progress unknown-token 断连，但 bot 指向的 #47378 是「成功后 2–5s 杀 stdin」另一症状（closed not_planned）——引用时写清 bot-dup 目标与正文不符，不以 #47378 当本坑修复追踪
  5. **GOOD：** 同 tick 内先派发已排队的 progress，再删 handler（#2967）| 刚完成 token 的迟到 progress 静默/debug，真未知仍报错（#2586）| Host 对未知 progress token 不断 transport、不中断其它在途调用 | 不以终端 progress 做完成闸门（完成以 result 为准）| 指标：unknown-token `onerror` 计数 vs 成功 `tools/call` 计数
- **§4 业务线：** 同一批影像导出任务 `EXPORT-8841`：MCP 工具 `export_album` 每张图发一条 progress，最后一条 `progress===total` 后立刻返回结果。**BAD v1**：Host 用 TS SDK 1.29.x，stdio 同一 read 里 progress+result → 终端进度进 `onerror`，UI 以为失败重试，server 端已写出文件（回扣 §3.1）。**BAD v2**：Claude Code 把未知 token 记成 connection dropped 并重连，同会话下一条带长 `body` 的 `tools/call` 被截断，server Zod 报 `body: expected string, received undefined`（回扣 §3.3）。**GOOD**：SDK 同 tick 先派发 progress；迟到 token 静默；Host 未知 token 只打 debug；`EXPORT-8841` 以 result 为完成信号，进度条允许丢最后一帧（回扣 §3.1–§3.3）
- **§5 可注入失败点：**
  1. **注入：** 无延迟地把 N 条 progress 与 result 塞进同一次 transport 派发 → **期望：** `onprogress` 收到全部 N 条；`onerror` 无 unknown-token；请求正常完成
  2. **注入：** result 处理后再发同 token 的 progress → **期望：** 不进 `onerror`（或仅 debug）；连接保持
  3. **注入：** Host 路径上紧挨 progress+result 的长工具，随后立刻发第二条大参数 `tools/call` → **期望：** 无 `STDIO connection dropped`；第二条参数完整到达 server
- **领域标签：** MCP Client Protocol Dispatch / Progress Notifications / Stdio Transport
- **专题归属：** **Agent Runtime Failure Handling**（续篇 #3：#1 `layered-retry-amplification` = 失败后谁重试；#2 `mcp-cancellation-not-propagated` = 放弃后对端是否停下；本篇 = 成功路径上通知与响应的分发顺序把「正常进度」打成协议错误 / 断连）
- **相关已发文 / 边界：**
  - vs `mcp-cancellation-not-propagated`：那篇 = 取消通知是否发出/应答；本文 = 进度通知与成功响应的顺序。交点只有「未知 id/token → 断连」一句互链
  - vs `mcp-server-instance-reuse-cross-client-leak`：那篇 = 多客户端共享实例错路由；本文 = 单连接内 handler 生命周期
  - vs `silent-tool-result-truncation` / `mcp-output-schema-validation-swallows-tool-errors`：那两篇是结果内容被裁/换；本文结果往往已成功，坏在旁路通知
  - vs `streaming-tool-call-index-collision`：那篇是 LLM 流式 tool_call 组装；本文是 MCP JSON-RPC 通知分发
- **参考线索：**
  - https://github.com/modelcontextprotocol/typescript-sdk/issues/2580 — **主证据（issue，open）**；unknown-token `onerror`；同 chunk 机制在评论中被钉死
  - https://github.com/modelcontextprotocol/typescript-sdk/pull/2967 — **主证据（fix PR，open，base `main`，未合）**；deferred delete；50 次复现表与真实 server 验证
  - https://github.com/anthropics/claude-code/issues/102831 — **主证据（issue，open）**；线抓包：progress 紧挨 result → connection dropped
  - https://github.com/modelcontextprotocol/typescript-sdk/pull/2586 — 旁证（open，base `v1.x`，未合）：recently-completed FIFO
  - https://github.com/anthropics/claude-code/issues/64475 — 旁证（closed not_planned，stale，未修复）：断连截断在途大参数
  - https://github.com/anthropics/claude-code/issues/47765 — 旁证（closed duplicate→#47378；正文与 #47378 症状不一致，引用须注明）
- **备注：** Gate PASS ready — Tue 2026-10-27 refill（读 #2580 正文+评论、#2967/#2586 PR 状态、#102831/#64475/#47765）。写稿禁令：不要写「SDK 已修复」——#2967/#2586 均未合；不要把 #47378 当本坑主线；#64475 的参数截断是报告者假设+日志相关，独立 MCP 客户端对照证明非 server bug，但 Claude Code 源码未开源核到具体 if；apple-photos 数字是报告者负载测试；「终端 progress 不可做完成闸门」是本文主张。P1。

### [ready] 2026-10-27 | P1 | tool-approval-cross-run-transfer
- **工作标题：** 上次点过同意，这次没问就执行了：审批记录只绑 call_id，不绑 run
- **失败面（Agent Host HITL / RunState 审批键空间，非 MCP OAuth consent、非子代理权限包络、非工具结果截断）：** 带 `needs_approval=True` 的工具在 Run 1 打断 → 人审批 → 执行；Run 2（新 run、常复用同一 `Agent` 实例）模型又发出**相同** `call_id` + 相同参数 → 应用把 Run 1 的 `ToolApprovalItem` 塞进 `state2.approve(...)` → `_approval_items_match` 只比 `(agent, invocation type, call_id, arguments fingerprint)`，**没有 run 谱系** → 受保护工具再次执行，本 run 无人点同意。旁路：(a) 并行工具批次里兄弟调用的 guardrail 炸掉时，已完成的副作用调用从 Session 消失，下一轮模型重做（#5327）；(b) 恢复审批回合上 output guardrail 绊倒时，streamed 路径留下无 output 的 orphan `function_call`（#4125）（误判「模型乱调 / Session 坏了 / 用户点过所以安全」）
- **为何够深（非科普）：** 主线锁 **审批是「对哪一次执行承诺」的能力，不是「对这个 call_id 形状的永久通行证」**。四点：(1) **谱系**：批准必须绑定 issuing run（或 execution generation），跨 run 重放 `ToolApprovalItem` 应拒绝（#5413；多人在 `main`@`0dc4cf1` 离线复现）；(2) **pending 集合**：`approve()` 对「当前并不在 `get_interruptions()` 里」的陈旧 item 仍可静默记账，随后模型再发出同 id 时直接执行（#5413 评论实测）；(3) **Agent 身份巧合防护**：换新 `Agent` 实例则 match 失败——模块级单例 Agent（常见写法）反而中招；(4) **与会话完整性联动**：并行批次异常不得丢掉已完成的 call/output（#5327）；审批后的 tool output 与 call 必须同生共死（#4125）。不是「怎么做 human-in-the-loop」入门
- **拟用案例 / 对照：**
  1. **BAD#1 跨 run 转让审批（OpenAI Agents Python）** #5413（open；测于 v0.23.1 / `main`@`0dc4cf1`）：`state2.approve(old_approval_item)` 让第二次 `write_marker(path="A")` 无新决策即执行；改参数则正确拒绝；独立复现评论给出 `after run 2: ['A', 'A']`
  2. **BAD#2 并行 guardrail 丢掉已完成兄弟调用** #5327（closed **completed** 2026-10-14，closer `jbeckwith-oai`；fix PR #5332 merged 2026-10-14）：`create_ticket` 已成功，`send_email` input guardrail 触发 → Session 只剩 `user`，下轮再开一张票；报告正文写「fix 后 0/10 重复建单」——合入后的 release 版号写稿前再核
  3. **BAD#3 恢复审批回合 + output guardrail → orphan call（streamed）** #4125（closed completed；feature:sessions）：人已 approve 的 tool 跑完后 output guardrail 绊倒 → `run_streamed` session 为 `['user','function_call']` 无 output；非 streamed 路径保留 pair
  4. **GOOD：** 审批记录带 run id（或 generation），`approve`/`reject` 校验谱系 | 只接受**当前** `get_interruptions()` 里的 item，拒绝预授权未来 call | 应用层自建 `(run_id, call_id, args_digest)` 表，一次性消费（issue 评论中的 app-side guard）| 并行批次异常时先落盘已完成 call/output 再抛 | 审批后的 call 与 output 同事务写入 | 副作用工具另加业务幂等键（评论建议，非 SDK 行为）
- **§4 业务线：** 同一张退款单 `RF-3390`：工具 `issue_refund`（`needs_approval=True`）。**BAD v1**：客服在 Run 1 批准退 $50；会话重放 / 负载均衡开出 Run 2，模型复用 `call_id`，旧 `ToolApprovalItem` 被 `approve` → 再次打款（回扣 §3.1–§3.2）。**BAD v2**：同 turn 并行 `create_credit_memo` + `send_refund_email`，email guardrail 绊倒 → credit memo 已生成但不进 Session，下轮再生成一张（回扣 §3.4 / #5327）。**GOOD**：Run 2 必须新中断、新人批；自建审批表按 run 消费一次；批次失败仍保留已完成项；`issue_refund` 以 `RF-3390` 业务键幂等（回扣 §3.1–§3.4）
- **§5 可注入失败点：**
  1. **注入：** Run 1 批准并执行后，Run 2 同 Agent、同 call_id、同 args，喂入 Run 1 的 approval item → **期望：** `approve` 拒绝或仍中断；工具执行次数不增加
  2. **注入：** 对「当前 pending 不是该 call」的陈旧 item 调用 `approve` → **期望：** 报错/拒绝，且不能预授权随后出现的同 id 调用
  3. **注入：** 并行两工具，后完成的那个触发 guardrail 异常 → **期望：** Session / `run_data` 仍含先完成那对 call+output；下轮模型看得见
- **领域标签：** Agent Host Runtime / Human-in-the-Loop Approval / Session Integrity
- **专题归属：** **Agent Session-State Integrity**（续篇 #5：#1 orphan 半对；#2 compaction；#3 streaming index；#4 tool-call-id 改写；本篇 = 审批/中断键没有 run 谱系，以及中断路径上已提交副作用从历史上消失）
- **相关已发文 / 边界：**
  - vs `orphan-tool-call-session-wedge`：那篇 = 缺 output 导致永久 400；本文 #4125 的 orphan 可被 `drop_orphan_function_calls` 剥掉继续跑，重点是**审批承诺与副作用是否提交**，不重讲 400
  - vs `mcp-consent-binding-confused-deputy` / `mcp-auth-identity-not-intent`：远程 OAuth/consent；本文 = 本地 RunState 工具审批
  - vs `subagent-delegation-envelope`：权限是否下传；本文 = 同会话审批票据是否跨 run 复用
  - vs `agent-write-idempotency`：超时重试幂等；本文把业务幂等键当审批泄漏时的兜底，不重讲幂等协议
  - vs `durable-agent-execution`：进程死后续跑；本文 #5413 评论提到 resume 与 run id 设计张力，只点一句
- **参考线索：**
  - https://github.com/openai/openai-agents-python/issues/5413 — **主证据（issue，open）**；跨 run 转让；多条独立离线复现评论
  - https://github.com/openai/openai-agents-python/issues/5327 — **主证据（issue，closed completed 2026-10-14，经已合 PR #5332，merged 2026-10-14）**；并行 guardrail 丢已完成调用
  - https://github.com/openai/openai-agents-python/issues/4125 — **主证据（issue，closed completed）**；恢复审批 + output guardrail → streamed orphan
  - https://openai.github.io/openai-agents-python/guardrails/ — 旁证文档：output guardrail 绊倒时保留 already-completed tool items（#5327 所引 commit 路径）
- **备注：** Gate PASS ready — Tue 2026-10-27 refill。写稿禁令：只谈 OpenAI Agents Python 的 RunState，不推断 JS SDK；#5413 无官方 fix，不要写已修；#5327 由 PR #5332（merged 2026-10-14，`fix: preserve completed tool outputs when a sibling fails`）关闭——写稿时核该 PR 进了哪个 release tag，不要写「SDK 仍必现」为现状；#4125 披露作者为 AI agent，机制以 issue 正文与 repro 为准；第三方 Tracekit / agent-approval-gate 只可作「应用层自建表」类比，不写成 SDK 方案；真实模型是否复用 call_id 未测（报告与复现均为 ScriptedModel）。P1。


### [ready] 2026-10-29 | P1 | mcp-list-changed-reload-blocks-receive-loop
- **工作标题：** `list_changed` 一来就卡死：通知 handler 里 await `list_tools`，接收环回不去，成功结果变成 "Error: Function failed."
- **失败面（MCP Host / Client 协议分发层 · 通知 handler 与 receive loop 的重入，非发现层目录陈旧、非 progress 顺序、非取消语义）：** MCP server 在 `tools/call` 执行中或刚返回前后发出 `notifications/tools/list_changed`（MATLAB / MongoDB 等动态工具目录常见）→ Host 的 `message_handler` **在 SDK 单线程 `_receive_loop` 回调里直接 `await load_tools()` / `session.list_tools()`** → `list_tools` 发出去的响应永远进不了 receive loop（loop 卡在 handler 里）→ 同连接上的 `call_tool` 超时 → Agent 把真实成功结果丢掉，给模型塞 `"Error: Function failed."`（误判「MATLAB/Mongo 工具坏了 / 超时调大 / stdio 不稳」）
- **为何够深（非科普）：** 主线锁 **「订阅了 list_changed ≠ 可以在 receive 回调里再发 RPC」**。三层可拆：(1) **重入死锁**：notification handler 与 in-flight request 共享同一条 receive loop，handler 内 await 任何需要响应的 RPC（`list_tools` / `list_prompts` / 甚至 `_ensure_connected`→`ping`）都会把自己卡死（microsoft/agent-framework #4828 + PR #4866 原文机制）；(2) **失败伪装**：SDK 直连同一 server 成功，Host 封装路径超时后把假错误喂给模型——值班会去查工具实现，而不是 Host 的 handler；(3) **与「不刷新」对称的另一极**：只打日志 / fire-and-forget 不 await → 下一轮仍用旧目录（Zed #57473；与已发 `mcp-progressive-disclosure` 的「通知≠刷新」相邻但更窄：本篇坏的是**在途 call 的完成**，不是下一轮召回）。GOOD：把 reload 排成后台 Task、立刻让出 receive loop（#4866 `_schedule_reload`）；或只脏标记缓存、在 turn 边界 / 显式 `connect(reset=True)` 再拉；下一轮推理前 await 在途 refresh（Zed #57473 提议）。不是「怎么订阅 list_changed」入门
- **拟用案例 / 对照：**
  1. **BAD#1 Host handler 内 await reload → 死锁（Microsoft Agent Framework Python）** #4828（closed **completed**；fix PR #4866 merged 2026-05-13，base `main`）：`matlab-mcp-core-server` 在工具执行期发 `tools/list_changed`；直连 `mcp.ClientSession.call_tool("detect_matlab_toolboxes")` 成功（`isError=False`），经 `MCPStdioTool` 则 `ToolExecutionException` 超时；Agent 第二轮请求的 `function_call_output` 是 verbatim `"Error: Function failed."`。PR #4866 钉死：handler 跑在 SDK 单线程 `_receive_loop` 上，`await load_tools()` → `list_tools` 响应无法投递
  2. **BAD#2 同类死锁的竞争修复曾想「改成只打日志」** #4896（closed completed 2026-05-14；症状原文是 mongodb-mcp-server 在工具执行中发 `resources/updated`，`list-collections` 经 `MCPStdioTool` 挂死，直连 SDK 成功）交叉引用未合的 PR #4898（closed **未合**）：把 inline reload 改成 debug log——能消死锁，但立刻退回「通知到了目录不刷」。真正合入的是 #4866 的后台 Task 路线；**不要把 #4896 的 resources/updated 症状写成 #4866 已证明修复的同一条 bug**（关闭时间紧随 #4866，但 PR 正文与测试针对的是 list_changed / load_tools）
  3. **BAD#3 另一极：detach 刷新、不等待 → 首轮调新工具失败（Zed）** #57473（closed **not_planned**，`github-actions` stale bot，**未修复**）：meta-tool 加载新工具后 server 先发 `tools/list_changed` 再回 `tools/call` result；Host `detach` 刷目录，agent 下一 turn 仍用旧 registry → tool not found，模型重试才成功。与 BAD#1 同属「list_changed 生命周期」，失败面是**下一轮发现**而非**本轮 call 完成**
  4. **旁证：** editor-code-assistant/eca@8746ab0 — plumcp 默认 list_changed handler 在 initialize 完成前就 `fetch-tools`，server 忽略 initialize 前请求 → handler 永久等待，客户端无法完成握手（pre-initialize 死锁变体）；livekit/agents #5378（open）+ PR #5604（open 未合）— 完全忽略 list_changed（更靠近已发 progressive-disclosure，只作「Host 常见三种坏法」对照，不当事主线复现）
  5. **GOOD：** notification handler 只调度、不 await RPC（#4866 `_schedule_reload` + 强引用 Task 防 GC）| 缓存脏标记，turn 边界 / 显式 reload 再 `list_tools` | 下一轮拼 tools 前 await 在途 refresh（#57473）| 指标：`call_tool` 超时且直连 SDK 成功的次数；unknown/missing tool 在 list_changed 后首轮的次数
- **§4 业务线：** 同一台工程计算会话 `ENG-4410`：Host 挂 MATLAB MCP，工具 `detect_matlab_toolboxes` 跑完会发 `tools/list_changed`（工具目录随 toolbox 探测变化）。**BAD v1**：Agent Framework `MCPStdioTool` 在 message_handler 里 `await load_tools()` → receive loop 卡死 → `detect_matlab_toolboxes` 已在 server 侧跑完，模型只看到 `"Error: Function failed."`，值班去重装 MATLAB（回扣 §3.1–§3.2）。**BAD v2**：团队「修复」成 handler 只打日志 → 死锁没了，但后续 `run_simulation` 新工具永远不进目录，模型坚持「没有仿真工具」（回扣 §3.3 / 与 progressive-disclosure 互链一句）。**GOOD**：handler 调度后台 reload；本轮 `call_tool` 先完成；下一 turn 前 await 刷新后的目录；`ENG-4410` 第一次就拿到 toolbox 列表并看见新工具（回扣 §3.1–§3.3）
- **§5 可注入失败点：**
  1. **注入：** mock server 在 `tools/call` 返回前同步发出 `notifications/tools/list_changed`；Host 使用「handler 内 await list_tools」路径 → **期望：** `call_tool` 在超时前返回真实结果；无 `"Error: Function failed."`
  2. **注入：** 同 1，但 handler 改为后台 Task reload → **期望：** 本轮结果正确；随后 `list_tools` 缓存更新（或脏标记后下次拉取为新目录）
  3. **注入：** meta-tool 加载新工具后，list_changed 与 call result 同流到达，立即开下一 agent turn 调新工具 → **期望：** 首轮即命中新工具，或明确等待 refresh，而不是 tool not found 后再撞大运重试
- **领域标签：** MCP Host / Client Protocol Dispatch · Notification Handler Reentrancy · Stdio Receive Loop
- **专题归属：** **Agent Runtime Failure Handling**（续篇 #4：#1 分层重试；#2 取消未下发；#3 progress 与 result 分发顺序；本篇 = 成功路径上的 list_changed 通知处理把「已成功的 tools/call」卡成超时假失败）
- **相关已发文 / 边界：**
  - vs published `mcp-progressive-disclosure`：那篇现象 E = list_changed 到了 Host **不刷 / 只打日志** → 目录陈旧、召回 miss；本篇 = Host **刷了但刷在 receive 回调里 await** → 本轮 call 死锁。互链一句「通知≠刷新」后立刻转到重入，不重讲 Tool Search / Inspect / cache
  - vs ready `mcp-progress-same-chunk-unknown-token`：那篇 = progress 通知与 result 的微任务顺序；本篇 = list_changed 通知 handler 里再发 RPC。同属协议分发，失败信号不同（unknown token / 断连 vs call 超时假失败）
  - vs published `mcp-cancellation-not-propagated` / `mcp-server-instance-reuse-cross-client-leak`：取消生命周期与多客户端实例复用；本篇是单连接 receive loop 重入
  - vs published `mcp-output-schema-validation-swallows-tool-errors`：那篇结果内容被校验换掉；本篇结果根本没回到 Host
  - vs ready `tool-approval-cross-run-transfer`：审批键空间；与 list_changed 无关
- **参考线索：**
  - https://github.com/microsoft/agent-framework/issues/4828 — **主证据（issue，closed completed）**；直连 SDK 成功 vs Host 封装超时；模型侧 verbatim `"Error: Function failed."`
  - https://github.com/microsoft/agent-framework/pull/4866 — **主证据（fix PR，merged 2026-05-13，base `main`，merge `7d23582e`）**；机制原文 + `_schedule_reload`；含回归测试
  - https://github.com/zed-industries/zed/issues/57473 — **主证据（issue，closed not_planned by stale bot，未修复）**；list_changed 后首轮 tool not found 的对称坏法
  - https://github.com/microsoft/agent-framework/issues/4896 — 旁证（closed completed；resources/updated 挂死；关闭紧随 #4866，勿断言同一修复覆盖）
  - https://github.com/microsoft/agent-framework/pull/4898 — 旁证（closed **未合**）：曾提议用「只打日志」消死锁
  - https://github.com/editor-code-assistant/eca/commit/8746ab0c56485f697e31cb8d47cac61bed47c4d4 — 旁证：initialize 前 list_changed handler 死锁
  - https://github.com/livekit/agents/issues/5378 / https://github.com/livekit/agents/pull/5604 — 旁证（PR open 未合）：忽略 list_changed
- **备注：** Gate PASS ready — Thu 2026-10-29 refill（读 #4828 / #4866 / #4896 / #4898 / #57473 正文与 API 状态；eca commit message；livekit #5378/#5604）。写稿禁令：允许引用 #4828 日志逐字超时 `Timed out while waiting for response to ClientRequest. Waited 30.0 seconds.`；并注明 PR #4866 正文写 “Fixes #4828 and #4896”。不要写「MCP 客户端都会死锁」——问题在 Host 把 await RPC 放进 SDK message_handler 的封装，直连 ClientSession 的路径在 #4828/#4896 里都成功；不要写 Agent Framework「仍必现」——#4866 已合 main（写稿前核 release 版号是否包含 7d23582e）；不要把 #4896 的 `resources/updated` 症状说成 #4866 回归测试覆盖的同一条；#57473 是 bot not_planned，不是维护者拒绝修复；#4898 未合，不能当 GOOD；livekit 忽略通知更靠近 progressive-disclosure，正文最多一句对照；§4 `ENG-4410` 是设计示例。P1。

### [idea] 2026-10-08 | P2 | mcp-sampling-server-controlled-prompt
- **工作标题：** MCP Sampling：Server 借 Client 的模型说话
- **失败面（MCP Client sampling 信任边界，非 tool description 投毒）：** Server 通过 `sampling/createMessage` 控制 prompt 和 `systemPrompt` 并消费补全 → 隐藏指令消耗配额 / 劫持后续对话 / 诱发隐蔽工具调用
- **为何仍是 idea：** 目前只有 Unit 42 研究博文和第三方汇总，**缺 primary source**（advisory / fix commit / client issue）；需要找到真实 Client 实现在 sampling 审批 / 隔离上的缺陷再升 ready
- **专题归属：** 候选 MCP 协议信任边界（与 MCP-Auth 相邻）
- **参考线索：**
  - https://unit42.paloaltonetworks.com/model-context-protocol-attack-vectors/ — 三类攻击向量（研究，非 primary）
- **备注：** Scout 2026-10-08 留 idea；升级条件：≥1 条 Client 侧 advisory / issue + 修复对照。**Fri 2026-10-16 复查：仍不升 ready。** (1) 唯一新线索 rmcp（Rust SDK）≤3.0.1 接受未关联原始请求的 server→client 请求（含 `sampling/createMessage`），3.1.0 以 SEP-2260 修复——但目前只在 Aikido 的 pre-CVE 聚合页（AIKIDO-2026-617985，2026-08-03）看到，未找到仓库侧 advisory / PR，不算 primary；(2) MCP 规范页（2026-07-28 版）已写明 Sampling 自该版起 deprecated（SEP-2577），新实现不应采用——选题价值下降，倾向 park；(3) 同一轮发现的真 advisory（GHSA-345p-7cg4-v4c7，TS SDK 共享 server / transport 导致 sampling / elicitation 等 server→client 消息串到别的 client）已另立 ready `mcp-server-instance-reuse-cross-client-leak`，不复用本条。

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
- 2026-10-09 Coordinator: published `subagent-delegation-envelope` → posts/subagent_delegation_envelope.md (Reviewer Approve → immediate push; Tool-Policy Assembly #2).
- 2026-10-10 Scout: Sat round (Alice 触发) — add ready `layered-retry-amplification` (P1, new Agent Runtime Failure Handling #1; nanobot PR #2759 / hermes-agent PR #53918 / gh-aw PR #47237, all merged) + `streaming-tool-call-index-collision` (P2, Session-State Integrity #3; openai-python PR #3425 / litellm PR #21337 / unsloth PR #10059, all merged); correct subagent-delegation-envelope (4 处: #7474 not planned + #7473 unmerged; #26597 regression + #27201 partial; Claude Code plan mode ≠ ceiling; `agent_id` claim removed — mis-attributed to sub-agents doc, actually in hooks doc); re-verify orphan-tool-call-session-wedge + compaction-drops-pinned-instructions (both PASS, close reasons / merge states annotated; [2026-10-16 更正：当时把 #23776 与 #14941 当作同一条去重链，Fri 10-16 复查确认两者症状不同——#23776 条件指令被压平，#14941 问句后被「继续任务」推去实现——不是同一个 bug]); skip computer-use grounding / structured-output schema drift / eval grader drift (not evidence-checked to primary-source level this round); keep mcp-sampling as idea.
- 2026-10-12 Coordinator: published `orphan-tool-call-session-wedge` → posts/orphan_tool_call_session_wedge.md (Reviewer Approve → immediate push; Session-State Integrity #1).
- 2026-10-14 Coordinator: published `layered-retry-amplification` → posts/layered_retry_amplification.md (Reviewer Approve → immediate push; Runtime Failure Handling #1).
- 2026-10-16 Scout: Fri refill PR — strict re-check `compaction-drops-pinned-instructions` (PASS ready, weak evidence; 5 claims corrected) + `streaming-tool-call-index-collision` (PASS ready; same-index = fragments of one call, staging-branch/open-PR states annotated); correct published `orphan-tool-call-session-wedge` (#45286→#31328 both unfixed; drop Azure #46092; verbatim #6836 error) and `layered-retry-amplification` (gh-aw #47237 diff = env var + 3 tests; WAIT/CAP/STOP from community commenter; 120s cap in conversation_loop.py; #47217 auto-report); add ready `mcp-server-instance-reuse-cross-client-leak` (P2, new MCP Server Runtime Boundaries #1; GHSA-345p-7cg4-v4c7 / TS SDK v1.26.0 / PR #2918); keep mcp-sampling as idea (deprecated in 2026-07-28 spec; rmcp lead unverified).
- 2026-10-16 Coordinator: published `compaction-drops-pinned-instructions` → posts/compaction_drops_pinned_instructions.md (Reviewer Approve → immediate push; Session-State Integrity #2; commit 4921c420, duplicate-content 699b3f73).
- 2026-10-21 Scout: Wed verify PR — correct published `streaming-tool-call-index-collision` (7 publish-note discrepancies re-checked against API + pages: #3203 = reporter-closed with state_reason=duplicate → #3201, page shows "Closed as duplicate"; quote source = #3203 repro-script comment, not PR #3232; "Kimi 2.6" verbatim; #21331 closed completed 2026-03-02 UTC; #21337 merged into staging branch, release unverified; #37792 open, #33682 / #39012 closed unmerged per API; unsloth slot / glued-name claims are PR-body only, no call count); correct ready `mcp-server-instance-reuse-cross-client-leak` mechanism per GHSA-345p Impact/Patches (final responses can mis-route → requester timeout; in-request progress/sampling/elicitation leak silently only on JSON-RPC id collision, else throw; spontaneous → last-connected), PASS keep ready; add ready `mcp-cancellation-not-propagated` (P2, Runtime Failure Handling #2; python-sdk #2507 / PR #2838 / #2416) + `tool-call-id-rewrite-cross-provider` (P2, Session-State Integrity #4; litellm PR #40872 / #34522 / #26060); keep mcp-sampling as idea. Ready = 3; Writer order: mcp-server-instance-reuse-cross-client-leak → mcp-cancellation-not-propagated → tool-call-id-rewrite-cross-provider.
- 2026-10-25 Scout: rebuild stale #83 onto current main after `mcp-cancellation-not-propagated` published (commit 07c1590a; main tip later rolled traffic). Folded the five MCP-reuse Writer/Reviewer 10-21～22 corrections into published-entry **Scout 更正** notes (no posts/ rewrite); kept cancellation `published` and recorded A/B/C-by-`notifications/cancelled` + #2480 comment-vs-API divergence as backlog alignment; retargeted cancellation / tool-call-id / output-schema boundary lines to `vs published` for reuse (+ cancellation for output-schema); added ready `mcp-output-schema-validation-swallows-tool-errors` (P2, MCP/Host Tool-Result Fidelity #2; TS #2748 / Python #2429 / TS #2612). Ready = 2; Writer order: tool-call-id-rewrite-cross-provider → mcp-output-schema-validation-swallows-tool-errors.
- 2026-10-26 Coordinator: Reviewer Approve → publish posts/tool_call_id_rewrite_cross_provider.md (Agent Session-State Integrity #4); backlog tool-call-id-rewrite-cross-provider → published. Ready left 1 (mcp-output-schema-validation-swallows-tool-errors).
- 2026-10-27 Scout: Tue refill — after tool-call-id published; main Ready was 1. +2 ready (P1): `mcp-progress-same-chunk-unknown-token` (Runtime Failure Handling #3), `tool-approval-cross-run-transfer` (Session-State Integrity #5). Ready on head = 3; Writer order: mcp-output-schema-validation-swallows-tool-errors → mcp-progress-same-chunk-unknown-token → tool-approval-cross-run-transfer.
- 2026-10-28 Coordinator: Reviewer Approve → publish posts/mcp_output_schema_validation_swallows_tool_errors.md (MCP/Host Tool-Result Fidelity #2); backlog mcp-output-schema-validation-swallows-tool-errors → published. Ready left 2 (mcp-progress-same-chunk-unknown-token, tool-approval-cross-run-transfer).
- 2026-10-29 Scout: Thu refill — main Ready was 2 after output-schema published. Fold #5332 (merged 2026-10-14) into ready `tool-approval-cross-run-transfer` (#5327 closing PR). Add ready `mcp-list-changed-reload-blocks-receive-loop` (P1, Runtime Failure Handling #4; agent-framework #4828 / PR #4866 merged + Zed #57473 not_planned). Keep mcp-sampling as idea. Ready = 3; Writer order: mcp-progress-same-chunk-unknown-token → tool-approval-cross-run-transfer → mcp-list-changed-reload-blocks-receive-loop.
