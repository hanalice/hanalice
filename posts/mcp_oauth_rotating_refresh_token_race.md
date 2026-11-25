---
title: 两个 401 同时刷新：旋转 refresh token 的并发重用会让授权失效
date: 2026-11-25
tags: Agent, MCP, OAuth, Refresh-Token, Concurrency
description: 多个请求同时收到 401，各自提交同一个旋转 refresh token，第二笔可能触发重放检测，连第一笔的新凭证也失效。刷新须按凭证记录单飞，重读新版本，持久化后才放行；invalid_grant 与结果不明不能继续重发旧令牌。MCP Auth Token Lifecycle 系列第 1 篇。
---

多个调用同时遇到 access token 过期，不能各自刷新后再继续。旋转 refresh token 往往只允许兑换一次：第一笔成功，第二笔提交旧令牌可能被当成重放，连刚产生的新凭证也被撤销。正确边界是同一凭证记录的 refresh single-flight（刷新单飞）、新凭证持久化后再放行，以及对 `invalid_grant` 和结果不明分别停止重发旧令牌。

这是 MCP Auth Token Lifecycle 系列第 1 篇。它发生在用户已经完成授权之后，不重讲 [身份不等于资源受众](posts/mcp_auth_identity_not_intent.md) 或 [consent 回调绑定](posts/mcp_consent_binding_confused_deputy.md)；也不是 [MCP Session ID 的 404 恢复](posts/mcp_streamable_http_404_session_stuck.md)。这里需要协调的是 OAuth 凭证记录，不是传输 session，也不是业务请求的重试次数。

## 1. 问题现象：一次刷新成功，整条连接随后却不能用了

### A. 两个调用各自处理 401，第二笔刷新被当成重放

[TypeScript SDK #1760](https://github.com/modelcontextprotocol/typescript-sdk/issues/1760) 报告两个并行请求收到 401 后各自调用 `auth()`，从同一 provider 读取同一个 refresh token，然后各发一次 refresh grant。报告以 Atlassian、Asana 的旋转策略为例，错误栈出现 `InvalidGrantError: Invalid refresh token`；这是报告者的环境与举例，不是所有授权服务器的统一行为。

[#2915](https://github.com/modelcontextprotocol/typescript-sdk/issues/2915) 进一步给出 `@modelcontextprotocol/client` 2.2.0、Node 22、Streamable HTTP 环境。作者自述：真实请求并发约 12 次中有 2 次触发，直接并发提交两笔 refresh 时 10 次都触发。这些是该作者的测试，不是本文实测概率，更不表示任意部署必现。关键现象是：第一笔换到了新令牌，第二笔 `invalid_grant` 之后，后续调用仍然失败。

### B. 日志说重试授权，实际又提交了一次已被拒绝的令牌

看起来合理的恢复逻辑是：捕获 `invalid_grant`，清掉旧凭证，再运行授权入口。但清理接口如果是可选的，provider 又没有实现，下一次读取仍是同一个 refresh token，程序就再次走 refresh 分支，而不是进入用户授权。

[候选修复 #2924](https://github.com/modelcontextprotocol/typescript-sdk/pull/2924) 正在处理这个独立缺口：让已被拒绝的 refresh token 不再被立即重试和后续调用重复提交。它不能代替并发去重；把重试路径修好，也不能撤回已经并发发出的第二笔 refresh。

### C. 代理拒绝旧令牌，不等于所有版本都会立即结束授权

[FastMCP #4901](https://github.com/PrefectHQ/fastmcp/issues/4901) 报告的版本是 3.4.4，另称在 3.4.2–3.4.7 的部署复现。报告中的模式是第一次 `/token` 成功旋转，随后旧令牌再请求得到 `401 invalid_grant`、`already rotated`。这些错误文本与会话丢失结论只属于该报告。

不能沿用这个旧报告描述新版本。[4.2.4 发行记录](https://github.com/PrefectHQ/fastmcp/releases/tag/v4.2.4) 已收入 [#6614](https://github.com/PrefectHQ/fastmcp/pull/6614)，保证并发下代理授权码和 refresh token 只兑换一次；[4.2.5](https://github.com/PrefectHQ/fastmcp/releases/tag/v4.2.5) 又收入 [#6706](https://github.com/PrefectHQ/fastmcp/pull/6706) 的重用检测。本文核对的 [v4.2.6 源码](https://github.com/PrefectHQ/fastmcp/blob/v4.2.6/fastmcp_slim/fastmcp/server/auth/oauth_proxy/proxy.py) 中，旧令牌旋转后 60 秒内重用仍被拒绝，但不因这次重用结束授权族；超过窗口才结束 grant。**这不是给旧令牌返回同一对新令牌。** 后者是 #4901 的提案，不是当前实现；issue 仍 open 也不能证明新版本仍无宽限、第二笔就立即永久掉线。

## 2. 根因分析：同一份凭证，被当成可以独立重试的输入

旋转会改变凭证的有效性。[RFC 9700 §4.14.2](https://www.rfc-editor.org/rfc/rfc9700.html#section-4.14.2) 描述 refresh token rotation：每次刷新发出新 refresh token，并使旧令牌无效；后续重用会暴露可能的泄漏，授权服务器无法判断是哪一方在重用，可以通过撤销活跃 refresh token 阻止攻击。该节对 public client 要求使用 sender-constrained token 或 rotation 等所列方法检测重放，不能简化成所有 OAuth 部署都一定旋转、一定撤销所有 access token。

所以两个合法客户端请求，在授权服务器眼里也可能与「旧令牌被盗后重用」无法区分。它不是一个无状态的查询接口：再发一次并不只是多消耗一次配额。

客户端缺口有两个相互独立的位置。本文读取的 [TS main `5ee54ee` 的 auth.ts](https://github.com/modelcontextprotocol/typescript-sdk/blob/5ee54ee/packages/client/src/client/auth.ts) 中，`auth()` 直接进入 `authInternal()`；后者读取 provider tokens 后刷新，再调用 `saveTokens()`，这段路径没有把同一凭证记录的并发调用合成一次。`invalid_grant` 分支又使用 `invalidateCredentials?.('tokens')` 后重新进入 `authInternal()`；可选调用不等于凭证真的已经失效。[1.32.2 的对应源码](https://github.com/modelcontextprotocol/typescript-sdk/blob/1.32.2/src/client/auth.ts) 同样可见直接刷新及可选清理路径。本轮是指定源码检查，没有重跑 SDK 竞态集成复现，不能凭 issue open 推导所有发行版都坏。

截至本稿取证，并发修复 [#2757](https://github.com/modelcontextprotocol/typescript-sdk/pull/2757) 与恢复修复 [#2924](https://github.com/modelcontextprotocol/typescript-sdk/pull/2924) 均 open、未合。#2757 提出的 `withAuthTransaction` 跨进程钩子也仍是候选接口，不是可直接依赖的现成功能。

再往下还有一个提交边界：服务端已经消费旧令牌，并不意味着客户端把新令牌存好了。成功响应之后存储失败、或者服务端成功而响应丢失，都不能安全地理解为「这次没发生，再提交旧令牌」。只给 HTTP 请求外面加锁，却在持久化之前释放，仍会让后到者读取旧凭证。

## 3. 机制 / 解法要点：协调完整刷新事务，不只协调网络请求

### 3.1 按凭证记录单飞，等待者重读已提交版本

同一授权记录的并发刷新共用一次在途操作。协调范围至少包括读取当前版本、兑换、保存新凭证及错误状态；等待者只能在保存成功后拿到结果。迟到的 401 还带着旧 access token 的版本，若存储已经更新，就直接使用新版本，不要再旋转一次。

不能只按 server URL 分组，更不能仅按 provider 对象地址假设所有访问都被覆盖。应用应以稳定的授权记录 ID 识别同一 refresh lineage，并绑定 issuer、client_id、账号；同一记录即使被多个资源或适配器引用，也要共用串行化边界。不同资源、scope 或授权操作不一定能共用结果：它们应在同一记录事务下重新校验请求上下文，scope 升级转新的授权流程，而不是套用旧权限。本文模型只处理**一个固定授权上下文、一个进程、一个事件循环、每条记录唯一 broker**的情况。

### 3.2 invalid_grant 后先重读，仍是旧版本就停止 refresh

在同一事务中重读持久化凭证。若另一个受协调的写入者已经保存了新版本，可交给调用方使用并重新验证；这不保证该新版本没有被授权服务器撤销，仍需验证实际响应，不能无限循环。若存储仍是已拒绝的旧版本，就把该记录置为 `reauth_required`，退出 refresh 路径，把重新授权交给 Host。

清理回调缺席不能让旧令牌再出现。Host 必须有自己的拒绝记录或持久化状态，后续调用也要检查；重新授权完成并可靠保存新版本之后才解除阻断。锁不覆盖浏览器 consent，也不由后台请求擅自弹出多个登录窗口。`invalid_client`、scope 不足、配置错误和 `invalid_grant` 不是同一种恢复条件，不应统统清空账号后重试。

### 3.3 响应丢失或保存失败，进入恢复状态，不重发旧令牌

令牌兑换成功、但新凭证未持久化时，不向等待者宣布成功。超时或断连导致兑换结果不明，也先阻断该记录的自动 refresh，再由受控恢复流程处理；除非授权服务器明确提供可验证的幂等契约，否则不能用旧 refresh token 盲重试。

调用方取消等待，不等于取消整个共享刷新。共享任务由 broker 持有，单个等待者取消只影响自己；任务继续到持久化或明确失败，并消费无人领取的异常。应用关闭时仍要等待或记录未完成事务；若 Host 显式取消共享任务，在能够保存标记时记录结果不明并传播取消。本地模型会屏蔽等待者取消，但不模拟进程崩溃；跨重启的未知状态必须持久化。令牌和失败正文不得写进诊断日志，只记授权记录 ID、版本、等待次数和恢复分类。

### 3.4 跨进程共享凭证，需要更大范围的所有权

进程内 Promise、锁或 broker 只能约束本进程。两个 worker 若共享同一份 refresh token，需要共享凭证服务或覆盖读取、兑换、持久化的跨进程事务。比较并交换（CAS）可防止旧写覆盖新版本，却挡不住两个进程已经各自向授权服务器提交旧令牌；租约过期后的 fencing token 也不能自动撤回外部请求。丢失所有权后不得继续兑换，外部结果不明要停止自动重试。强一致存储、所有参与者遵循同一协调协议和崩溃恢复都需要单独验收；不能把本文本地示意当成分布式解决方案。

代理侧重用策略又是另一个边界。FastMCP 4.2.6 的 60 秒窗口只减少近同时重用导致的授权族撤销，并不会给输掉竞争的客户端补发新凭证；客户端仍须共享新版本。不要为了掩盖竞态，无限期接受旧令牌、关闭重放检测，或把 #4901 的“短窗返回同一对新令牌”提案写成规范保证。

## 4. 同一条连接 CONN-OAUTH-209：错法 → 改法 → 失败点

`CONN-OAUTH-209` 是一个设计示例：Host 已授权，在一个固定授权上下文中并行查询两个工具。下面用整数版本替代凭证，不含真实 access / refresh token，也不是 SDK 或 FastMCP 源码。业务 `tools/call` 不在模型中自动重放，工具副作用与幂等仍按 [写操作幂等](posts/agent_write_idempotency.md) 独立判断。

### BAD：每个调用自行刷新，失败又拿同一版本再来

两笔调用都带版本 0 得到 401，并各读到版本 0 的 refresh token。第一笔把授权服务器推进到版本 1；第二笔仍提交版本 0，可触发重放检测。即使保存了版本 1，也可能已经失效。

```python
# 示意：两个调用早已读到同一代凭证；exchange 模拟单次兑换。
async def bad_refresh(store, exchange):
    old = store.read()
    try:
        new = await exchange(old)
    except InvalidGrant:
        # BAD：所谓“重试授权”仍是刷新同一版本。
        new = await exchange(old)
    store.cas(old, new)
    return new
```

### GOOD：同一记录唯一 broker，共享任务覆盖到持久化

回扣 §3.1，迟到者先查版本、并发者等待同一任务；回扣 §3.2，明确拒绝的旧版本转重新授权；回扣 §3.3，未知结果与保存失败转阻断状态。`Store.cas` 在模型里同步且原子，生产中需由真实事务实现；这里并未用 CAS 代替 §3.4 的跨进程刷新所有权。

```python
# Python 3.11+ 控制流模型。版本代替凭证；不模拟 OAuth 报文与网络。
import asyncio
from dataclasses import dataclass

class InvalidGrant(Exception):
    pass

class Reauthorize(Exception):
    pass

class RecoveryRequired(Exception):
    pass

@dataclass(frozen=True)
class Record:
    version: int
    state: str = "ready"

class Store:
    def __init__(self):
        self.value = Record(0)
        self.fail_write = False

    def read(self):
        return self.value

    def cas(self, expected, new):
        if self.fail_write:
            raise OSError("storage unavailable")
        if self.value != expected:
            raise RecoveryRequired("credential version changed")
        self.value = new

class Broker:
    # Host 注册表确保每条凭证记录仅有一个实例，且授权上下文固定。
    def __init__(self, store, exchange):
        self.store, self.exchange = store, exchange
        self.pending = None
        self.blocked = False

    async def recover(self, failed_version):
        if failed_version > self.store.read().version:
            raise RecoveryRequired("unknown failed credential version")
        if self.pending is None:
            self.pending = asyncio.create_task(self._refresh(failed_version))
            self.pending.add_done_callback(self._finished)
        return await asyncio.shield(self.pending)

    def _finished(self, task):
        if self.pending is task:
            self.pending = None
        if not task.cancelled():
            task.exception()  # 无等待者时也回收异常。

    def _mark(self, old, state):
        self.blocked = True  # 就算状态写入失败，本 broker 也不再重发旧令牌。
        self.store.cas(old, Record(old.version, state))

    async def _refresh(self, failed_version):
        old = self.store.read()
        if self.blocked or old.state == "uncertain":
            raise RecoveryRequired()
        if old.state == "reauth_required":
            raise Reauthorize()
        if old.state != "ready":
            raise RecoveryRequired("unknown credential state")
        if old.version > failed_version:
            return old  # 迟到的 401；新版本已保存，不再刷新。
        if old.version != failed_version:
            raise RecoveryRequired("unexpected version")
        try:
            new = await self.exchange(old)
        except InvalidGrant:
            current = self.store.read()
            if current.state == "ready" and current.version > old.version:
                return current
            self._mark(old, "reauth_required")
            raise Reauthorize() from None
        except asyncio.CancelledError:
            # 直接取消共享任务属于 Host 关机/终止，不是假装兑换没发生。
            self._mark(old, "uncertain")
            raise
        except Exception:
            # 超时/未知兑换结果：宁可阻断，也不假设旧令牌尚未消费。
            self._mark(old, "uncertain")
            raise RecoveryRequired() from None
        try:
            if new != Record(old.version + 1):
                raise RecoveryRequired("unexpected exchange result")
            self.store.cas(old, new)
        except Exception:
            self.blocked = True
            # 存储也可能不可用；此时跨重启恢复不在模型保证内。
            raise RecoveryRequired("exchange completed; commit not confirmed") from None
        return new  # 只在保存成功后交给全部等待者。
```

`Record.version` 是 Host 对同一凭证记录的单调版本，不是 OAuth 令牌里的字段，真实实现应把整组 access / refresh token 与元数据原子提交。模型发生 `invalid_grant` 后，首批等待者收到 `Reauthorize`；后续因 broker 已阻断可收到更一般的 `RecoveryRequired`，两者都不能自动重新 refresh。Host 负责统一展示一次恢复入口；持久化标记失败时原始存储错误也可能上抛，安全性来自 broker 已被阻断，而不是错误名称。

这段 GOOD 是本文设计，不声称上游已经实现。它不持有跨进程锁，不覆盖授权浏览器往返、进程重启或网络集成；从重新授权返回时，Host 必须保存新版本并建立干净的 broker，再解除恢复状态。不能只清空内存 `blocked` 后继续使用版本 0。

## 5. 发版前清单：注入并发、拒绝和提交不确定性

- [ ] **并发 401。** 两个调用明确都在版本 0 上失败，兑换用 barrier 暂停；断言只发生一次兑换，两个等待者拿同一已持久化的新版本。另跑 BAD，验证重复兑换如何触发重放，而不靠随机 sleep 等待撞上竞态。
- [ ] **迟到 401。** 版本 1 已保存后才处理版本 0 的失败；不再发 refresh。不同授权记录各用自己的 broker，不串账号；同一记录不能因不同 provider 包装器而创建两把互不相干的锁。
- [ ] **明确拒绝。** 兑换返回 `invalid_grant` 且没有新版本：转恢复状态，随后再次调用也不重发旧令牌。可选清理未实现不能改变这个结论；若存储已有新版本，重读后使用，但不承诺它必然未被撤销。
- [ ] **取消等待者。** 取消一个调用不取消共享兑换；另一个等待者仍在提交完成后拿结果。没有等待者时也不能遗失任务及异常，关机要接管未完成操作。
- [ ] **兑换成功、保存失败。** 不向任何等待者返回成功，新版本不被假装持久化；后续不再使用旧令牌。跨重启另测恢复日志及持久化的未知状态，本文进程内标记不能代替它。
- [ ] **成功响应丢失。** 服务端已经旋转但客户端超时：阻断自动 refresh，不再提交同一旧令牌。只有经授权服务器明确约定的幂等恢复才能例外。
- [ ] **跨进程。** 两个 worker 共享凭证库，验证兑换前的所有权及提交后释放；单独的 CAS、进程锁或未合 PR 接口不能算通过。
- [ ] **代理版本。** 用 FastMCP 4.2.6 集成注入近同时与超 60 秒旧令牌重用：两者都不应换得新令牌，前者保留 grant，后者结束 grant。不要把 3.4.x 报告或“同一对新令牌重放”提案作为新版本的验收结果。

## 6. 小结：刷新成功的边界，是新凭证已经可靠提交

并发处理两个 401 时，正确目标不是让每个请求都“努力刷新一次”，而是让同一凭证记录只发生一次受控兑换，让等待者拿到已提交的新版本。`invalid_grant` 后仍提交旧令牌，与成功兑换后丢掉新令牌，是两个独立的恢复缺口；单飞之外还需要版本重读、拒绝状态和结果不明时停止重试。

本篇推进的是授权后的 Token Lifecycle，不把身份、consent、MCP Session ID 或重试放大再讲一遍。引用的 SDK 源码、候选修复与 FastMCP 已发行行为各有边界；下面的参考也区分报告、源码和本文模型，不能用模型测试替代真实 SDK / IdP / 多进程集成验收。随稿脚本从 Markdown 提取 BAD / GOOD，21/21 项独立模型测试通过，覆盖并发、迟到 401、拒绝状态、取消、响应丢失、保存失败及 CAS 防覆盖；它不证明真实授权服务器或代理的行为。

### 参考

- [RFC 9700 §4.14.2](https://www.rfc-editor.org/rfc/rfc9700.html#section-4.14.2)，rotation 与重放检测的授权服务器语义。
- [TS #1760](https://github.com/modelcontextprotocol/typescript-sdk/issues/1760) 与 [#2915](https://github.com/modelcontextprotocol/typescript-sdk/issues/2915)，并发与恢复失败报告；2/12、10/10 均为报告者自述。
- [TS auth.ts @5ee54ee](https://github.com/modelcontextprotocol/typescript-sdk/blob/5ee54ee/packages/client/src/client/auth.ts) 与 [1.32.2](https://github.com/modelcontextprotocol/typescript-sdk/blob/1.32.2/src/client/auth.ts)，本稿读取的源码边界，未跑 SDK 竞态集成。
- [候选并发修复 #2757](https://github.com/modelcontextprotocol/typescript-sdk/pull/2757) 与 [候选恢复修复 #2924](https://github.com/modelcontextprotocol/typescript-sdk/pull/2924)，本稿取证时均 open 未合，接口不视作现成功能。
- [FastMCP #4901](https://github.com/PrefectHQ/fastmcp/issues/4901)，3.4.x 环境报告及短窗重放提案，不是 4.2.6 行为证明。
- [FastMCP 4.2.4](https://github.com/PrefectHQ/fastmcp/releases/tag/v4.2.4)、[4.2.5](https://github.com/PrefectHQ/fastmcp/releases/tag/v4.2.5) 与 [v4.2.6 代理源码](https://github.com/PrefectHQ/fastmcp/blob/v4.2.6/fastmcp_slim/fastmcp/server/auth/oauth_proxy/proxy.py)，分别核 #6614、#6706 的发行与当前窗口行为，未重跑代理集成。
- [身份与受众](posts/mcp_auth_identity_not_intent.md)、[consent 绑定](posts/mcp_consent_binding_confused_deputy.md)、[Session ID 恢复](posts/mcp_streamable_http_404_session_stuck.md) 与 [分层重试放大](posts/layered_retry_amplification.md)，相邻但不同的失败面。
