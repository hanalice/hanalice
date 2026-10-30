# Posts Tagged With: #Agent

Total: 22 posts

---

- [2026-10-30] [进度通知和结果同一包到了：客户端先删 handler，再把「未知 token」当成断连](../posts/mcp_progress_same_chunk_unknown_token.md)
- [2026-10-28] [工具报了错，模型却只看到 -32602：MCP outputSchema 校验把 tool error 吞成协议错误](../posts/mcp_output_schema_validation_swallows_tool_errors.md)
- [2026-10-26] [换了个模型，会话就 400 了：tool call id 在跨 provider 重放时被改写](../posts/tool_call_id_rewrite_cross_provider.md)
- [2026-10-23] [客户端超时了，工具还在跑：MCP 取消没过线，迟到的取消又把连接打断](../posts/mcp_cancellation_not_propagated.md)
- [2026-10-22] [MCP Server 实例复用：一个 McpServer 连两个客户端，响应、elicitation 与通知各按自己的条件发错地方](../posts/mcp_server_instance_reuse_cross_client_leak.md)
- [2026-10-19] [流式 tool call 的身份键坍缩：并行调用被拼成一个坏 call，在进历史之前就已经坏了](../posts/streaming_tool_call_index_collision.md)
- [2026-10-16] [Compaction 之后 Agent 忘了「先给我看计划」：被摘要掉的不是历史，是约束](../posts/compaction_drops_pinned_instructions.md)
- [2026-10-14] [一个 429 打出成倍的上游请求：Agent 重试叠在 SDK 自动重试上，调用链没有唯一 retry owner](../posts/layered_retry_amplification.md)
- [2026-10-12] [一次中断，整个会话永久 400：tool_use / tool_result 配对不变量要在写入侧闭合](../posts/orphan_tool_call_session_wedge.md)
- [2026-10-09] [子代理一派生，父会话的权限没跟过去：Delegation Envelope 不是「继承」两个字](../posts/subagent_delegation_envelope.md)
- [2026-09-30] [工具策略「滤完了」：MCP/LSP 却在过滤之后才拼进来](../posts/host_tool_policy_merge_after_filter.md)
- [2026-09-28] [静默截断：工具「成功返回」了半截，模型却自信答完](../posts/silent_tool_result_truncation.md)
- [2026-09-23] [MCP Consent Binding：Consent 绿了，IdP callback 没绑到同意过的浏览器（Confused Deputy）](../posts/mcp_consent_binding_confused_deputy.md)
- [2026-09-22] [MCP Auth：Identity ≠ Audience——OAuth 绿了，token 没绑到这台 MCP](../posts/mcp_auth_identity_not_intent.md)
- [2026-09-22] [专员互相转交都「成功」：无终止谓词的 Handoff 环](../posts/multi_agent_closed_loop_handoff.md)
- [2026-09-21] [Agent 记得太久：Session Summarization 把间接注入写成跨会话「系统指令」](../posts/agent_memory_poisoning.md)
- [2026-09-18] [长跑 Agent 挂了：Checkpoint 不等于 Durable Execution](../posts/durable_agent_execution.md)
- [2026-09-17] [长程 Agent：第一个错 ≠ 决定性错误](../posts/long_horizon_decisive_error.md)
- [2026-09-16] [Agent 写操作的幂等：超时之后凭什么敢重试](../posts/agent_write_idempotency.md)
- [2026-09-15] [MCP 工具设计：为什么 Agent 总发出「合法但错误」的调用](../posts/mcp_tool_design_valid_but_wrong.md)
- [2026-09-15] [Trajectory Eval：答对了为什么还是假绿](../posts/trajectory_eval_false_green.md)
- [2017-08-07] [使用ssh-agent 管理多个ssh key](../posts/ssh-agent.md)

---
[← Back to Home](../README.md)