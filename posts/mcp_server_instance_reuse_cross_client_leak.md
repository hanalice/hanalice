---
title: MCP Server 实例复用：一个 McpServer 连两个客户端，响应、elicitation 与通知各按自己的条件发错地方
date: 2026-10-22
tags: Agent, MCP, Server-Runtime, Transport, Multi-Tenant
description: 多个客户端共用一个 McpServer 或无状态 transport 时，后连者覆盖 _transport：最终响应错投、发起方超时；id 碰撞时 progress、elicitation 静默串给别人；主动通知总发给最后连接者。修法是每连接一个实例加 fail-fast 守卫。MCP Server Runtime Boundaries 系列第 1 篇。
---

## 1. 问题现象 (Problem Symptoms)

结论先行：**在 MCP TypeScript SDK 里，一个 `McpServer` / `Server` 对象只能对应一个连接，一个无状态的 `StreamableHTTPServerTransport` 只能处理一个请求。** 把它们复用给多个并发客户端，坏掉的不是某一类消息，而是三类消息按三种不同的条件发错地方：最终响应可能被投到另一个客户端的 transport，发起方只看到超时；handler 执行中发出的 progress、sampling、elicitation 只有在 JSON-RPC id 碰撞时才**静默**串到别的客户端，不碰撞时 transport 直接抛错；handler 之外的主动通知不需要任何条件，总是发给最后连上的那个客户端。官方在 1.26.0 的修法不是加隔离层，而是让复用直接报错，所以**升级之后开始报错是预期行为**，要改的是代码结构。

这是新专题 **MCP Server Runtime Boundaries** 的 #1：讲 MCP Server 在运行时的隔离边界，这一篇是「连接实例」这条边界。它和本站已发的两篇 MCP 安全文不在同一层：

| 文章 | 层 | 问的是 / 和本文的交点 |
| --- | --- | --- |
| [MCP Auth：Identity ≠ Audience](posts/mcp_auth_identity_not_intent.md) | OAuth token 的受众绑定 | 那篇：token 有没有绑到这台 MCP。本文：认证和授权都通过了，payload 在 server 进程内部被路由到了另一个客户端的连接，不涉及 token |
| [MCP Consent Binding](posts/mcp_consent_binding_confused_deputy.md) | consent ↔ callback 的浏览器绑定 | 那篇：授权流程里的委托方被混淆。本文：授权之后的数据面，实例复用造成错路由 |
| [流式 tool call 的身份键坍缩](posts/streaming_tool_call_index_collision.md) | 流式 delta 的组装键 | 同属「按 id / index 键的映射被碰撞」。那篇的键是流式片段属于哪个调用；本文的键是 JSON-RPC 请求 id 属于哪条连接。只在这里互链一句 |
| **本文**（MCP Server Runtime Boundaries #1） | MCP Server 的连接作用域 | 一个 server 对象 / 一个 transport 同时服务了几个客户端 |

证据范围先说清：下面的机制全部来自官方 advisory [GHSA-345p-7cg4-v4c7](https://github.com/advisories/GHSA-345p-7cg4-v4c7)（CVE-2026-25536）、v1.26.0 release 和主线修复 PR [#2918](https://github.com/modelcontextprotocol/typescript-sdk/pull/2918)。**这只是 TypeScript SDK 的实现问题，不是 MCP 协议的漏洞**；advisory 只覆盖 `@modelcontextprotocol/sdk`，Python / Rust / Go SDK 是否有同类问题，我们没有核实，不做推断。下面三个现象「看起来都合理」，因为每一种写法都曾是社区里常见的写法。

### 现象 A：无状态模式下，一个 transport 给所有请求用

为了「省掉每次请求的构造开销」，服务启动时建一个 `McpServer`、一个 `sessionIdGenerator: undefined` 的 `StreamableHTTPServerTransport`，每个 HTTP 请求都交给这同一个 transport。

advisory 的 Issue 1 说明了后果：transport 内部维护一张 `requestId → stream` 的映射，而 SDK 默认客户端的 JSON-RPC id 是**从 0 开始递增的计数器**，两个客户端天然会产生相同的 id。第二个客户端的请求覆盖第一个客户端的映射项，响应被发到错误的 HTTP 流上。受影响的是**所有请求类型**（`tools/call`、`resources/read`、`prompts/get` 等），不需要任何 server 主动发起的功能。

### 现象 B：transport 改成每请求新建，server 仍是全局一个

团队发现了 A，改成每个请求新建 transport，但 server 对象（连同上面注册的全部工具）仍然是启动时建的那一个，每个请求都 `server.connect(transport)`。`tools/call` 的结果看起来都对了，但只要工具在执行中发 progress、发起 sampling（`createMessage`）或 elicitation，就会偶发报错；上线到多租户高并发之后，报错没了，换成了一个客户端收到另一个客户端的 elicitation。

这是 advisory 的 Issue 2：`Protocol` 内部只有一个 `this._transport` 引用，第二次 `connect()` 会**静默覆盖**它。handler 执行中发出的消息走的是这个共享引用，此时它可能已经指向别人的 transport。

### 现象 C：上了 `sessionIdGenerator`，以为每个会话已经隔离

再进一步，团队改成有状态模式：每个会话一个 transport，用 `mcp-session-id` 查表。但 server 还是共享的。这时出现了第三种症状：某个会话里一个普通的 `tools/call` 偶发超时，重试又好了；server 主动推送的通知只有最新连上的那个会话收得到。

advisory 明确写了这一点：**用了 `sessionIdGenerator`、但跨会话共享一个 `McpServer`，仍然受 Issue 2 影响。** 「我们有 session id」不等于「我们有每会话的 server 实例」。

这类写法确实常见：[#204](https://github.com/modelcontextprotocol/typescript-sdk/issues/204)（2025-03-17 提出，closed completed）里提问者贴的就是一个 `McpServer` 配多个 SSE transport 的写法，并指出 `server.connect(transport)` 会替换已有的 transport；PR #2918 的描述里也写明，主线 express / fastify / hono / node 各包的 README 示例、两个 Streamable HTTP server transport 的 JSDoc 示例和底层 server 指南，此前展示的都是「所有请求共用一个 server，或共用一个无状态 transport」，这个 PR 才改成每请求一套。#204 是提问类 issue，不是漏洞报告，这里只用来说明写法常见。

三个现象的共同点：**症状随并发度和 id 分布变化。** 低并发的测试环境里是偶发报错、偶发超时，最常见的误判是「网络抖动」「客户端超时设短了」「SDK 不稳定」；只有在并发足够高、id 正好撞上时，它才变成没有任何报错的跨客户端泄漏。

---

## 2. 根因分析 (Root Cause Analysis)

根因只有一条：**违反了连接实例的所有权不变量**，即一个 server 对象 = 一个连接，一个无状态 transport = 一个请求。难排查的地方在于，违反之后三类消息的泄漏条件各不相同。下面的表按 advisory Impact 节整理：

| 复用了什么 | 消息类型 | 走哪条路由 | 发错的条件 | 表现 |
| --- | --- | --- | --- | --- |
| 无状态 transport（Issue 1） | 所有请求的响应 | transport 内 `requestId → stream` 映射 | 两个客户端的 JSON-RPC id 相同，后到的覆盖先到的 | 响应进了别人的 HTTP 流 |
| server 对象（Issue 2） | ① 最终响应 | 处理请求时捕获的 `this._transport` | 请求在第二次 `connect()` **之后**才经旧 transport 到达；不需要 id 碰撞 | 响应被路由到新 transport，**发起方超时** |
| server 对象（Issue 2） | ② handler 执行中的 progress / sampling / elicitation | 共享的 `this._transport` | 新 transport 上存在与本请求**相同 id** 的请求 | 碰撞：**静默**发给另一个客户端；不碰撞：transport **抛错**，不会错发 |
| server 对象（Issue 2） | ③ handler 之外的主动通知 | 共享的 `this._transport` | 无条件 | **总是**发给最后连接的客户端 |

这张表有三点要说清：

1. **「共享 server 就一定静默泄漏」是错的。** 只有第 ② 类要求 id 碰撞才会静默；第 ① 类的表现是超时而不是泄漏，第 ③ 类不需要碰撞。把三者混成一句「会串数据」，排查时就会在错误的地方找证据：盯着 id 碰撞查，会漏掉超时和主动通知；只看有没有异常日志，会漏掉静默的那一类。
2. **id 碰撞在这里不是罕见的边角情况。** advisory 写明 SDK 默认客户端的 id 是从 0 开始递增的计数器，所以两个刚连上、节奏相近的客户端很容易产生相同的 id。真正决定碰不碰撞的是并发时序，这就是它在测试里是偶发报错、上线后变成静默泄漏的原因。
3. **最终响应的路由规则，advisory 自己的两处表述不一致。** Issue 2 的「What happens」一段写「最终响应路由正确（Protocol 在请求时捕获 transport 引用）」，紧接着的「What is affected」又写最终响应「多数情况下受影响」：在第二次 `connect()` 之前已经在途的请求，捕获的引用正确；在覆盖**之后**才到达旧 transport 的请求，捕获到的是新 transport，响应错投，发起方超时。本文按后者更细的说明写。

还有一层误判要拆开：**认证、session id、租户字段都管不了这一层。** advisory 的 CVSS 向量里权限要求是 `PR:L`（低权限），也就是说触发条件是一个普通的已接入客户端；鉴权通过之后，错路由发生在 server 进程内部的对象引用上。在这一层加鉴权，或者在 payload 里加租户 id，都不能阻止一条消息被写进另一个客户端的流。

---

## 3. 机制要点：实例所有权、按消息类分析、fail-fast、生命周期收口 (Mechanism)

先给范围：3.1 和 3.3 有官方修复可对照；3.2 是排查方法；3.4 的前半出自 advisory Patches 节，后半「handler 在副作用前自己检查 signal」是本文主张；3.5 是测试策略。

### 3.1 一个 server 对象 = 一个连接；复用注册表，不复用连接对象

- **无状态模式：每个请求新建 server + transport；有状态模式：每个会话新建 server + transport。** 这是 advisory Workarounds 节给出的两种形态，也是 PR #2918 改写后 README 示例的形态。
- **要复用的是工具定义，不是连接对象。** 把 `registerTool` / `registerResource` 等注册逻辑收进一个工厂函数 `buildServer()`，每次连接调用一次；工具的 schema、handler 函数本身可以是模块级常量，被每个实例引用。构造开销如果真成了问题，优化的方向是让工厂更轻，而不是共享实例。
- 边界：工厂只解决「对象共享」。handler 闭包里如果引用了模块级的可变状态（例如「当前用户」这类全局变量），同样会跨客户端串，这不是本文的 SDK 问题，但同一次代码评审里要一起查。

### 3.2 排查时按消息类别分开判断影响面

对照 §2 的表，问三个问题，而不是问「有没有串数据」：

1. 有没有共享无状态 transport？有 → 所有请求类型都可能串（Issue 1）。
2. 有没有共享 server 对象（无论有没有 `sessionIdGenerator`）？有 → 按工具是否在执行中发 progress / sampling / elicitation、server 有没有主动通知，逐类判断（Issue 2）。
3. 是否只有单客户端（例如本地一个 IDE）？advisory 写明单客户端环境不受影响。

advisory 的「How to tell if you're affected」给了逐形态的结论，其中一条容易被忽略：**无状态、每请求新 transport、但共享 server → 只受 Issue 2 影响；工具只返回结果、执行中不发 progress / sampling / elicitation 时是安全的。** 这意味着同一套代码的风险会随某个工具「加了个进度条」而改变，评审时要看工具行为，不能只看入口代码。

另外，**偶发超时要算进证据。** 第 ① 类的表现就是发起方超时；如果某个工具只在多客户端并发时偶发超时，先查实例是否共享，再去调超时。

### 3.3 fail-fast：把静默错路由变成立即报错

advisory Patches 节列出 1.26.0 的守卫：

1. `Protocol.connect()` 在已连接 transport 时抛错，阻止静默覆盖（对应 Issue 2）；
2. 无状态 `StreamableHTTPServerTransport.handleRequest()` 被第二次调用时抛错，强制无状态模式下一个 transport 只处理一个请求（对应 Issue 1）；
3. 见 3.4。

advisory 还写明，之前错误复用实例的服务升级后会收到明确的报错，提示为每个连接创建独立实例。v1.26.0 的 release notes 只写了「Addresses … GHSA-345p-7cg4-v4c7」，没有单列修复 PR 或守卫细节，所以守卫内容以 advisory 为准。

主线（`packages/server`）的 PR #2918（2026-10-02 UTC 合入）把同样的规则落到新包里，PR 自述「1.x 线自 1.26.0 起已有前两项检查」。**以下错误名和状态码只出自这个 PR，1.x 的报错文案我们没有核：**

- `Server.connect()` / `McpServer.connect()` 在已连接时以 `SdkErrorCode.AlreadyConnected` 拒绝（升级说明里写作 `ALREADY_CONNECTED`）；`close()` 之后可以再次连接。
- 无状态 `WebStandardStreamableHTTPServerTransport` 拒绝第二次 `handleRequest()`；包装它的 `NodeStreamableHTTPServerTransport` 对第二个请求回 `500`。
- `createMcpHandler` 的工厂返回了一个仍在服务其他请求的实例时，回 `500`（`-32603`）并调用 `onerror`，正在进行的那个请求照常完成。
- 报错落到哪里取决于宿主：Express 5、Fastify、Hono 回 `500`；**没有自己错误处理的裸 `node:http` 监听器会得到一个未处理的 rejection，进程直接退出。**

工程含义有两条：

- **升级就是一次结构检查。** 共享实例的服务升级后会在第一个重叠请求（有状态模式是第二个会话的 `initialize`）上报错，这是预期行为。不要为了「让它不报错」去降级或吞掉这个错误。
- **入口处必须有错误处理。** 否则 fail-fast 会从「一个请求 500」变成「整个进程退出、所有在途请求一起丢」。

### 3.4 生命周期收口：close 时取消在途 handler，发送前检查 abort signal

Patches 第 3 项（只出自 advisory，PR #2918 的描述里没有这一项）：`close()` 时清理在途请求 handler 的 abort controller，handler extras 里的 `sendNotification` / `sendRequest` 在发送前检查 abort signal，防止 transport 被替换之后还有消息漏出去。

为什么守卫 1 之外还需要这一条：`close()` 之后同一个对象可以重新 `connect()`（PR #2918 明确保留了这种用法）。如果旧连接上还有没跑完的 handler，它后续发出的 progress 不能落到新连接上。

本文的补充主张（不是 SDK 现有行为）：SDK 只在**发消息**这一步检查 signal（advisory Patches 第 3 条：`sendNotification` / `sendRequest` 发送前检查 abort signal）；handler 自己在执行**副作用**之前（写库、调外部服务、把文件发给第三方）也要检查一次 `signal.aborted`。否则连接已经关了，消息虽然发不出去，副作用照样做完。

### 3.5 测试要有重叠请求和碰撞的 id，「顺序跑一遍是绿的」不算数

- **顺序测试测不出来。** PR #2918 的升级说明里有一条：一个 server 对象、每请求新建无状态 transport，并且在响应结束时 close transport 的写法，升级后**只有重叠的请求会失败**。也就是说，只做顺序请求的集成测试，修复前看不到泄漏，修复后也看不到报错。
- **id 要故意撞上。** 两个测试客户端都用 SDK 默认、从 0 开始的 id，让它们的请求在时间上重叠；只有这样才能覆盖 §2 表里的第 ② 类。
- **超时不等于没执行。** 第 ① 类里发起方看到的是超时，而它的工具很可能已经在 server 端执行完了；如果那是写操作，重试前要按 [Agent 写操作的幂等](posts/agent_write_idempotency.md) 的思路先查状态，这里不展开。

---

## 4. 同一个服务 `svc_review-bot`：怎么接、错在哪、改完怎么走

业务线固定为一个多租户代码审查 agent 服务 `svc_review-bot`：租户 A 的会话 `sess_A-17` 和租户 B 的会话 `sess_B-04` 同时在跑，两边客户端都用 SDK 默认、从 0 开始递增的 JSON-RPC id，都会调用同一个工具 `review_diff`。这个工具在执行中会发 progress（带当前文件名），并向客户端发起 elicitation：「是否把这个文件发给外部 linter？」。下面的场景和代码都是我们构造的**示意**，用的是 1.x 风格的 API 名，不是任何真实事故或开源项目的实现；advisory 确认了 sampling / elicitation 会被错路由，但没有公开的真实受害案例。

为了让每一版的差异看得见，固定一个时序：A 先连上；A 的第 4 个请求（`id: 3`）是 `tools/call review_diff`，正在执行；这时 B 连上，B 的第 4 个请求恰好也是 `id: 3`，也在执行中。两边的 id 都从 0 开始，所以撞上 `id: 3` 不需要任何巧合，只需要两边节奏相近。

### 4.1 BAD v1：一个 server、一个无状态 transport，服务所有请求

```ts
// 示意：svc_review-bot v1 —— 启动时建一次，所有 HTTP 请求共用
const server = buildReviewServer();                       // 注册 review_diff 等工具
const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
await server.connect(transport);

app.post('/mcp', async (req, res) => {
  await transport.handleRequest(req, res, req.body);      // A 和 B 的请求都进这同一个 transport
});
```

A 的 `id: 3` 先在 transport 的 `requestId → stream` 映射里登记了 A 的 HTTP 流；B 的 `id: 3` 到达后覆盖了这一项。A 的 `review_diff` 返回时，结果按 `id: 3` 查表，被写进了 B 的 HTTP 流：B 收到一份 A 仓库的审查结果，A 一直等不到响应。这不依赖任何 progress 或 elicitation，`resources/read`、`prompts/get` 同样会串（advisory Issue 1）。

低并发的冒烟测试里，两个请求很少重叠，这一版是绿的。

修复方向：一个无状态 transport 只处理一个请求，见 v2（回扣 §3.1）。

### 4.2 BAD v2：transport 每请求新建，server 仍是全局一个

v2 只改了一处：transport 移进 handler，server 保持全局。

```ts
// 示意：v2 —— 相对 v1 只改这里：每个请求新建 transport；server 仍在模块级共享
const server = buildReviewServer();

app.post('/mcp', async (req, res) => {
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });  // 新增
  await server.connect(transport);                        // 第二次 connect 静默覆盖 _transport（1.25.x）
  await transport.handleRequest(req, res, req.body);
});
```

`review_diff` 的最终结果现在都对了：A 的请求到达时 `this._transport` 还是 A 的 transport，捕获的引用正确。但 A 的 handler 还在执行，B 的请求触发了第二次 `connect()`，共享的 `this._transport` 被改指向 B 的 transport。之后 A 的 handler 发出的消息有两种结局：

- **id 撞上（B 的 transport 上正好有在途的 `id: 3`）**：A 的 progress（带着 A 的文件名）和那条「是否把这个文件发给外部 linter？」的 elicitation，被**静默**发进了 B 的流。没有任何报错，两边的日志都是「成功」。B 那边的用户看到一个关于陌生文件的确认框；如果他点了同意，这个回答会怎样被处理，advisory 没有说明，我们也不推演，但「另一个租户的用户替 A 做了数据外发的决定」这个可能性已经足够让这一版不能上线。
- **id 没撞上**：transport 抛错，A 的 progress 发送失败。这在低并发测试里表现为偶发报错，最常见的处理是给 `sendNotification` 包一层 try/catch，这样就把唯一的信号也吞掉了。

advisory 对这个形态的结论是只受 Issue 2 影响；工具执行中不发 progress / sampling / elicitation 时是安全的。`review_diff` 恰好两样都发。

修复方向：团队的下一步是「上 session，让每个租户隔离」，见 v3。

### 4.3 BAD v3：上了 `sessionIdGenerator`，server 还是共享的

v3 相对 v2 只改了一处：transport 从「每请求」改成「每会话」，按 `mcp-session-id` 查表复用；server 仍是全局一个。

```ts
// 示意：v3 —— 相对 v2：transport 改为每会话一个（有状态模式）；server 仍共享
const server = buildReviewServer();
const sessions = new Map<string, StreamableHTTPServerTransport>();

app.post('/mcp', async (req, res) => {
  const sid = req.headers['mcp-session-id'] as string | undefined;
  let transport = sid ? sessions.get(sid) : undefined;
  if (!transport) {
    transport = new StreamableHTTPServerTransport({ sessionIdGenerator: () => randomUUID() });
    await server.connect(transport);                      // 新会话的 initialize：覆盖 _transport
    // ...初始化完成后 sessions.set(transport.sessionId, transport)
  }
  await transport.handleRequest(req, res, req.body);
});
```

Issue 1 没了：每个会话有自己的 transport 和映射表。但 v2 的第 ② 类还在，而且多出两类：

- **① 最终响应错投（不需要 id 碰撞）**：`sess_B-04` 连上之后，`sess_A-17` 在自己的会话 transport 上又发了一个 `tools/call`（`id: 4`）。这个请求是在覆盖**之后**才到达 A 的 transport 的，处理时捕获的 `this._transport` 已经指向 B，响应被路由到 B 的 transport。`sess_A-17` 看到的只是一次超时，重试之后如果恰好没有新会话插进来，又好了。值班的人会去调超时，或者怀疑网络。
- **② handler 内消息（需要 id 碰撞）**：同 v2。`sessionIdGenerator` 对这一类没有任何作用。
- **③ 主动通知（无条件）**：server 在 handler 之外主动发出的通知（例如我们在示意里假设的「审查规则已更新」这类推送），总是发给最后连接的会话。`sess_A-17` 从此收不到，`sess_B-04` 收到两份；下一个新会话连上后，又全部转给它。

v3 的教训是 §3.2 那一条：「有 session id」不等于「有每会话的 server 实例」，而这个服务三类消息都用了。

修复方向：server 也按会话新建，再加上 1.26.0 的守卫和生命周期收口，见 GOOD。

### 4.4 GOOD：每会话一套 server + transport，守卫兜底，生命周期收口

```ts
// 示意：svc_review-bot GOOD —— 相对 v3：server 移进「新会话」分支（§3.1）；升级到 >=1.26.0（§3.3）
const sessions = new Map<string, { server: McpServer; transport: StreamableHTTPServerTransport }>();

app.post('/mcp', async (req, res, next) => {
  try {
    const sid = req.headers['mcp-session-id'] as string | undefined;
    let entry = sid ? sessions.get(sid) : undefined;
    if (!entry) {
      const server = buildReviewServer();                 // 工厂：每会话一个实例，工具定义是共享常量
      const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: () => randomUUID() });
      // onclose 里只做登记清理；不要在这里再调 server.close()：此时 _transport 尚未清空，
      // server.close() 会再关同一个 transport、再触发 onclose，重入直到栈溢出。
      // transport 关闭后 SDK 的 _onclose() 会 abort 在途 handler 并清空 _transport（§3.4）；主动结束会话从外部调 server.close()
      transport.onclose = () => { sessions.delete(transport.sessionId!); };
      await server.connect(transport);                    // 若误把已连接的实例传进来：1.26.0 起直接抛错
      entry = { server, transport };
      // ...初始化完成后 sessions.set(transport.sessionId!, entry)
    }
    await entry.transport.handleRequest(req, res, req.body);
  } catch (err) {
    next(err);                                            // 守卫抛出的错误必须落到错误处理里，不能让进程退出（§3.3）
  }
});

// review_diff 的 handler：发消息前 SDK 会检查 abort signal（advisory Patches 第 3 项）；
// 副作用前我们自己再查一次（本文主张，§3.4）
async function reviewDiff(args, extra) {
  const ok = await extra.sendRequest(elicitLinterConsent(args.file), ElicitResultSchema);
  if (extra.signal.aborted) return cancelledResult();     // 连接已关：不把文件发出去
  if (ok.action === 'accept') await sendToLinter(args.file);
  // ...
}
```

用同一个时序再走一遍：

- A 和 B 各有自己的 server 和 transport。A 的 `id: 3` 和 B 的 `id: 3` 落在两张不同的映射表、两个不同的 `_transport` 上，碰撞不再有意义；A 的 elicitation 只会出现在 `sess_A-17`；A 在 B 连上之后发的 `id: 4` 正常返回；主动通知按会话发送。
- 如果有人把 v1–v3 的任何一种共享写法改回来，1.26.0 的守卫会在第一个重叠请求、或第二个会话的 `initialize` 上直接抛错，错误经 `next(err)` 落到错误处理，变成一个可观测的失败，而不是静默串流或进程退出。
- `sess_A-17` 中途断开时，`onclose` 只把它从 `sessions` 里删掉；transport 关闭后 SDK 的 `_onclose()` 清空 `_transport`、abort 在途 handler，`review_diff` 的 abort signal 被触发，后续的 progress 不再发送，`sendToLinter` 之前的检查让外发不会发生。

v1 → GOOD 的每处改动回扣 §3：

| 版本 | 改动 | Issue 1：响应串流 | ① 最终响应 | ② progress / elicitation | ③ 主动通知 | 对应 §3 |
| --- | --- | --- | --- | --- | --- | --- |
| v1 | 一个 server + 一个无状态 transport | **id 相同即串**（所有请求类型） | — | — | — | 基线 |
| v1 → v2 | transport 每请求新建 | 消除 | advisory 对此形态只列出 handler 内消息的风险 | **碰撞时静默串，否则抛错** | — | §3.1（只做了一半） |
| v2 → v3 | transport 每会话（`sessionIdGenerator`） | 消除 | **覆盖后到达的请求错投，发起方超时** | **同 v2** | **总发给最后连接者** | §3.2（session ≠ 实例隔离） |
| v3 → GOOD | server 每会话新建（工厂）；升级 ≥1.26.0；入口错误处理；close 取消在途 handler；副作用前查 signal | 消除 | 消除 | 消除 | 消除 | §3.1 + §3.3 + §3.4 |
| GOOD 的验证 | 重叠请求 + 碰撞 id 的测试 | 见 §5 | 见 §5 | 见 §5 | 见 §5 | §3.5 |

一句话回顾这条线：v1 共享了 transport，v2 共享了 server，v3 以为 session 就是隔离；GOOD 让连接对象只属于一个连接，并让任何回退都在第一个重叠请求上报错。

---

## 5. 发版前清单：对准可注入的失败点 (Pre-Ship Checklist)

不要靠「两个客户端顺序各调一次都对」判断。下面六个注入点都在你**自己的**测试环境里，用两个（或更多）测试客户端对自己的服务跑；每一项都要求请求在时间上重叠，并让两边使用 SDK 默认、从 0 开始的 id。

**注入 1：两个客户端的请求重叠到达同一个无状态入口，id 相同（对应 §3.1 / §3.3，Issue 1）**

- [ ] 每个客户端只收到自己的响应；响应内容可以按客户端区分（测试工具回显调用方标识）
- [ ] 若代码意外复用了无状态 transport：第二个请求被拒（1.26.0 起 `handleRequest()` 抛错；主线 PR #2918 下 Node transport 回 `500`），而不是被写进另一个客户端的流
- [ ] 拒绝落到入口的错误处理，进程不退出

**注入 2：第二个会话在第一个会话的 handler 执行中完成 `initialize`（对应 §3.1 / §3.3，Issue 2）**

- [ ] GOOD：两个会话各自的 server 实例互不影响
- [ ] 回退检测：把 server 改回模块级共享后，第二次 `connect()` 直接失败（主线 PR #2918：`SdkErrorCode.AlreadyConnected`）；CI 里这条用例必须是红的

**注入 3：第一个会话的工具在执行中发 progress 和 elicitation，同时第二个会话上有一个同 id 的在途请求；再跑一遍不同 id 的版本（对应 §3.2 第 ② 类）**

- [ ] 两种 id 分布下，progress 和 elicitation 都只出现在发起请求的那个会话里
- [ ] 断言「第二个会话没有收到任何不属于它的消息」，而不只是「第一个会话收到了」
- [ ] 对旧版本做回归对照时，能分别复现「碰撞 → 静默错发」与「不碰撞 → 抛错」，证明测试确实能区分这两种结局

**注入 4：第二个会话连上之后，第一个会话发一个新的普通 `tools/call`（对应 §3.2 第 ① 类）**

- [ ] 第一个会话在正常时延内收到自己的响应，不超时
- [ ] 第二个会话的 transport 上没有出现这个响应
- [ ] 监控里，按会话统计的工具超时率不随新会话连接而上升

**注入 5：在 handler 之外触发一次 server 主动通知，且此时有三个会话在线（对应 §3.2 第 ③ 类）**

- [ ] 通知只发到它应该去的会话（按你的业务规则），而不是最后连接的那一个
- [ ] 第三个会话连上前后，前两个会话收到通知的行为不变

**注入 6：handler 执行中 `close()` 该会话的 transport，handler 随后尝试发 progress 并执行一个外发副作用（对应 §3.4）**

- [ ] close 之后没有任何消息从这个 handler 发出，也没有消息出现在之后新建的连接上
- [ ] 外发副作用没有执行（handler 在副作用前检查了 `signal.aborted`）；调用方侧把这次调用记为结果未知，而不是「没做」

**发版评审口头否决**

- [ ] 「构造 server 太贵，全局建一个复用」（要复用的是工具定义，不是连接对象）
- [ ] 「我们用了 `sessionIdGenerator`，已经按会话隔离了」，但 server 仍是共享的
- [ ] 「payload 里带了租户 id / 已经过了鉴权，不会串」（错路由发生在鉴权之后的对象引用上）
- [ ] 升级到 1.26.0 后出现 `connect()` 报错，处理方式是降级、吞错或加重试
- [ ] 给 `sendNotification` / `sendRequest` 包 try/catch 后静默忽略失败
- [ ] 入口没有错误处理，fail-fast 的 rejection 能把进程带走
- [ ] 隔离测试只有顺序请求，或两个测试客户端的 id 刻意错开
- [ ] 把多客户端下的偶发超时归因为网络，未先排查实例共享
- [ ] 在 `transport.onclose` 回调里再调 `server.close()`（`_transport` 尚未清空，会重入同一个 transport 的 close，直到栈溢出）

---

## 6. 小结 (Takeaways)

**看到「只在多客户端时偶发超时」「progress 偶发报错」「通知只有最新会话收得到」，先别调超时、别加重试。问三件事：server 对象是不是每个连接一个；无状态 transport 是不是每个请求一个；三类消息（最终响应、handler 内消息、主动通知）各自走的是哪个引用。**

- 根因：违反「一个 server 对象 = 一个连接，一个无状态 transport = 一个请求」。共享 transport 时，id 相同就会让所有请求类型的响应串流；共享 server 时，最终响应在覆盖之后到达会错投、发起方超时，handler 内的 progress / sampling / elicitation 只在 id 碰撞时静默串流、否则抛错，主动通知总发给最后连接者（§1–§2）。
- 修法：每请求（无状态）或每会话（有状态）新建 server + transport，复用的是工具定义；按消息类别判断影响面；升级到 1.26.0 让复用 fail-fast，入口兜住这个错误；close 时取消在途 handler，副作用前查 signal；用重叠请求和碰撞的 id 做测试（§3）。
- `svc_review-bot` 从 v1 → v2 → v3 → GOOD，每次只改一处，分别回扣 §3.1 / §3.2 / §3.1 + §3.3 + §3.4，验证靠 §3.5（§4）；发版靠六个注入点把关（§5）。
- 证据边界：只讲 TypeScript SDK，不推断其他语言 SDK；这是实现层的实例复用，不是协议漏洞；`AlreadyConnected` / `ALREADY_CONNECTED` / `500` / `-32603` 只出自主线 PR #2918，1.x 的报错文案未核；abort 清理只出自 advisory Patches 节；§4 的 elicitation 场景是设计示例，advisory 没有给出真实受害案例；「副作用前自查 signal」是本文主张。

系列位置：**MCP Server Runtime Boundaries** 专题 #1，管 MCP Server 的**连接实例**边界。它和已发的 [MCP Auth](posts/mcp_auth_identity_not_intent.md)、[MCP Consent Binding](posts/mcp_consent_binding_confused_deputy.md) 分工明确：那两篇守的是 token 和授权流程，本篇守的是授权通过之后，一条消息有没有被写进正确的连接。同样是「按 id 键的映射被碰撞」，流式组装层的版本见 [流式 tool call 的身份键坍缩](posts/streaming_tool_call_index_collision.md)；第 ① 类超时之后的重试是否安全，见 [Agent 写操作的幂等](posts/agent_write_idempotency.md)。

---

## 参考 (References)

1. GitHub Advisory Database — [GHSA-345p-7cg4-v4c7 / CVE-2026-25536：@modelcontextprotocol/sdk has cross-client data leak via shared server/transport instance reuse](https://github.com/advisories/GHSA-345p-7cg4-v4c7)（reviewed，severity high，CVSS 3.1 = 7.1；发布 2026-02-04 UTC；影响 `@modelcontextprotocol/sdk` >= 1.10.0, <= 1.25.3，1.26.0 修复；机制以 Impact 节为准，守卫以 Patches 节为准）。仓库侧同一 advisory：[typescript-sdk security advisory](https://github.com/modelcontextprotocol/typescript-sdk/security/advisories/GHSA-345p-7cg4-v4c7)。
2. modelcontextprotocol/typescript-sdk — [Release v1.26.0](https://github.com/modelcontextprotocol/typescript-sdk/releases/tag/v1.26.0)（2026-02-04 UTC；release notes 只写 “Addresses … GHSA-345p-7cg4-v4c7”，未单列修复 PR 与守卫细节）。
3. modelcontextprotocol/typescript-sdk — [PR #2918：fix(server): refuse a second connect and stateless transport reuse](https://github.com/modelcontextprotocol/typescript-sdk/pull/2918)（merged 2026-10-02 UTC 至 `main`；主线 `packages/server`；`SdkErrorCode.AlreadyConnected`、Node transport `500`、`createMcpHandler` `500`/`-32603` 均出自此 PR；README 示例改为每请求一套；PR 自述 1.x 自 1.26.0 起已有前两项检查）。
4. modelcontextprotocol/typescript-sdk — [Issue #204：Multiple clients to the same SSE connection?](https://github.com/modelcontextprotocol/typescript-sdk/issues/204)（closed completed，2025-12-05 UTC；提问类 issue，单 server 多 SSE transport 的写法；advisory 引用）。
5. modelcontextprotocol/typescript-sdk — [Issue #243：How to use MCP client in a multi-user application?](https://github.com/modelcontextprotocol/typescript-sdk/issues/243)（closed completed，2025-12-05 UTC；提问类 issue，问的是多用户 Web 应用里客户端 / transport 如何复用；advisory 引用，本文只作「多用户场景常见疑问」的旁证）。
6. 本站 — [MCP Auth：Identity ≠ Audience——OAuth 绿了，token 没绑到这台 MCP](posts/mcp_auth_identity_not_intent.md)（认证层，划界）。
7. 本站 — [MCP Consent Binding：Consent 绿了，IdP callback 没绑到同意过的浏览器（Confused Deputy）](posts/mcp_consent_binding_confused_deputy.md)（授权流程层，划界）。
8. 本站 — [流式 tool call 的身份键坍缩：并行调用被拼成一个坏 call，在进历史之前就已经坏了](posts/streaming_tool_call_index_collision.md)（同为 id / index 映射碰撞，层不同，互链）。
9. 本站 — [Agent 写操作的幂等：超时之后凭什么敢重试](posts/agent_write_idempotency.md)（第 ① 类超时后的重试，只引用不复述）。
