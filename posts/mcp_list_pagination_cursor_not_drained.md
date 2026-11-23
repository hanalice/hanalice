---
title: 第一次 list 成功 ≠ 目录完整：nextCursor 没跟完，后页工具从未注册
date: 2026-11-20
tags: Agent, MCP, Host, Discovery, Pagination
description: 服务端已经给出 nextCursor，Host / SDK 却只拿第一页，或把合法的重复不透明 cursor 当成结束并删掉续页标记，目录看起来完整，后页工具从未注册。结束条件只能是响应省略 nextCursor；空字符串要继续走，硬上限必须 fail-loud，续页失败不得发布半份目录。MCP Host Discovery 系列第 2 篇。
---

第一次 `tools/list` 成功返回，并不等于目录完整。服务端按规范在第一页带上 `nextCursor` 之后，只要 Host 或 SDK 聚合器不再跟游标，后面几页的工具就从未进入注册表。模型看到的是一份「看起来完整」的短目录，调用页 2 的工具时得到 `"No such tool available"`，值班很容易误判成「网关没暴露这些工具」，再去改搜索策略或把 page size 调大。

本文只讨论**单次 list 的游标排空**：要不要跟 `nextCursor`，以及跟的时候用什么条件结束。它不是 [Host 渐进发现](posts/mcp_progressive_disclosure.md) 里的召回策略，也不是 [`list_changed` 刷新卡死本轮调用](posts/mcp_list_changed_reload_blocks_receive_loop.md)，更不是 [工具结果被静默裁切](posts/silent_tool_result_truncation.md)。那三篇分别讲发现策略与通知后未刷新、刷新动作重入、以及结果载荷被截断；本篇即使刷新已经成功，只要这一轮 list 没把游标跟完，页 2 仍然不会出现在目录里。MCP Host Discovery 系列第 2 篇。

## 1. 问题现象：不是网关少暴露了工具，是后页从未注册

### A. 第一页成功回来，页 2 的工具却「不存在」

一个按页返回工具目录的网关，第一页带着 `nextCursor`。Host 侧的聚合只发了一次 `tools/list`，把这一页写进了目录，就当发现完成。模型稍后要调后页的工具，得到的是 `"No such tool available"`。从调用轨迹看，这次 list 是成功的，目录里也有一批真实工具，所以故障会被说成网关配置问题，而不是发现层没有排空分页。

Python SDK 的 [`ClientSessionGroup` 聚合缺陷](https://github.com/modelcontextprotocol/python-sdk/issues/3792) 把这个形状写得很清楚：进程内 server 第一页给出工具 `first` 和 `next_cursor="page-2"`，第二页给出 `second` 且不再续页；`group.connect_with_session(...)` 之后，`group.tools` 里只有 `first`，server 也只收到一次 listing。该报告把复现绑在当时的 main `d7845c07`。同仓库的 [`list_all_*` 辅助提案](https://github.com/modelcontextprotocol/python-sdk/issues/2556) 记录了同一类接入错误：报告里的 AWS Bedrock AgentCore Gateway 有 31 个工具、分两页返回（第 0 页 14 个并带 `nextCursor`，第 1 页 17 个）；提案还写到，Claude Code、Cursor 和 Inspector CLI 都曾按「一次 list 即全部」接入，因而只看到 14 个——这是该 issue 的指认，不是本稿对 Cursor 或 Inspector 源码的独立核实。

这组「31 / 14」不要和另一份 Host 生产报告混在一起。[Claude Code #39586](https://github.com/anthropics/claude-code/issues/39586) 描述的是另一种页大小：AgentCore 按 30 个一页分页，48 个工具只注册了前 30 个。它已作为重复 issue 关闭并指向 [#59538](https://github.com/anthropics/claude-code/issues/59538)；后者同样报告过 `list_changed` 之后重拉目录，仍然只读到第 1 页。两份报告都已关闭，不能写成「当前 CLI 仍必现」，但失败面是清楚的：单次 list 没有把游标跟完，后页工具从未进入 Host 目录。

### B. 聚合结果上看不到 nextCursor，截断被当成完整

第二种更隐蔽。客户端其实已经在循环分页，却用「这个 cursor 我见过」作为结束条件，再把结果上的 `nextCursor` 删掉。截断后的短目录和完整目录在字段上看不出来。

TypeScript SDK 在修复前的 [`_listAllPages`](https://github.com/modelcontextprotocol/typescript-sdk/issues/2735) 就是这个形状。报告版本是 `@modelcontextprotocol/client` 2.0.0：服务端用稳定的空字符串 cursor 自己记账，依次给出 `alpha`、`beta`，并继续带上 `nextCursor: ""`，最后一页才是 `gamma` 且省略游标。当时的 `seen` 集合在第二页遇到重复的 `""` 就停走，再 `delete acc.nextCursor`，调用方拿到的是 `tools: alpha, beta`，`nextCursor` 为 `undefined`。这个问题已由 [PR #2886](https://github.com/modelcontextprotocol/typescript-sdk/pull/2886) 于 2026-09-28 合入，merge commit 是 `ef39308`，并写入 `@modelcontextprotocol/client` 2.2.0 的 changelog。该修复解决了「仅因 cursor 重复就停走」，但保留了「条目与游标都相同时提前结束」的启发式；本文下文的严格排空与失败不发布，是另行提出的 Host 加强设计，不是对 2.2.0 全部行为的描述。

### C. 搜索里能「看见」名字，目录里却没有这个工具

动态工具网关经常把后页的名字放进搜索类元工具。模型从搜索结果里看到了工具名，发出 `tools/call`，Host 却在自己那份短目录里找不到它。表面像搜索与执行不一致，根上仍是：第一次 list 没有把分页排空，Host 从未注册这些名字。把 page size 调大、再加一条搜索，都不会修复「一次 list 就当作目录完整」这条假设。

## 2. 根因分析：结束条件写错了，或根本没有跟游标

[MCP 2026-07-28 的分页规则](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination) 把结束信号规定得很窄。客户端 SHOULD 把**缺失的** `nextCursor` 当作结果结束；同时 MUST 把 cursor 当作不透明 token，除了「是否提供了非 null 值」之外，不得依据 cursor 的取值做任何判断。规范还写明：空字符串是合法 cursor，因此 MUST NOT 被当成结束。页大小由服务端决定，客户端 MUST NOT 假设固定页长。

失败通常叠在三层上，不必同时出现。

第一层是**单页聚合**。`ClientSession.list_tools()` 这类 API 本身是单页原语，返回一页加上可选的 `next_cursor`，这并不自动等于「给我全部工具」。#2556 也指出，更高一层的 `Client.list_tools()` 文档只写「List available tools」，没有提示分页。Host 或 `ClientSessionGroup._aggregate_components()` 若对每个 `list_*()` 只调用一次、忽略 `next_cursor`，后页组件就不会进入聚合表，也就无法经 `group.call_tool()` 到达。#3792 建议把排空放进聚合器，先在临时目录里收齐再注册；这比只在公开 API 上增加 `list_all_*` 更窄，也更贴近「连接时目录必须完整」的职责。截至本稿，#3792 与 #2556 仍 open，对应的修复 PR（包括 [#3793](https://github.com/modelcontextprotocol/python-sdk/pull/3793)，以及 #2556 下提到的 #3021、#3083、#2441）均已关闭且未合入。不能写成 Python SDK 已修复；issue 仍 open 也不等于最新 main 必现，复现请绑定报告中的 `d7845c07`。

第二层是**排空了，结束条件却写成了「cursor 取值」**。规范允许服务端发出稳定的、甚至为空字符串的 cursor，并由服务端自己推进位置。客户端若维护一个 `seen` 集合，在 `cursor` 重复时停走，就是在用取值做判断，直接违反「不得依据 cursor 值做决定」。若再删掉结果上的 `nextCursor`，截断会被缓存成完整目录。2.2.0 之后的 TypeScript 客户端不再用 `seen` 集合截断：无 cursor 的 `listTools()` / `listPrompts()` / `listResources()` / `listResourceTemplates()` 不再仅因 cursor 重复就停止，通常会跟到服务端不再发送该字段；不过已合入的实现仍保留提前结束路径：若条目与 `nextCursor` 均与上一页相同，就不追加这一页并结束行走，随后删除 `nextCursor`，聚合仍可被缓存；`listMaxPages` 仍是硬上限。这不证明目录已经完整，不能把该修复概括为本文全部保证已经实现。

第三层是**失败伪装**。续页请求失败、游标环、或走到页数上限时，如果把已经拿到的前几页标成完整目录并对外发布，调用方无法区分「这就是全部」和「后面还没读完」。#3792 的修补方向因此包含两点：在更新 group 之前，先在临时结构里排空全部页，续页失败则保持原注册不变；另外用页数上限约束不会终止的 listing。需要分清的是：用 cursor 取值做「已访问集合」来宣布结束，会回到第二层的静默截断；环与死循环应当靠页数上限 fail-loud，而不是靠「这个 cursor 见过」来假装目录完整。

## 3. 机制 / 解法要点：只把「省略 nextCursor」当作结束

### 3.1 循环直到响应省略 nextCursor

排空循环的终止条件只有一个：这一页的结果里没有 `nextCursor` 字段（在类型里通常是 `None` / `undefined`，而不是空字符串）。第一页请求不带 `cursor`；之后每一页都把上一页给出的 token 原样送回，不解析、不改写、不跨会话持久化。`list_tools()` 仍然可以保持单页原语；需要完整目录的是 Host、聚合器或明确的 `list_all_*` 辅助。不要让「一次调用成功」在语义上滑成「目录完整」。

### 3.2 空字符串与重复 cursor 都要继续走

`if not cursor` 或 `while cursor:` 会把 `""` 当成结束，少走至少一页。规范把空字符串定为合法续页 token，客户端必须把它送回服务端，而不是当成 falsy。重复出现的不透明 cursor 同样不是结束标记：服务端可能用稳定句柄自己记账，下一页仍会给出新条目。2.2.0 的已合修复仍用「条目与 `nextCursor` 都与上一页相同」来提前结束，但从客户端看到的相同页面，不能证明服务端内部位置没有推进。例如连续两页都是 `items=()`、`nextCursor=""`，第三页才有工具，提前终止就会漏掉它。**本文的 Host 加强设计不使用这个启发式**：有续页就继续请求，只有字段缺席才正常结束；不会终止的服务端交给页数上限报错。

### 3.3 硬上限必须 fail-loud，半份目录不得发布

服务端若每次都铸造新的 cursor 且永不省略该字段，客户端必须有页数上限。TypeScript 客户端在 2.0 系列就为自动聚合提供了 `listMaxPages`（默认 64），越过上限时抛出带 `SdkErrorCode.ListPaginationExceeded` 的 `SdkError`，避免把不完整聚合写入缓存。页数超限时，上游有明确报错；但相同页提前结束并不走这条报错路径。本文要求的加强保证是：**只有排空成功才能发布；超限或请求失败都明确报错，并让这次目录更新不生效**。错误的失败是：返回短列表，再把 `nextCursor` 去掉，让调用方以为已经读完。续页中途失败同样如此：先在临时目录里排空，成功后再一次性替换；失败则保留旧注册，而不是发布一半新目录。

### 3.4 先排空再做碰撞检查与对外发布

聚合表若按最终组件名做键，后页若与前页重名，会在无声覆盖里丢掉其中一方。碰撞检查要在完整目录上做，而不是只扫描第一页。资源、prompt、工具三类 list 都要走同一条排空规则；某一类未覆盖（例如 group 若根本不调用 `list_resource_templates`）应在实现说明里写清，避免把「修了工具分页」读成「目录已全部覆盖」。第 4 节示意代码把最终工具名简化为字符串：排空后先检查重名，再替换 `published`；跨页同名与页内同名都抛 `NameCollision`，不做静默覆盖或隐式去重。真实实现要在命名钩子运行后的最终路由名上检查，并对三类组件的发布定义清楚的事务边界。指标上至少要能看见 `list_pages_fetched`、是否在仍有 `nextCursor` 时把结果标成完整，以及注册数与服务端声明数是否对得上。

## 4. 同一条企业网关会话：错法 → 改法 → 失败点

下面用同一条企业网关会话 `GW-CATALOG-318` 把三种接法串起来。网关按 AgentCore 风格为 `tools/list` 分页，后面还有多个后端目标。`GW-CATALOG-318` 是设计示例，用来回扣第 3 节的结束条件与发布规则，不是一次新的线上复现。下面 GOOD 是本文的严格 Host 设计，不是 PR #2886 源码的改写；它不采用上游保留的相同页终止启发式。

### BAD #1：聚合器只取第一页，页 2 的工具从未注册

Host 经 `ClientSessionGroup` 接入。聚合对每个 `list_*()` 只调用一次，忽略 `next_cursor`。模型要调后页的 `explain_cluster`，得到 `"No such tool available"`，值班以为网关没挂这个工具。这是第 3.1 节的反面，对应 #3792 在 `d7845c07` 上的两页复现，以及 #2556 报告的「31 个工具只见 14 个」。

```python
# 示意：单次 list 的游标排空与目录发布。不是 SDK 源码，也不模拟传输 I/O。
from dataclasses import dataclass


class DrainError(Exception):
    """排空失败；调用方不得把半份目录标成完整。"""


class PaginationExceeded(DrainError):
    pass


class NameCollision(DrainError):
    pass


@dataclass(frozen=True)
class Page:
    items: tuple[str, ...]
    next_cursor: str | None = None  # None 表示省略；"" 是合法续页 token


@dataclass(frozen=True)
class Catalog:
    items: tuple[str, ...]
    complete: bool


def first_page_only(list_page) -> Catalog:
    """BAD：一次 list 成功就被当成目录完整。"""
    page = list_page(None)
    return Catalog(page.items, complete=True)


def seen_set_drain(list_page) -> Catalog:
    """BAD：把合法的重复 cursor 当成结束，并抹掉续页痕迹。"""
    items: list[str] = []
    cursor = None
    seen: set[str] = set()
    while True:
        if cursor is not None:
            if cursor in seen:
                return Catalog(tuple(items), complete=True)
            seen.add(cursor)
        page = list_page(cursor)
        items.extend(page.items)
        if page.next_cursor is None:
            return Catalog(tuple(items), complete=True)
        cursor = page.next_cursor


class HostCatalog:
    """GOOD：严格排空、检查最终名称，再一次性发布；失败保留旧注册。"""

    def __init__(self, max_pages: int = 64) -> None:
        if type(max_pages) is not int or max_pages < 1:
            raise ValueError("max_pages must be a positive integer")
        self.max_pages = max_pages
        self.published: Catalog | None = None

    def drain(self, list_page) -> Catalog:
        items: list[str] = []
        cursor = None
        for _ in range(self.max_pages):
            page = list_page(cursor)
            items.extend(page.items)
            if page.next_cursor is None:
                # items 在本模型中就是命名钩子处理后的最终工具名。
                names: set[str] = set()
                for name in items:
                    if name in names:
                        raise NameCollision(name)
                    names.add(name)
                staged = Catalog(tuple(items), complete=True)
                self.published = staged
                return staged
            # 不解析、不做 seen 去重，也不以相同页面推断排空。
            cursor = page.next_cursor
        raise PaginationExceeded(self.max_pages)

```

`first_page_only` 在第一页带 `nextCursor` 时仍返回 `complete=True`。若把该返回值当作完整目录注册，`GW-CATALOG-318` 后页的 `explain_cluster` 就不会进入 Host 的可调用表。

### BAD #2：已经会跟 cursor，却在合法的空字符串重复处静默停走

把客户端换成会循环分页的实现后，网关用稳定的空字符串 cursor 自己记账。`seen_set_drain` 在第二页遇到重复的 `""` 就返回，并把结果标成完整。目录仍然缺最后一页，字段上却看不出 `nextCursor`。这是第 3.2 节的反面，对应 #2735 修复前的 `alpha` / `beta` / `gamma` 复现。不要把这个形状写成 2.2.0 之后 TypeScript 客户端的当前行为。

### GOOD：省略才结束，重复与空 cursor 继续走，上限与失败都 fail-loud

`HostCatalog.drain` 把 `next_cursor is None` 当作唯一的正常结束；`""` 会作为下一轮请求的 `cursor` 原样送回。即使连续两页都为空且使用同一游标，也继续取第三页；如果一直没有结束信号，最多请求 `max_pages` 页后抛 `PaginationExceeded`，旧的 `published` 保持不动。这回扣第 3.1–3.3 节。

正常排空后，还要扫描全部最终名称：若前后两页都给出 `explain_cluster`，本设计抛 `NameCollision` 并保留旧目录，不发布重复项，也不让后到覆盖先到，这回扣第 3.4 节。只有全部页取得且名称校验通过，`GW-CATALOG-318` 才一次性换上新目录，最后一页工具才进入可调用表；实际 `tools/call` 路由仍须由 Host 集成测试验收，本文模型只测目录发布。

## 5. 发版前清单：用游标排空注入，而不是只跑单页 happy path

- [ ] **两页目录。** mock server 第一页带 `nextCursor`，第二页给出另一工具且不再带 cursor。期望：注册两页全部工具；Host 集成中再断言页 2 工具的 `tools/call` 成功，而不是只看第一次 list 没抛错。
- [ ] **重复不透明 cursor，含空字符串。** 中间页重复同一 cursor（包括 `""`），最后一页省略 `nextCursor`。期望：全部页被聚合；不能靠删除游标把未排空目录伪装成完整。
- [ ] **连续相同空页后仍有工具。** 前两页均为 `items=()`、`nextCursor=""`，第三页返回工具并省略 cursor。期望：三页都请求，第三页工具出现在发布目录；不能以相同页面推断结束。
- [ ] **恒定空页与续页错误。** 服务端永远返回空页与 `nextCursor=""` 时，恰好请求上限页数后抛 `PaginationExceeded`；续页请求失败时传播错误。两者均须保留同一个旧目录对象，不发布半份目录；无旧目录时仍保持未发布。
- [ ] **跨页名称冲突。** 两页都出现同一个最终工具名，最后一页无 cursor。期望：排空后抛 `NameCollision`，保留旧目录；同页重名也拒绝。失败原因是名称冲突，不是把重复 cursor 当成结束。
- [ ] **边界与来源。** `""` 不得被 falsy 检查当作结束；31/14 与 48/30 保持为两份独立报告。明确区分 TS 已合修复和本文更严格的 Host 发布保证；不把 bot 评论当作 Host 版本已修复的独立证据。
- [ ] **相邻故障仍独立验收。** 本清单不替代 `list_changed` 重入或工具结果截断测试。刷新成功后仍须跑分页注入，重拉只读第一页同样会漏工具。

## 6. 小结：第一页成功，只说明第一页成功

目录完整与否，要看这一次 list 有没有把 `nextCursor` 跟到省略为止。忽略续页、或用 cursor 取值宣布结束再删掉标记，都会留下一份看起来完整的短目录，后页工具在调用时才变成 `"No such tool available"`。排空循环的结束条件是字段缺席，空字符串和重复 cursor 都不是结束；页数上限与续页失败必须 fail-loud，并且先排空再发布。Python SDK 侧的聚合缺陷在本稿依据的 `d7845c07` 报告里仍然成立，对应 issue 在本稿取证时仍 open，相关修复 PR 未合入，不能写成已经修好；TypeScript 客户端的 2.2.0 已合入 #2886（`ef39308`），去掉了仅按游标重复停走的判断，但仍保留相同页提前结束、删除游标并缓存的路径；本文 GOOD 另外取消这条启发式，靠上限明确失败，并在最终名称校验通过后才发布。

### 参考

- [MCP 2026-07-28 Pagination](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination) — 客户端 SHOULD 把缺失的 `nextCursor` 当作结束；MUST 把 cursor 当不透明 token，空字符串 MUST NOT 当结束
- [python-sdk#3792](https://github.com/modelcontextprotocol/python-sdk/issues/3792) — 主证据（open）：`ClientSessionGroup` 忽略 `next_cursor`；复现绑在 `d7845c07`
- [python-sdk#2556](https://github.com/modelcontextprotocol/python-sdk/issues/2556) — 主证据（open）：报告称 Bedrock Gateway 31 个工具只见 14 个；提出 `list_all_*` 排空辅助
- [python-sdk#3793](https://github.com/modelcontextprotocol/python-sdk/pull/3793) — 针对 #3792 的修复 PR，closed 且未合入
- [typescript-sdk#2735](https://github.com/modelcontextprotocol/typescript-sdk/issues/2735) — 主证据（closed completed）：重复不透明 cursor 曾被静默截断
- [typescript-sdk#2886](https://github.com/modelcontextprotocol/typescript-sdk/pull/2886) — 已于 2026-09-28 合入，commit `ef39308`，写入 `@modelcontextprotocol/client` 2.2.0 changelog
- [claude-code#39586](https://github.com/anthropics/claude-code/issues/39586) / [#59538](https://github.com/anthropics/claude-code/issues/59538) — 旁证（Host 生产报告；已关闭，勿当当前 CLI 必现）；#39586 为 48 / 30，不要与 #2556 的 31 / 14 混写
- [Host 渐进发现](posts/mcp_progressive_disclosure.md) — 发现策略与 `list_changed` 未刷新；通知不等于刷新，也不等于这一次 list 已经排空
- [list_changed 刷新卡死本轮调用](posts/mcp_list_changed_reload_blocks_receive_loop.md) — 刷新动作重入；刷新成功后若只拉第一页，页 2 仍然缺失
- [静默截断工具结果](posts/silent_tool_result_truncation.md) — 截的是工具结果载荷，不是目录条目
