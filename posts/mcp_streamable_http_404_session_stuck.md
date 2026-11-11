---
title: 服务端重启后一直 404：Streamable HTTP 会话失效，重试却还带着旧 session id
date: 2026-11-09
tags: Agent, MCP, Streamable-HTTP, Session, Runtime
description: 有状态 MCP 服务端重启后，客户端反复携带失效 session id，每次调用都 404。带会话请求的 404 要触发无 session id 的重新初始化，但不授权无条件重放工具调用。拆开错误分类、并发恢复与状态丢失，按安全性有界重放。Agent Runtime Failure Handling 系列第 5 篇。
---

## 1. 问题现象 (Problem Symptoms)

**带 `MCP-Session-Id` 的请求收到 HTTP 404，先恢复会话，不要原样重试旧请求。重新初始化成功，也不等于可以重放任意工具调用。** 前一件事是 MCP 规范的要求，后一件事需要业务安全性证明；把它们合成一个“自动重试”，既会让长跑 Agent 一直 404，也可能在恢复后重复执行写操作。

这是 **Agent Runtime Failure Handling 系列第 5 篇**。上一篇 [list_changed 重入](posts/mcp_list_changed_reload_blocks_receive_loop.md) 是会话还活着、receive 回调阻塞结果投递；本篇是服务端不再承认旧会话，客户端却把这个终态当普通错误继续使用。与 [分层重试](posts/layered_retry_amplification.md) 只交叉一句：重试次数有界还不够，重试所用的会话也必须有效。

### 现象 A：第一轮成功，服务端重启后每一轮都 404

TypeScript SDK [报告 #3056](https://github.com/modelcontextprotocol/typescript-sdk/issues/3056) 描述了一个长跑 harness 连接有状态 Rancher MCP 的场景：服务端夜间因证书轮转重启，旧会话丢失；客户端此后每次 `tools/call` 都携带原来的 `Mcp-Session-Id`，持续收到 “session not found”。报告称关闭并重新连接 transport，或重启进程，才能恢复。

证据绑定到报告明确检查的 **`@modelcontextprotocol/client` 2.0.0**：作者检查发布包 `dist/index.mjs`，称 `_sessionId` 仅在初始化成功时写入；POST 错误分支特殊处理 401，而 404 直接抛错，没有清 id、重握手的路径。这里转述的是报告与指定版本，**不是本文独立复现，更不是对当前源码的断言**。

看起来合理的补丁是加退避：第一次 404 等一会，再发一次。服务端确实能响应 HTTP，只是不认识这个会话；只要每次仍发旧 id，等多久都没有补上缺失的初始化。

### 现象 B：同是会话丢失，却与普通 Invalid Request 混成一类

Python SDK [报告 #3799](https://github.com/modelcontextprotocol/python-sdk/issues/3799) 给了更隐蔽的失败：HTTP 上同样是“带 session id 的请求收到 404”，到了调用方却只剩普通 `MCPError`，错误码还取决于响应体。

| 报告中的响应 | 调用方看到的错误 | 误判风险 |
| --- | --- | --- |
| HTTP 404，空 body | `MCPError(-32600, "Session terminated")` | 当成普通 Invalid Request |
| HTTP 404，Python SDK server 风格 body | `MCPError(-32600, "Session not found")` | 同上，只是文案变了 |
| HTTP 404，TS SDK server 风格 body | `MCPError(-32001, "Session not found")` | 依赖实现定义的错误码 |
| HTTP 200，普通 JSON-RPC invalid request | `MCPError(-32600, "Invalid request")` | 真正不该靠换会话解决的输入错误 |

这组输出来自报告中的 **`mcp==2.3.0`**，以及作者测试的开发提交 **`d7845c0` / `2.3.1.dev17+d7845c07`**；不是本文运行输出。不能只匹配 `-32600`，也不能只匹配 “Session terminated”：前者会混进普通无效请求，后者会漏掉另两种 body。

该报告引用的 Temporal MCP 集成提交 [`88745dc`](https://github.com/temporalio/ai-integrations/blob/88745dc256c708950c858c6a731051b7bafd5fd5/python/mcp/src/temporalio/mcp/_activities.py#L48-L59) 把 `INVALID_REQUEST` 放在不可重试协议错误集合里。本文读取了这个固定提交，确认有该映射；不把结论扩展到所有 Temporal 版本或其他编排器。错误分类如果丢掉 HTTP/session 上下文，本可恢复的会话故障就可能被编排层立即判死。

### 现象 C：重握手修好了，却把“会话恢复”误当“原业务恢复”

下面是设计反例，不是上述工单中的实测事故：Host 在任何 404 后都新建会话并重放上一次调用。`list_clusters` 看起来恢复了；换成一次结果未知的变更操作，或依赖旧会话中的临时对象，重放却可能重复变更、找不到句柄，甚至在错误的上下文里执行。

**恢复连接、恢复会话状态、决定是否重放，是三个不同决策。** 本文后面的 GOOD 把它们分开，不把报告作者建议的“重放一次”当成规范原文。

证据状态截至本次写稿读取：#3056 与 #3799 均 open；open 只描述工单状态，不证明最新代码仍然缺陷相同。`SessionNotFoundError` 在 #3799 中是**提案**，本文不会将它写成已发布 SDK 接口。

## 2. 根因分析 (Root Cause Analysis)

三个保证被错误合并成了“重连就好”：

| 层 | 要回答的问题 | 本篇的错误合并 |
| --- | --- | --- |
| HTTP / 会话生命周期 | 服务端是否仍承认发送时的 session id？ | 把会话终态当普通失败，继续复用旧 id |
| 协议错误分类 | 是带会话请求的 404，还是普通 Invalid Request？ | 只保留 JSON-RPC code/message，丢掉恢复依据 |
| 业务执行 | 原操作能否跨会话再执行，旧状态是否还有效？ | 把重新初始化的 MUST 扩成无条件重放工具 |

[MCP 2025-11-25 Session Management](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports#session-management) 明确两条相连的规则：服务端可以随时终止会话，此后必须对携带该 id 的请求返回 404；客户端收到**带 `MCP-Session-Id` 的请求对应的 HTTP 404** 时，必须发送不附带 session id 的新 `InitializeRequest` 来开始新会话。

这里的判定输入是 **HTTP status + 该次请求实际发送的 session id**，不是响应 body 的一句英语。没有 session id 的普通 404 不满足这个会话丢失判据；代理路由配置错误也不会因为重握手就自动变好。对明确的带会话 404，先按规范尝试新初始化；新初始化自身失败则有界退出，不能无限重连。

并发会再放大这个坑。A、B 都带旧会话出去，A 先收到 404 并建立新会话，B 的旧 404 随后才到。如果 B 无条件清掉“当前 session id”，它清掉的是刚恢复的会话。只拿一把锁还不够；必须知道这次错误属于哪一代连接，拒绝让旧代响应污染新代状态。

## 3. 机制要点 (Mechanism / Solutions)

### 3.1 在传输边界保留会话丢失的证据

Host 若能控制传输适配层，应在把错误变成普通 `MCPError` 前，记录本次请求的 HTTP status、是否携带会话、连接代数及安全处理后的 endpoint 标识。`status == 404` 且该请求带过 id，才形成本文的 `SessionLost` 信号。这里的 `SessionLost` 是 **Host 自定义示意类型**，不是现有 SDK 接口；#3799 的专用异常类型仍是提案。

向上保留原 JSON-RPC code/message，供诊断与兼容旧处理器；向恢复管理器额外提供类型化上下文。若现有 SDK 已丢掉状态码和请求头信息，就不能靠模糊匹配文案来宣称可靠分类，应改适配层或选择能保留该上下文的实现。

不要把原始 session id 写进普通日志或指标标签。诊断可用本地递增代数与脱敏标识，不需要泄露完整会话凭据。

### 3.2 同一逻辑连接只允许一个恢复者，旧代错误不能清新代

管理范围不是整个进程共用一个“连接”：至少按 endpoint、身份与业务隔离范围划分。每次调用拿到一个不可变 lease，其中带连接对象与本地 epoch；响应、失败都归属这个 lease，不能读一个可随时变化的全局 id 来推断发送时状态。

状态迁移是 `READY(e) → RECOVERING(e) → READY(e+1)`，或恢复失败进入 `FAILED`。同代的并发 404 共享一个恢复任务，不各自 initialize；新调用在恢复完成前等待，不再借出已失效会话。旧代迟到的错误可以加入已有恢复或观察到新代已可用，**不能再次清除新代**。旧代迟到的成功结果也不能无条件当作新代目录或临时对象状态发布。**成功结果同样携带来源信息**：由 Host 的发送 lease 填写 `(scope, source_epoch)`，不能相信 payload 自报的 epoch。普通只读值若经业务确认与会话无关，策略可接收为带来源代数的历史观测；不得将其改标为新代状态。目录、临时句柄、订阅等会话绑定结果，必须在 manager 的原子校验/发布点确认 `READY`、隔离范围相同、`source_epoch == current_epoch`，否则抛出 `StaleSessionResult`，不进入业务历史中的可用句柄区。结果类别由受信业务合同决定，默认按会话绑定处理，不由工具响应自行宣称。

校验不是“一次通过永久有效”。即使句柄返回时同代，后续使用也必须携带原 `(scope, source_epoch)` 重新借出匹配的 lease；已经切代就拒绝，不把句柄改绑到新连接。接收普通只读值只允许作为观测值消费，不授权该值更新当前目录或连接状态。

恢复任务负责：停用旧连接，清除旧 id 的使用路径，以不带旧 id 的请求重新 initialize，完成初始化通知与必要的版本/能力协商，再发布新连接。协议版本、capabilities 和工具目录要重新验证；不是把旧 transport 的 id 改为空就继续随便发业务请求。#3056 还提到 v2 era 协商设计分歧；本文不替维护者决定具体 SDK 内部实现，而要求使用该版本支持的完整连接流程。

### 3.3 重新初始化必须做，重放必须另外证明安全

恢复后分别判断：

- **无副作用、跨会话可重新计算的只读查询：** 重新验证工具与参数后，可在业务期限内自动重放一次；新的 JSON-RPC request id 对应同一个逻辑业务操作。
- **写操作：** 不能从一个会话丢失错误推导出跨所有尝试的副作用历史。若之前已有断连、超时或上层重试，结果可能未知。只有业务实现提供跨会话仍有效的幂等键、持久去重与结果查询，且本次策略允许时，才考虑重放；否则返回“需核对业务结果”，而不是静默再写。详见 [工具写操作的幂等](posts/agent_write_idempotency.md)。
- **依赖旧会话状态的调用：** 临时句柄、订阅、工作目录、交互流程和审批上下文不得默认迁移。先执行显式的状态重建与重新验证；做不到就停止该业务链。单有 `readOnlyHint` 之类声明不能替代对实现语义的确认。

一个符合规范且确实在执行前拒绝旧 id 的 404，可以表明**这次被拒绝的请求**未进入工具执行；它仍不证明更早的尝试没有产生副作用，也不证明这个工具在新会话仍具有相同前置条件。不能把这个局部保证扩成整个业务操作的 exactly-once。

业务期限也必须与次数一起落实：入口创建一个基于事件循环单调时钟的绝对 `deadline`，首次调用、借连接、恢复等待、策略判断和重放都沿用它，不为每一步重置预算。整个业务控制流由 `asyncio.timeout_at(deadline)` 包围，两次 `invoke` 也显式传入同一绝对期限；适配器把剩余时间传到 HTTP 读写，并响应取消。结果返回后再次检查期限，超期结果不得被当作及时成功接收。若底层忽略取消，Python 超时无法强制抢占，必须隔离/终止该传输任务并管理清理；示意不承诺对任意不合作实现硬实时返回。

调用阶段超时保留“结果未知”，不冒充 `SessionLost`，也不自动重放；等待共享恢复超时只结束本次等待，共享任务仍受 manager 自己的期限和关闭策略管理。调用方取消同样必须传播，不能误判成会话丢失。

将恢复尝试预算与工具重放预算分开：本例每次调用最多加入一次恢复、最多重放一次，外层不能再套无限 retry。若新会话上的那次重放又 404，仍要使该会话失效并启动规范要求的新初始化，但**不再重放该业务调用**；交还明确失败。管理器对连续初始化失败和无进展的失效链设期限与熔断，不无限自旋。

### 3.4 恢复任务与关闭也必须有主人

等待者取消只取消自己的等待，不把共享恢复一起取消；恢复任务由连接管理器持有、统一设期限、收取异常。关闭时先在连接管理器作用域置 `closing`，禁止新 lease 与新恢复，再唤醒等待者、取消并等待全部所属任务，关闭尚未发布的新连接与旧 transport。检查 `closing` 必须发生在建连接之前和发布之前；关机期间握手即使成功也不能把新连接重新放回池里。

这不是要把本篇写成任务调度教程，而是防止“同代共享恢复”修好惊群后，又留下后台异常无人收、某个取消的 turn 杀掉全部恢复、shutdown 之后重新开连接的缺口。

## 4. 同一条运维业务链 `OPS-MCP-771`：错法 → 改法 → 崩溃点

`OPS-MCP-771` 是设计示例：长跑运维 Agent 连接有状态 Rancher MCP，定期做只读集群查询 `list_clusters`；工具名和业务 ID 都是示意，不宣称为报告中的真实接口。业务链从取目录到查询结果入 Agent 历史保持不变，服务端重启是固定注入点。后半段把同一业务链中的动作换成“依赖旧会话句柄的变更”，用来验证不会因为查询能恢复就放开所有重放。

### 4.1 BAD v1：只退避，不换会话

```python
# 示意：同一连接已初始化，transport 缓存着旧 session id。
for attempt in range(3):
    try:
        return await cached_session.call_tool("list_clusters", {})
    except TransportError:
        await backoff(attempt)
        # 重启后继续用 cached_session → 仍然发送旧 id → 再次 404
raise QueryFailed("OPS-MCP-771")
```

次数虽然有界，修复对象却不对。对应 §3.1：必须在传输边界识别“本次带会话请求的 404”；对应 §3.2：让该 lease 失效，禁止连接池把它继续借出去。增加尝试次数不能替代这两步。

### 4.2 BAD v2：按 `-32600` 判死；或对任何错误都重连重放

```python
# 示意：不是 Temporal API 源码。
except MCPError as err:
    if err.code == -32600:
        raise NonRetryableError()  # 会话丢失也落到这里
    return await reconnect_and_replay(last_call)  # 写操作也一律再发
```

第一条分支把可恢复会话与非法输入合并，第二条分支又把所有其他失败都当成可安全重放。两条都省掉了必要上下文。对应 §3.1 保留传输证据、§3.3 另做业务重放判断；不能只把 `-32600` 从黑名单挪到白名单。

### 4.3 GOOD：恢复管理器管会话，业务策略管重放

下面是 **Host 层接口与控制流示意**，不是可直接复制的 SDK 补丁。`SessionLost`、`manager`、`policy` 及业务异常均由 Host 定义；没有声称 SDK 已提供 `SessionNotFoundError`。先把管理器的原子状态合同写清，避免用一个不明含义的 `reconnect()` 隐藏并发问题。

```text
示意：每个隔离范围一份 ConnectionManager
状态：closing；current(epoch, connection)；recovery(epoch, owned_task)

borrow：
  在同一状态锁内检查 closing。
  READY 才能借出不可变 lease；RECOVERING 则等待所属任务后重新检查；
  FAILED 则抛有原因的恢复失败。失效连接绝不再次借出。
  borrow(deadline) 不重置总期限；等待共享恢复时不取得其取消所有权。

lease.invoke(operation, deadline)：
  发送前检查剩余时间，HTTP 读写继承该绝对期限；响应取消并有界清理。
  发送 lease 的 scope/epoch 保持不可变，不从当前全局连接补写来源。

accept_reply(reply, operation, policy, deadline)：
  在同一原子状态校验/发布点检查期限、closing 与 reply.scope；
  来源 epoch 由 Host lease 写入，类别由受信 operation 合同决定。
  普通、无会话绑定的只读观测：业务允许且期限内时可接受旧代值，
    保留 source_epoch；不写当前目录，不把它冒充新代状态。
  目录/句柄/订阅等会话绑定值（默认类别）：
    只有 READY 且 source_epoch == current_epoch 才可发布；
    RECOVERING/FAILED/切代 → StaleSessionResult，不更新当前状态。
  返回仍带 scope/epoch 的结果；后续使用句柄时重新验证同代 lease。
  原子区内不 await，也不调用阻塞业务代码；策略须是有界纯判断。

mark_lost_and_start_recovery(failed_epoch)：
  在同一状态锁内完成（不在锁内 await 网络）：
    closing → 拒绝，不创建任何任务。
    failed_epoch < 当前已发布 epoch → 返回已完成的恢复结果；不清新会话。
    该 epoch 已有 recovery → 返回同一 owned_task。
    否则：移走 current、立即标 RECOVERING；登记唯一 owned_task。
  任务由管理器持有；完成回调收取异常，不让它丢在后台。

owned_task（有总期限）：
  停用旧 transport；创建不携带旧 id 的新连接；
  按所用 SDK 的完整流程 initialize + initialized，重新协商能力；
  重新获取工具目录，验证业务前置条件；不假装旧会话状态仍存在。
  发布时在锁内再次检查 closing 与恢复代数；
    closing / 已过期 → 关闭未发布连接，不再入池；
    成功 → 原子发布 READY(epoch+1)，唤醒等待者。
  失败 → 关闭候选连接，记录 FAILED 与原因，唤醒等待者。
  无论失败或取消，资源都有 finally 清理者；不遗留半初始化连接。

shutdown：
  先在整个 manager 置 closing（不是仅给已有 connection 打标）；
  拒绝新 borrow / 新 recovery，唤醒等待者报 Closing；
  再取消、await 全部所属任务并收取异常；关闭全部所属连接。
```

`failed_epoch` 是本地连接代数，不是 MCP 协议字段。仅靠比较服务端返回的 session id 不够：初始化结果可以不分配 id，连接生命周期仍然存在。示意要求调用 lease 记录“本次请求是否带 id”，只有已确认的会话丢失才能进入下面的 `SessionLost` 分支。

```python
# 示意：Python 3.11+；Host 自定义类型/manager 合同如上，非 SDK API。
from dataclasses import dataclass
import asyncio

@dataclass(frozen=True)
class ReplyEnvelope:
    scope: str
    source_epoch: int
    payload: object

def require_time(deadline):
    if asyncio.get_running_loop().time() >= deadline:
        raise OperationDeadlineExceeded()  # 尚未派发，不谎称已执行

async def invoke_checked(manager, lease, operation, policy, deadline):
    require_time(deadline)  # 期限已耗尽则不再派发首次调用/重放
    payload = await lease.invoke(operation, deadline=deadline)
    # 即使底层吞取消并晚返回，也不把超期 payload 当作成功接收。
    if asyncio.get_running_loop().time() >= deadline:
        raise TimeoutError("late tool result")
    reply = ReplyEnvelope(lease.scope, lease.epoch, payload)
    # 两次调用都经过这个门；不能对首次调用直接 return 原始 payload。
    return manager.accept_reply(reply, operation, policy, deadline=deadline)

async def run_operation(manager, operation, policy, deadline):
    phase = "borrow"
    try:
        # deadline = loop.time() + 总预算；全程只创建这一个超时作用域。
        async with asyncio.timeout_at(deadline):
            lease = await manager.borrow(deadline=deadline)
            phase = "invoke"
            try:
                return await invoke_checked(
                    manager, lease, operation, policy, deadline
                )
            except SessionLost:
                # 仅 HTTP 404 + 该次请求带 session id；不是 TimeoutError。
                recovery = manager.mark_lost_and_start_recovery(lease.epoch)

            phase = "recovery_wait"
            # 共享恢复有 manager 自己的期限；本次超时/取消不杀它。
            await asyncio.shield(recovery)
            fresh = await manager.borrow(deadline=deadline)
            require_time(deadline)
            decision = policy.evaluate(operation, fresh)  # 有界、无 I/O
            if not decision.safe_across_sessions:
                raise BusinessRecoveryRequired(operation.business_id)

            phase = "invoke"
            try:
                # 新 request id；逻辑业务 id / 幂等键不变；仍用原 deadline。
                return await invoke_checked(
                    manager, fresh, operation.with_new_request_id(),
                    policy, deadline
                )
            except SessionLost:
                manager.mark_lost_and_start_recovery(fresh.epoch)
                raise ReplayBudgetExhausted(operation.business_id)
    except TimeoutError as err:
        if phase == "invoke":
            # 首次调用和重放超时均无可靠业务结果；不进入恢复/重放分支。
            raise OperationOutcomeUnknown(operation.business_id) from err
        raise OperationDeadlineExceeded(operation.business_id) from err
    # 调用方 CancelledError 不捕获、不转译，照常传播。
```

调用方取消、普通 Invalid Request、无会话请求的 404、网络超时都不会被这个 `except SessionLost` 冒充为会话丢失；它们保留各自处理路径。上层 durable worker 应消费这些明确结果，而不是在外层把 `ReplayBudgetExhausted` 再包成一个无限重试循环。同一个绝对期限耗尽则本次操作退出，不替共享恢复任务取消所有其他等待者；`borrow` 的内部等待也必须遵守这一所有权合同。

例如 A 正在旧代创建临时句柄，B 先收到 404 并恢复到新代，A 随后才返回成功。`invoke_checked` 会把 A 的结果封成旧 epoch 的 `ReplyEnvelope`；`accept_reply` 拒绝这个会话绑定结果，不把它交给模型当作新代可用句柄。若 A 返回的是已证明无会话绑定的普通只读查询值，则可按业务策略保留为旧代观测，来源代数不变；这不是允许旧目录覆盖新目录。

这一版恢复的不是所有旧状态：`list_clusters` 经过业务确认是无副作用、可跨会话重新计算的查询，因而可以重放一次。若同一业务链接下来要用旧会话中的临时句柄执行变更，策略返回 `BusinessRecoveryRequired`；即便网络已恢复，也不能继续沿用旧句柄或旧审批上下文。

| 改动 | 避免的失败 | 回扣机制 |
| --- | --- | --- |
| 用 status + 发送时会话上下文形成类型化信号 | 三种 body、两种 code 导致恢复分类漂移 | §3.1 |
| lease 固定 epoch，同代共享恢复，借出前检查状态 | 并发初始化惊群、旧 404 清掉新会话 | §3.2 |
| 全新无旧 id 初始化，再协商与验证目录 | 旧 id 重试不止、能力与状态被假定继承 | §3.2–§3.3 |
| 只读查询可重放一次，写操作另证幂等，状态丢失则停止 | 无条件重复写、旧句柄在新会话误用 | §3.3 |
| 总绝对期限覆盖首次调用、等待与重放，超期不接收成功 | 隐藏超时预算重置、晚结果被当作及时成功 | §3.3 |
| 两次调用都封装来源并走 accept_reply，句柄后续使用再验代 | 旧代句柄迟到混入新代业务链 | §3.2 |
| manager 拥有恢复任务，关闭先拒绝新工作 | turn 取消干扰其他调用、关闭后重新入池 | §3.4 |

**崩溃点必须分开验收：** 初始化之前崩溃，重新进入时不能从持久化历史里复活旧 id；初始化成功但尚未发布时关闭，要清掉候选连接；查询重放完成但结果尚未写入工作流历史时崩溃，后续重入仍需要业务层的只读或幂等保证。最后一个问题不是 MCP 握手能替 durable execution 解决的，参见 [Checkpoint 不等于 Durable Execution](posts/durable_agent_execution.md)。

## 5. 发版前清单 (Pre-Ship Checklist)

以下是可注入的验收目标；末尾另注明本地 mock 覆盖范围，不把清单全体写成已测通过。协议层 mock 与真实 SDK 集成都要测，不能只看“重启 Agent 后又能用了”。

### 注入 1：旧会话失效，HTTP 404 的三种 body

- [ ] 初始化后使服务端忘记会话，对带旧 id 的请求分别回空 body、`-32600 Session not found`、`-32001 Session not found`；三者均识别为会话丢失。
- [ ] 抓取新 `InitializeRequest`，确认无旧 session id；完成初始化后不再发送旧 id。
- [ ] 普通 HTTP 200 的 JSON-RPC `-32600 Invalid request` 不进入会话恢复；无会话请求的普通 404 不假冒 SessionLost。
- [ ] endpoint 配错、初始化持续失败时，有明确期限和失败结果，不形成重连风暴。

### 注入 2：并发旧 404 与迟到响应

- [ ] 多个调用共用同一 epoch，首个 404 后只创建一条恢复任务；恢复中不再借出旧连接。
- [ ] A 的 404 已触发新会话发布后，B 的旧代 404 才到；新会话不被清除，也不再重复握手。
- [ ] A 在旧代请求临时句柄，B 先恢复并发布新代，A 才成功返回：来源 epoch 仍属于旧 lease，`accept_reply` 抛 `StaleSessionResult`；句柄不进入新代业务链、目录和缓存不更新。
- [ ] 对照 A 返回无会话绑定的只读值：仅在受信业务策略允许时作为旧代观测接收，保持 `source_epoch`，不更新当前会话状态。
- [ ] 句柄接收时尚同代、使用前已切代：再次借同代 lease 失败，不把它改绑到新连接。
- [ ] 其他在途写调用若结果未知，分别记录未知结果，不因会话恢复而自动重放。
- [ ] 身份或业务隔离范围不同的连接不共享恢复任务或 session id。

### 注入 3：工具重放安全性与预算

- [ ] 业务确认的跨会话只读查询可自动重放一次；wire request id 新建，逻辑业务 id 保持。
- [ ] 未证明跨会话幂等的写调用不自动重放；返回需要核对业务结果的明确状态。
- [ ] 支持业务幂等的写工具，验证去重记录跨服务端重启/会话有效；不能用 JSON-RPC id 或 session id 顶替业务幂等键。
- [ ] 重放再次 404：新会话仍失效并触发新初始化，但该业务调用退出，外层不会再无限重放。
- [ ] 网络超时、401 和普通协议错误各走各的路径，不全塞进会话恢复。

### 注入 4：总期限覆盖首次调用、等待与重放

- [ ] 首次 `invoke` 阻塞超过入口总预算：抛 `OperationOutcomeUnknown`，不标成 SessionLost，不重放。
- [ ] 首次快速 404、恢复完成后重放耗时超过剩余预算：仍按同一个绝对 deadline 超时，不在 40ms 后把结果当作 10ms 期限内的成功。
- [ ] 恢复等待耗尽预算：本次抛 `OperationDeadlineExceeded`，共享恢复仍可服务其他等待者；后续不派发重放。
- [ ] 底层抑制取消并晚返回：超期 payload 不经 accept_reply 发布为成功；检查清理所有权，不误称 Python 超时能强制抢占。

### 注入 5：新会话不等于旧状态续接

- [ ] 重握手后能力或工具 schema 改变，重新验证而不是继续发旧参数。
- [ ] 旧临时句柄、订阅、工作目录、交互上下文丢失；能够显式重建并验证才继续，否则 fail closed。
- [ ] 旧审批若与会话/资源版本绑定，恢复后重新校验，不擅自延续授权。
- [ ] 候选连接没分配 session id 的合法初始化结果，也不会破坏本地 epoch 与失效判断。

### 注入 6：等待者取消、恢复失败与 shutdown

- [ ] 一个等待恢复的 turn 被取消，`CancelledError` 传播；同代其他等待者仍可等到恢复，不被连带取消。
- [ ] 恢复失败时所有等待者得到明确失败，没有人永远等 READY；任务异常被收取。
- [ ] shutdown 先置 manager closing；关闭后首次 borrow 或 404 恢复请求均不开工。
- [ ] 初始化完成与 shutdown 交错时，新候选连接不再发布；所有所属任务被 await、所有连接被关闭。

本次对上文 Python 控制流做了 8 条本地 mock 检查：首次调用超时、10ms 总期限内的 40ms 重放拒绝、等待超时不取消共享恢复、抑制取消后的晚结果拒绝、B 切代后 A 的旧句柄拒绝、旧代普通只读值保留来源、句柄使用前再次验代、调用方取消传播，均通过。mock 为 manager 提供上述接收合同，不代表完整并发管理器、真实 SDK、HTTP 清理或 Rancher 场景已通过集成测试。

指标至少分开：带会话 404、恢复尝试/成功/失败、旧代迟到错误、禁止重放、业务重放预算耗尽。原始 session id 不进指标标签；“HTTP 又通了”不能替代“业务前置条件有效且操作得到明确结果”。

## 6. 小结 (Takeaways)

**会话失效不是多等一次就能好，重新初始化也不是重放工具调用的许可证。**

- 带 session id 的请求收到 404，要退出旧会话、发送无 id 的新初始化；不要继续携带失效 id。
- 会话丢失应保留 HTTP 与发送时上下文，不与普通 `-32600` 混为一类；专用 SDK 异常仍以实际发布接口为准。
- 并发恢复按逻辑连接隔离，同代共享、旧代错误不清新代；成功结果也保留来源 epoch，旧代句柄不得发布为新代状态。
- 总期限覆盖首次调用、恢复等待和重放，调用超时保留结果未知，共享恢复不被某个等待者取消；工具重放单独判断安全性、次数；旧会话状态、未知写结果和工作流持久化问题不会被一次握手消除。

系列位置：**Agent Runtime Failure Handling 第 5 篇**。前四篇是 [分层重试](posts/layered_retry_amplification.md)、[取消未传播](posts/mcp_cancellation_not_propagated.md)、[progress/result 分发顺序](posts/mcp_progress_same_chunk_unknown_token.md) 与 [list_changed 重入](posts/mcp_list_changed_reload_blocks_receive_loop.md)。本篇只管客户端会话终态与恢复，不把 OAuth、服务端响应流路由键碰撞或取消传播混成同一个问题。

## 参考 (References)

1. MCP — [Transports / Session Management，2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports#session-management)：带会话请求 404 后，以无 session id 的 `InitializeRequest` 开始新会话；不包含无条件重放工具的要求。
2. TypeScript SDK — [Issue #3056](https://github.com/modelcontextprotocol/typescript-sdk/issues/3056)：长跑 Rancher 场景与发布包检查来自报告者，明确版本 `@modelcontextprotocol/client` 2.0.0；本次读取状态 open。未独立运行该场景，未核当前源码修复状态。
3. Python SDK — [Issue #3799](https://github.com/modelcontextprotocol/python-sdk/issues/3799)：404 三种 body 的错误分类对照，报告测试 `mcp 2.3.0` 与开发提交 `d7845c0`；本次读取状态 open。`SessionNotFoundError` 为提案，不是本文声称可导入的 SDK 接口。
4. Temporal AI integrations — [固定提交的 MCP 协议错误分类](https://github.com/temporalio/ai-integrations/blob/88745dc256c708950c858c6a731051b7bafd5fd5/python/mcp/src/temporalio/mcp/_activities.py#L48-L59)：`INVALID_REQUEST` 在不可重试协议错误集合中；仅说明此提交，不推断所有版本。
5. 本站 — [Agent 写操作的幂等](posts/agent_write_idempotency.md)、[Checkpoint 不等于 Durable Execution](posts/durable_agent_execution.md)：跨会话重放与工作流重入的不同保证。
