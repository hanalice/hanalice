---
title: MCP 响应流错投：str(id) 合并了整数、字符串与 GET 哨兵
date: 2026-11-18
tags: Agent, MCP, Server-Runtime, Streamable-HTTP, JSON-RPC
description: 同一会话里的请求可能都合法，却因 str(id) 把整数与字符串合并而收到别人的响应；内部 GET 哨兵还会被外部 id 覆盖。修复要同时保留类型、隔离命名空间、拒绝重复注册，并按所有者清理；流键修复不等于取消表修复。MCP Server Runtime Boundaries 系列第 2 篇。
---

## 1. 问题现象：不是 SSE 断了，是响应被送给了另一个请求

**JSON-RPC request id 的类型也是身份的一部分；把它转成字符串再建路由表，会把两个不同请求合并。** 即使客户端不复用 id，整数 `77` 和字符串 `"77"` 也可能共用一条响应流；如果内部 GET 流还用普通字符串作键，外部请求甚至能覆盖通知通道。修法不是给字典加锁，而是保留身份、拒绝覆盖，并让清理操作验证所有者。

这是 **MCP Server Runtime Boundaries 系列第 2 篇**。第 1 篇 [MCP Server 实例复用](posts/mcp_server_instance_reuse_cross_client_leak.md) 讲多个连接覆盖同一实例的 transport；本文讲**同一个仍然存活的 session 内，请求到响应流的索引发生碰撞**。与 [session-404 恢复](posts/mcp_streamable_http_404_session_stuck.md) 的分界也很明确：那篇是会话失效后如何恢复，这篇是会话没死、结果却走错了路。

证据范围先列清，避免把问题单状态当成最新版实测结论：

| 来源 | 报告绑定的版本 / 场景 | 本文采用的事实 |
| --- | --- | --- |
| Python SDK [#3060](https://github.com/modelcontextprotocol/python-sdk/issues/3060) | v1.27.0，有状态 Streamable HTTP | 同一个 id 被并发复用，后到注册覆盖先到，响应错投与悬挂 |
| Python SDK [#3786](https://github.com/modelcontextprotocol/python-sdk/issues/3786) | v1.30.0 / v2.3.0，有状态 Streamable HTTP | 不同类型的同文本 id 经 `str()` 碰撞；字符串 id 与 GET 哨兵碰撞 |
| Python SDK [#3807](https://github.com/modelcontextprotocol/python-sdk/issues/3807) | v2.3.0 / 报告所测 `d7845c0`，含 stdio | 另一张 `_in_flight` 表经 `coerce_request_id` 合并身份，取消命中错误 handler |

截至 2026-11-18 核查，三个 issue 均仍 open。**本文没有独立运行这些 SDK 的集成复现，也不据 open 状态断言最新 main 必然仍复现。** 下文先还原报告中的机制，再给出独立的设计示例；不把示例写成已合入的 SDK 补丁。

### A. 两个 POST 都带 id: 1：一个拿错结果，一个一直等

[#3060](https://github.com/modelcontextprotocol/python-sdk/issues/3060) 报告的顺序是：同一 session 上 A 先到、B 后到，都用整数 `1`；B 的注册覆盖 A。随后 A 的结果被送到 B 的 HTTP 流，A 的流没有收到自己的结果，另一份结果可能因为槽位已清理而丢弃。

报告者在 v1.27.0 的 12 并发实验中记录了 `same_id` 为 0 个正确、1 个错投、11 个超时，唯一 id 对照为 12 个正确。这是**报告者的实验结果**，不是本文测试数据。报告者还称 claude.ai 自定义连接器每次发送 `id: 1`，并描述过“一位用户的工具响应到了另一对话的请求”；本文没有独立抓包，也不把它扩大成已证实的任意跨租户攻击。

这里客户端违反了 id 唯一性要求，但服务器不能用“静默覆盖并返回成功”处理违规输入。SSE 心跳仍在到达，只能证明连接有字节流动，不能证明请求还能收到结果；报告中的客户端因此使用总时限，而非仅依赖每次读超时。

### B. 客户端改用不同 id，77 和 "77" 仍然相撞

[#3786](https://github.com/modelcontextprotocol/python-sdk/issues/3786) 不是 A 的重复：整数 `77` 与字符串 `"77"` 是两个不同 id，不能因为显示文本相同就认为客户端违规。报告中的共同路径是：

```python
str(77) == str("77")  # True；类型信息已经丢失
```

报告者在有状态 HTTP 上并发提交两者，取消整数请求后，字符串请求的 HTTP 流收到了整数请求的取消响应，自身 handler 未被取消但结果丢失或错投。它描述的是**响应流的目标错误**，不要直接推断成字符串 handler 被取消；后者要另查取消表。报告的 JSON / SSE、正常结束 / 取消矩阵也显示：不靠真正的重复 id，单纯类型合并就足以破坏路由。

### C. 普通字符串请求覆盖了 GET 通知流

同一个 [#3786](https://github.com/modelcontextprotocol/python-sdk/issues/3786) 还报告内部键 `GET_STREAM_KEY = "_GET_stream"` 与请求 id 共用字符串命名空间。POST 的 id 恰好是 `"_GET_stream"` 时，GET 注册被替换，随后通知丢失，原先实现用来拒绝第二条 GET 的检查也失效。

报告中第二次 GET 从预期 409 变成 200，是该实现单 GET 策略被破坏的信号；**不是说 MCP 规范统一要求第二次 GET 必须 409**。规范允许客户端开多条 SSE 流，具体实现需要明确并守住自己的策略。

## 2. 根因分析：把不同层的身份压进了同一个键

[MCP 2025-11-25 基础消息规范](https://modelcontextprotocol.io/specification/2025-11-25/basic) 要求 request id 为字符串或整数、不得为 null，并规定：

> The request ID MUST NOT have been previously used by the requestor within the same session.

这比“只要当前不在途就能复用”更强：**同一个请求方在同一 session 内，已完成的 id 也不能再次使用。** 同一规范要求响应带回对应请求的相同 id。整数和字符串的区别，不能在进入映射表后才决定要不要保留。

先把表分开看：

| 状态 / 表 | 本来标识什么 | 错误合并发生在哪里 |
| --- | --- | --- |
| `_request_streams` 等响应流索引 | 某一 session、某一方向、某个 typed id 对应的响应流 | 不检查重复注册，或用 `str(id)` 抹掉类型 |
| GET 通知流注册 | 传输内部的独立通知通道 | 把内部哨兵当作客户端也能提供的字符串键 |
| dispatcher 的 `_in_flight` | 入站请求对应的可取消 handler | `coerce_request_id` 让整数与数字字符串共享槽位 |

前两行是本文主线，第三行是相关但独立的失败面。修复 transport 的三个 `str()` 入口，不会自动改变 dispatcher 的查找规则。

响应错投不需要字典损坏，也不需要两个 CPU 同时写。以下完全串行的交错就够了：

| 顺序 | 状态变化 | 后果 |
| --- | --- | --- |
| 1 | A 把 `streams["1"]` 设为 A 的流 | A handler 开始运行 |
| 2 | B 把同一个槽设为 B 的流 | A 的流还存在，但路由表不再指向它 |
| 3 | A 产生 result，按 id 查到 B 的流 | B 收到 A 的内容 |
| 4 | B 的 writer / 清理路径移除该槽 | 余下响应可能无处投递 |

因此，一把锁若只包住 `streams[key] = stream`，不过是把**错误覆盖**执行得更有序。只有把“检查是否允许注册 + 建立唯一所有者”作为同一个原子状态转换，锁才有意义；而 `77` / `"77"` 的问题还必须先修键函数。

## 3. 机制 / 解法要点：分别守住键、注册与生命周期

### 3.1 单射键保留类型，重复 id 则在接入时拒绝

对合法 id 域，键函数必须满足：不同的 `(类型, 值)` 不得映射到同一内部键。可以用 `("int", 77)`、`("str", "77")`；不要通过解析数字、去空白或改大小写“帮忙兼容”。Python 里还应排除 `bool`：`isinstance(True, int)` 为真，不代表 JSON 布尔值是合法的 MCP request id。

作用域同样要完整：下面 §4 的注册表**每个 session、每个请求方向各一份**。若进程级共用表，键还必须包含 session 与方向；不能只把类型加回去，就允许不同 session 的整数 `77` 共用槽位。

对真正重复的 id，本文选择直接拒绝，不排队复用。活动槽位检查保护当前请求，session 生命周期内的 `seen` 集合则阻止完成后的复用。`seen` 要有资源上限：接近上限时停止接受新请求并要求新建 session，而不是逐出旧 id 后悄悄允许复用。

[#3060](https://github.com/modelcontextprotocol/python-sdk/issues/3060) 提议返回 JSON-RPC `-32600`。这是可采用的实现策略，**不是规范对这一情况指定了唯一错误码**。关键是错误经新来的 POST 自己返回，不进入已冲突的共享路由槽；旧请求不能被覆盖或取消。对于明确违规的客户端，宁可暴露错误，也不要把错误响应伪装成别人的成功。

### 3.2 所有原始 id 入口共用同一个转换，wire id 不变

只改注册处没有用。入站注册、最终响应路由、`related_request_id` 定向消息、取消索引以及公共关闭接口，都要核对各自的 id 语义：凡是按**请求身份**查找的路径，必须保持相同类型和值。但这些路径不一定属于同一张表，修改要分别落地。

对 HTTP 流表，尤其要区分：

- `close_sse_stream(raw_request_id)` 仍接受协议原始 id，在边界派生内部键。
- 内部清理使用持有的注册项 / 所有者，不再把“已经派生的键”当原始 id 转换一遍。
- wire 上响应继续使用原请求的 `77` 或 `"77"`，不能把内部元组、前缀编码返回给客户端。

[#3786](https://github.com/modelcontextprotocol/python-sdk/issues/3786) 特别提醒：机械替换为 `json.dumps(id)`，却不改关闭接口，会让原始字符串 id 的关闭路径失配。若事件存储也使用旧流键，编码变更还需要 replay 迁移策略。该 issue 的[后续评论](https://github.com/modelcontextprotocol/python-sdk/issues/3786#issuecomment-6590624510) 明确指出其候选补丁会改变字符串 id 的历史事件键；不能把重连回放兼容性当成免费附赠。

### 3.3 GET 流与请求流使用互不可达的内部命名空间

最直接的做法是用两个字段 / 两张表，而不是选一个“足够奇怪”的字符串。把 `"_GET_stream"` 改成另一个长字符串，仍然允许客户端提交同名 id，并没有建立隔离边界。

本文示例使用独立的 `get_stream` 字段，并采用单 GET 策略。生产实现也可以支持多条 GET，但必须按自身流标识管理；普通 POST 注册不得改变 GET 的数量、所有者或通知目标。

### 3.4 清理按所有者匹配，断线不等于业务取消

注册时生成不可伪造的进程内所有者引用，writer、关闭回调与清理路径持有同一个注册项。删除前比较“表内还是不是我”；不允许任意旧回调 `pop(key)` 清掉后来属于别人的对象。发送前也核对结果是否带回同一个 typed id、是否属于当前注册项。

“拒绝覆盖”与“所有者匹配”是互补约束，不是二选一：前者挡住坏注册，后者保护延迟回调、关闭竞态与后续维护路径。若实现会在重连时更换流绑定，还需要独立的绑定版本 / generation，旧 writer 不能以同一个 request id 对新绑定执行清理。

这里的 release 是**请求生命周期终结**，不是 TCP 断开的别名。[传输规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) 明确指出断开连接不应被当成取消；需要回放时，请求状态、事件存储与 HTTP writer 的寿命必须拆开。不要在 disconnect 的 `finally` 里顺手清空仍在运行的 handler。

### 3.5 取消表独立验收，不保留跨类型“猜测命中”

[#3807](https://github.com/modelcontextprotocol/python-sdk/issues/3807) 的 `_in_flight` 碰撞在 stdio 也能触发，所以不是 SSE 流表的另一种叫法。本文建议入站取消按 typed id 精确匹配，并把它作为 dispatcher 的独立改动验收，不宣称 HTTP 流键改好就已经修复取消。

还要测迟到取消：字符串 `"77"` 已结束，整数 `77` 仍在运行；若精确查找失败后尝试转整数，迟到取消仍会杀掉无关请求。只有一个候选也不能证明它就是目标。[该 issue 的后续讨论](https://github.com/modelcontextprotocol/python-sdk/issues/3807#issuecomment-6639415508) 专门指出了这个反例。去掉这种兼容行为是明确的行为变更，不是本文能替上游宣布的决定；出站 `_pending` 的响应兼容规则也应另行评估。

按[取消规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation)，未知或已完成请求的取消应忽略，并要妥善处理取消 / 完成竞态。取消方不应以“必须收到取消响应”判断取消成功；接收方通常应停止处理、释放资源且不发送该请求的响应。本文现象 B 只是复述某版本实验中观察到的取消响应，不把它写成必须实现的协议行为。

## 4. 同一条诊断业务链：错法 → 改法 → 失败点

下面是**设计示例，不是已发生的生产事故，也不是 SDK 可直接粘贴的补丁**。诊断网关把 A / B 两个调用方的 `explain_cluster` 请求汇聚到 `sess_MCP-STREAM-09`，每次请求携带不同的诊断标记，以便验收结果来源。

多租户汇聚本身还需要认证与授权隔离；不同租户优先使用隔离的安全上下文，不能把 JSON-RPC id 当租户身份。这里故意固定在一个 session 内，单独展示即使工具执行各自正确，响应路由仍可能把 A 的诊断片段交给 B。

### BAD #1：复用同一个 id，后到覆盖先到

```python
# 示意：一个 session 的入站请求方向，省略 HTTP / SSE I/O。
streams = {}

def bad_register(raw_id, sink):
    streams[str(raw_id)] = sink  # 不检查槽位是否已占用

def bad_reply(raw_id, result):
    streams[str(raw_id)].append({"id": raw_id, "result": result})

a, b = [], []
bad_register(1, a)               # A: explain_cluster("cluster_A")
bad_register(1, b)               # B: explain_cluster("cluster_B")
bad_reply(1, "diagnostic:A")     # B 的 sink 得到 A 的结果
```

先到 / 后到只是注册顺序，不保证执行完成顺序。把工具串行化能降低某些交错概率，却没有修掉“不允许覆盖”的不变量；把同 id 排队执行，也不满足同 session 内不得复用 id 的严格策略。

### BAD #2：换成不同且合法的 id，原有 str() 仍然出错

```python
# 对同一条诊断链做另一次独立试验，换新 session / 空表。
streams.clear()
a, b = [], []
bad_register(77, a)
bad_register("77", b)            # 不同 id，仍覆盖同一字符串槽
bad_reply(77, "diagnostic:A")    # B 收到整数 77 的响应
```

这次不能让客户端背“重复 id”的责任。再在同一表里放入 `streams["_GET_stream"] = get_sink`，一个同名字符串 id 的 POST 就会重演第三种碰撞。锁住赋值不会改变这两个等式。

### GOOD：每个 session / 方向一个注册表，键与所有权都显式化

下面是可执行的**状态机模型**。它用列表代替输出队列，只展示接纳、路由与清理；不实现 HTTP、SSE、重连回放或 dispatcher 取消。所有方法都在同一个事件循环线程里同步执行，中间不 `await`，因此检查与更新不可被其他协程插入；多线程 / 多进程实现必须用等价的原子操作。

```python
from dataclasses import dataclass, field


def request_key(raw_id):                        # §3.1 / §3.2
    if type(raw_id) is int:
        return ("int", raw_id)
    if type(raw_id) is str:
        return ("str", raw_id)
    raise ValueError("request id must be an integer or string")


class Rejected(Exception):
    pass


@dataclass(eq=False)
class Entry:
    raw_id: int | str
    key: tuple
    owner: object = field(default_factory=object)
    output: list = field(default_factory=list)


class SessionRoutes:
    # 一个实例只服务一个 session 的一个请求方向。
    def __init__(self, id_limit=10000):
        self.active = {}
        self.seen = set()
        self.get_stream = None                  # §3.3：不占 request key
        self.id_limit = id_limit

    def register(self, raw_id):
        key = request_key(raw_id)
        if key in self.seen:                    # §3.1：含已完成 id
            raise Rejected("duplicate request id")
        if len(self.seen) >= self.id_limit:
            raise Rejected("session id budget exhausted")
        entry = Entry(raw_id, key)
        self.seen.add(key)
        self.active[key] = entry
        return entry

    def current(self, entry):
        slot = self.active.get(entry.key)
        return slot is entry and slot.owner is entry.owner

    def deliver(self, entry, response):          # entry 来自 handler 上下文
        if not self.current(entry):             # §3.4：不能只拿 raw id 找槽
            return False
        if request_key(response["id"]) != entry.key:
            raise ValueError("response id does not match request")
        entry.output.append(response)           # 模拟向该请求的队列入队
        return True

    def related(self, raw_related_id, message):  # §3.2：原始 id 统一派生
        entry = self.active.get(request_key(raw_related_id))
        if entry is None:
            return False
        entry.output.append(message)
        return True

    def release(self, entry):                    # §3.4：终结时 compare-delete
        if not self.current(entry):
            return False
        del self.active[entry.key]
        return True                             # seen 不删除

    def close_sse_stream(self, raw_id):           # 保留 raw-id 公共契约
        entry = self.active.get(request_key(raw_id))
        return False if entry is None else self.release(entry)

    def open_get(self, sink):                    # 本例选择单 GET 策略
        if self.get_stream is not None:
            raise Rejected("GET already open")
        self.get_stream = sink

    def notify(self, message):
        if self.get_stream is None:
            return False
        self.get_stream.append(message)
        return True


routes = SessionRoutes()                        # sess_MCP-STREAM-09
notifications = []
routes.open_get(notifications)
a = routes.register(77)                         # A 的 handler 持有 a
b = routes.register("77")                       # B 的 handler 持有 b
control = routes.register("_GET_stream")         # 不会触及 GET 字段
routes.deliver(b, {"id": "77", "result": "diagnostic:B"})
routes.deliver(a, {"id": 77, "result": "diagnostic:A"})
assert a.output == [{"id": 77, "result": "diagnostic:A"}]
assert b.output == [{"id": "77", "result": "diagnostic:B"}]
routes.notify({"method": "notifications/tools/list_changed"})
assert len(notifications) == 1
routes.release(a)
assert not routes.deliver(a, {"id": 77, "result": "late:A"})
```

映射回第 3 节，每处改动都有独立目的：

| 改动 | 回扣机制 | 在这条诊断链上挡住什么 |
| --- | --- | --- |
| `request_key` 保留类型，公共关闭 / related 也用它 | §3.1 / §3.2 | A 的整数键与 B 的字符串键不相等，字符串 id 的关闭不会误中整数 |
| `seen` + 原子接纳，失败在启动 handler 前返回 | §3.1 | 两个 `1` 不再覆盖；第一次完成后第二次 `1` 也被拒 |
| `get_stream` 独立字段 | §3.3 | `"_GET_stream"` 只是普通请求，通知目标保持不变 |
| handler 上下文保留 `Entry`，清理做 compare-delete | §3.4 | 迟到结果 / 旧关闭回调不能修改不属于它的槽 |
| dispatcher 另设 typed-id 入站索引并单测 | §3.5 | 取消 A 不会取消 B；这部分不由上述流表模型冒充实现 |

`Rejected` 在 HTTP 接入层应被转换为明确错误，并直接写回**被拒的那个 POST**；只有 `register()` 成功后才能启动工具。不要 catch 后继续分派，不要用旧槽发送错误。模型的 `close_sse_stream` 表示显式终结请求路由，内部旧回调必须调用携带 `Entry` 的 `release()`，不能以 raw id 冒充所有者；它不是 disconnect 处理器，也不负责取消工具。

真实部署的异步 writer 还须绑定该 `Entry` 专属的输出队列，I/O 期间不能重新按 raw id 找“当前流”。`related()` 模型只表达当前注册项的定向消息查找；历史回放、重新绑定以及迟到的内部消息需要额外的绑定版本 / 来源校验，不能拿这段简化模型证明重连已安全。

最后单独演练取消：在 dispatcher 的入站表里让 `77` 与 `"77"` 同时运行，精确取消前者，只验证整数 handler 收到停止信号，字符串 handler 继续；再让字符串请求先结束，发送它的迟到取消，整数请求仍须继续。这个断言测的是“取消找谁”，不是“HTTP 响应写哪条流”。与 [MCP 取消未传播](posts/mcp_cancellation_not_propagated.md) 也应划界：传播链再完整，入口选错 handler 一样会取消错误工作。

## 5. 发版前清单：用身份冲突注入，而不是只跑唯一整数 happy path

- [ ] 同一 session 并发提交两个整数 `1`，用屏障固定先后次序。第二个在工具启动前被明确拒绝；第一个仍能收到自己的结果；错误经第二个 POST 返回，不借用第一条流。
- [ ] 第一个 `1` 完成后再次提交 `1`，仍按 session 唯一性策略拒绝；达到 id 预算时有显式新建 session 策略，不逐出 `seen` 掩盖复用。
- [ ] 并发 `77` / `"77"`、`0` / `"0"`，颠倒注册顺序和完成顺序；在 JSON 与 SSE 响应模式下，每条结果均保留原 id 类型和诊断标记，不能仅比对 `str(id)`。
- [ ] GET 已打开时 POST `"_GET_stream"`，通知仍可达。第二次 GET 符合实现所声明的单流 / 多流策略，而非硬套一个协议没有统一指定的状态码。
- [ ] 给 `related_request_id` 分别传整数与字符串，目标互不混淆；公共 `close_sse_stream("77")` 不会关闭整数 `77`，也不会把内部编码当原始 id 再编码。
- [ ] 注入旧 writer 延迟返回、重复清理与伪造的旧注册项：只允许当前所有者发送 / 删除。断线不自动取消 handler；若支持重连，额外验证绑定版本和历史事件键迁移。
- [ ] 单独测试 dispatcher：取消整数不影响字符串，取消字符串不影响整数；字符串先完成后的迟到取消也不能经 coercion fallback 命中整数。stdio 与 HTTP 都覆盖，不能只测 HTTP 流键。
- [ ] 不以“被取消请求必须返回响应”作成功标准；断开、取消、超时分别记录。超时只说明结果未知，不代表执行没有发生，更不能直接重放有副作用的工具。
- [ ] 两个 session 都用整数 `77`，两个请求方向也允许出现同值 id，表的作用域必须隔离。认证 / 授权测试独立存在，不以路由正确替代租户隔离。
- [ ] 观测被拒的重复注册、身份校验失败、过期所有者清理与请求总时限；日志保留 id 的类型，不记录敏感结果正文，不把原始 id / session id 直接当高基数指标标签。

上述清单是生产验收目标。本文本地 15 项自检覆盖 §4 同步路由模型与独立取消索引模型的确定性交错，**不等价于跑通 SDK、JSON / SSE 网络传输、事件存储或网关集成**。#3060 的 stateless 对照仅支持其同 id 覆盖实验路径；不能据此宣布切 stateless 就修复所有类型碰撞和取消表问题。

## 6. 小结：能存进字典，不代表保住了请求身份

同 id 复用、不同类型被归一化、内部哨兵占用外部命名空间，会得到相似的“响应去了别人那里”，却不是同一个输入错误。真正的修复要分别回答：**两个协议身份是否可能同键、重复注册是否被拒绝、内部通道能否被外部值表示、迟到清理还能不能删错对象。**

本篇推进的是 MCP Server Runtime Boundaries #2 的请求路由边界，不是实例复用、会话恢复或取消传播的重复讲解。HTTP 流表与 dispatcher 取消表必须各自验收；不要把“我已经修了一个 `str()`”当成整条调用链身份安全的证明。

### 参考

1. MCP 2025-11-25 — [Basic / Messages](https://modelcontextprotocol.io/specification/2025-11-25/basic)：id 类型、同 session 不得复用、响应带回相同 id。
2. MCP 2025-11-25 — [Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)：Streamable HTTP、GET / POST、断线与取消分离、流与回放。
3. MCP 2025-11-25 — [Cancellation](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation)：取消 / 完成竞态与未知请求处理。
4. Python SDK — [#3060，同 id 并发复用错投](https://github.com/modelcontextprotocol/python-sdk/issues/3060)：v1.27.0 报告；客户端行为与生产事件均归因于报告者。
5. Python SDK — [#3786，typed id 与 GET 哨兵碰撞](https://github.com/modelcontextprotocol/python-sdk/issues/3786)：v1.30.0 / v2.3.0 报告；[后续候选修复说明](https://github.com/modelcontextprotocol/python-sdk/issues/3786#issuecomment-6590624510) 讨论三处转换、raw-id 关闭契约及事件键兼容性，不代表已合入。
6. Python SDK — [#3807，入站取消索引类型合并](https://github.com/modelcontextprotocol/python-sdk/issues/3807)：与 HTTP 流表分开；[迟到取消反例](https://github.com/modelcontextprotocol/python-sdk/issues/3807#issuecomment-6639415508) 说明精确查找后再跨类型回退仍不安全。其 CI 数字为报告者证据，本文未复跑。
7. 本站 — [MCP Server 实例复用](posts/mcp_server_instance_reuse_cross_client_leak.md)：MCP Server Runtime Boundaries #1，连接 / 实例层，与本文 session 内路由层划界。
8. 本站 — [MCP session-404 恢复](posts/mcp_streamable_http_404_session_stuck.md)、[MCP 取消未传播](posts/mcp_cancellation_not_propagated.md)：分别是会话恢复与取消传播，不等于请求身份匹配。
