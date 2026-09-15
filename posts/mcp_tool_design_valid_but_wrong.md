---
title: MCP 工具设计：为什么 Agent 总发出「合法但错误」的调用
date: 2026-09-15
tags: Agent, MCP, Tool-Calling, Schema, Context-Engineering
---

## 1. 问题现象 (Problem Symptoms)

给 Agent 接上 MCP Server 之后，最常见的失败形态不是「参数校验挂了」，而是：**调用在 schema 层面完全合法，在业务层面完全错误**。

Zod / JSON Schema 绿灯，JSON-RPC 也没抛协议错误，但结果已经偏了。这类 failure 难排查：日志里看不到 malformed payload，只有一串 well-formed wrong。

### 现象 A：选错工具——`update` 当 `send`

你暴露了 `update_invoice` 和 `send_invoice`。用户说「把这张发票发出去」。两份 description 语义重叠，模型选了 `update_invoice({ status: "sent" })`，以为改了状态就等于寄出了 PDF。每个参数都合法，邮件从未发出。

### 现象 B：合法字符串，错误枚举——`region` 自由文本

字段类型是 `region: string`。同一次任务里，模型可能写出 `"Canary Islands"`、`"canarias"`、`"ES-CN"`、`"islas canarias"`。全部是合法 string；税务引擎只认其中一个 canonical token。

### 现象 C：超时重试导致双写

`create_order` 超时。错误是一坨 stringified `500` / `timeout`，模型分不清「已落库但响应丢了」和「根本没写成功」，于是换个参数再调一次——双写。idempotency key 没进 schema，retry 变成了 side effect amplifier。

### 伴随症状：Context Bloat

多个 MCP Server 一挂上，工具定义在用户开口前就占满 context。推理能力下降 → 更差的工具选择 → 更多重试 → context 继续膨胀。Confusion 与 Bloat 互相喂养。

```mermaid
flowchart LR
  A[工具定义塞满 context] --> B[推理退化]
  B --> C[选错工具 / 填错参数]
  C --> D[重试与无效结果回流]
  D --> A
```

---

## 2. 根因分析 (Root Cause Analysis)

AWS 对 MCP 工具失效的归纳很干脆：**Confusion + Bloat**。协议本身很少是罪魁；多数团队把现有 REST API 原样 wrap 成 tool，指望模型「自己看懂」。

- **Bloat**：工具定义每轮都进 context，无论用不用。多 Server 叠加后，上下文在第一轮提问前就已稀缺。
- **Confusion**：推理变差后，模型更容易选错工具、填错参数；语义相近的工具名、开放字符串、模糊 description 再放大错误；重试继续喂大 bloat。

这不是 input-validation bug，而是 **interface design bug**。Frihet 一文把「schema 通过但行为错误」拆成四类 misuse：

| 类型 | 典型表现 | 根因杠杆 |
| --- | --- | --- |
| Wrong tool | 该 `send` 却调了 `update` | description 不互斥 / 工具边界模糊 |
| Valid-but-wrong arg | `region` 自由字符串变体 | 开放类型允许非法状态可表示 |
| Wrong order / precondition | 未 finalize 就开 credit note | 缺少状态前置条件与可行动错误 |
| Can't recover | stringified 500，盲目重试或放弃 | 错误不可分支；写操作无幂等键 |

经验研究也在侧面印证「描述层」问题的普遍性：对 103 个 MCP Server、856 个工具的扫描显示，**约 97.1% 的工具描述至少带有一种 smell**，其中约 56% 甚至未能清楚陈述用途（Unclear Purpose）。描述增强能抬升成功率，但也可能让执行步数暴涨——又一次撞上 Confusion vs Bloat 的权衡。

---

## 3. 协议要点：description 是路由契约 (Protocol Notes)

MCP Tools 规范里，工具靠 `name` + `description` + `inputSchema`（以及可选的 `outputSchema` / `annotations`）被模型发现和调用。对 Agent 而言，**description 不是注释，而是路由契约**：模型几乎只靠它决定「调谁」。两份 description 都能回答「发送这张发票」，就是你发到生产上的 routing bug。

### Protocol Error vs `isError`

规范区分两层错误，设计时必须分开用：

1. **Protocol Errors**（JSON-RPC `error`）：未知工具、参数不符合 schema、服务端协议级故障。客户端 / Host 层处理。
2. **Tool Execution Errors**（结果里 `isError: true`）：业务失败、上游 API 限流、前置条件不满足。内容会回到模型上下文，**应当写成可行动指令**（例如「请先 finalize 发票再开 credit note」），而不是裸 `500`。

把业务前置条件失败塞进 JSON-RPC `-32602`，模型往往得不到可恢复信号；把「参数类型错了」只写成散文 `isError`，又浪费了 schema 本可在协议层挡住的机会。

### Annotations 是提示，不是安全边界

`readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` 让 Host 可以对读操作自动放行、对破坏性写操作要求人工确认。规范明确：**clients MUST consider tool annotations to be untrusted unless they come from trusted servers**。真实鉴权、对象级授权、幂等与速率限制必须落在 Server 侧；annotation 只能缩小 blast radius，不能替代 enforcement。

---

## 4. 设计演进：V1 → V4 与 BAD / GOOD Schema (Design Evolution)

AWS 用同一套 K-12 内容搜索后端对照了多种工具设计。这里收敛到工程上最常落地的四档（对应其 V1–V4），并给出可直接改代码的 schema 对照。

| 版本 | 做法 | 对 Confusion | 对 Bloat | 主要代价 |
| --- | --- | --- | --- | --- |
| V1 Passthrough | API 原样暴露，一行 docstring | 极差：无合法值、无同义映射 | 定义很瘦 | 重试与空结果把真实成本打爆 |
| V2 Rich descriptions | docstring 写清合法值与同义词；砍冷门参数；错误带指引 | 明显下降 | 定义变胖 | 每轮都付描述税，多 Server 时更痛 |
| V3 Schema + defaults | 重命名贴近领域；enum / defaults；拆 detail 工具 | 进一步下降（协议层约束） | 通常比 V2 更瘦 | 需重构参数模型 |
| V4 Lazy taxonomy | 搜索工具只留短 hint；`get_taxonomy` 按需加载 | 歧义查询可先查再搜 | 基线最瘦 | 多一次 round-trip；简单查询可能跳过 |

后续还有 Server 侧 introspection（自选小模型解释自然语言 → 推荐 filter）以及 Agent-as-tool（单一自然语言入口，内部自有工具编排）。准确率与一致性更高，但推理成本与延迟归你承担——适合「必须跨客户端模型稳定」的场景。本文聚焦多数团队会先走完的 V1→V4。

### BAD：开放字符串 + 重叠描述

```typescript
// ❌ 合法但错误的温床
server.tool(
  "update_invoice",
  "Update or send an invoice", // 与 send_invoice 重叠
  {
    invoiceId: z.string(),
    status: z.string().optional(),
    region: z.string().optional(), // "Canary Islands" | "canarias" | "ES-CN"...
  },
  async (args) => { /* ... */ },
);

server.tool(
  "send_invoice",
  "Send invoice to customer", // 模型仍可能觉得 update 也能「发出去」
  { invoiceId: z.string() },
  async (args) => { /* ... */ },
);
```

对应的 JSON Schema 同样「看起来没问题」：

```json
{
  "type": "object",
  "properties": {
    "invoiceId": { "type": "string" },
    "region": { "type": "string", "description": "Customer region" }
  },
  "required": ["invoiceId"]
}
```

### GOOD：互斥描述 + 关闭非法状态 + 默认值

```typescript
// ✅ 让非法状态不可表示；让路由互斥
server.tool(
  "update_invoice",
  "Update draft invoice fields only. Does NOT email or finalize. Use send_invoice to deliver.",
  {
    invoiceId: z.string().uuid(),
    clientLocation: z
      .enum(["peninsula", "canarias", "ceuta_melilla", "eu", "world"])
      .optional()
      .describe("Fiscal zone driving IVA vs IGIC vs exempt"),
    operationType: z.enum(["service", "goods"]).optional(),
    irpfRate: z.number().min(0).max(100).optional(),
  },
  async (args) => { /* ... */ },
);

server.tool(
  "send_invoice",
  "Email the finalized PDF to the client. Requires invoice status=finalized. Not for drafting edits.",
  {
    invoiceId: z.string().uuid(),
    idempotencyKey: z.string().min(8).describe("Stable key; retries must reuse the same value"),
  },
  async (args) => { /* ... */ },
);
```

V3 风格的搜索工具还会把内部列名改成模型能懂的名字，并用 enum / default 去掉猜测：

```typescript
// V3: 领域命名 + Literal/enum + defaults（示意）
{
  subject: z
    .enum(["Math", "Science", "Literacy/ELA", "Social Studies"])
    .describe("Was: discipline"),
  resource_class: z
    .enum(["Student Resource", "Teacher Support"])
    .default("Student Resource"),
  language: z.enum(["en", "es"]).default("en"),
  // 冷门字段删除；详情走 get_resource_detail
}
```

V4 则把「合法值大表」挪出 always-loaded 定义：

```typescript
// V4: 搜索工具只留短 hint；taxonomy 按需加载
server.tool(
  "search_content",
  "Search K-12 resources. For ambiguous filters, call get_taxonomy first.",
  {
    subject: z.string().optional().describe("e.g. Math, Science, Literacy"),
    keyword: z.string().optional(),
  },
  searchHandler,
);

server.tool(
  "get_taxonomy",
  "Return valid values and NL→canonical mappings for the requested fields only.",
  { fields: z.array(z.enum(["subject", "grade", "media_type", "resource_class"])) },
  taxonomyHandler,
);
```

经验法则（AWS Prescriptive Guidance 也提到）：单工具参数尽量控制在约 **8 个以内**；响应默认返回决策所需的少量字段，详情另开工具按需拉取（Anthropic 报告过按需详情可砍掉约三分之二 response token；Tool Search / 懒加载定义在大规模场景可把工具定义 token 降到约 15% 量级）。

---

## 5. 发工具前检查清单 (Pre-Ship Checklist)

注册任何一个 tool 之前，用四类 misuse 逐条过一遍：

**Wrong tool**

- [ ] description 与邻居工具互斥，祈使句只陈述「这一件工作」
- [ ] 必要时显式写出 *does not*（例如「不发邮件」「不 finalize」）
- [ ] 用近邻 prompt（「发出去」「标记已发送」「更新状态」）做 confusion test

**Valid-but-wrong argument**

- [ ] 领域只允许 N 个值时，schema 也只允许 N 个（enum / union / 数值上下界）
- [ ] 禁止「先靠 422 教育模型」——合法值必须在 discovery 时可见
- [ ] 参数名跟领域语言对齐，而不是跟 DB 列名对齐
- [ ] 常用值给 default，让模型只填「变化的部分」

**Wrong order / precondition**

- [ ] 读工具返回当前状态 + 合法下一步（必要时带 version / ETag）
- [ ] 写工具在 Server 侧校验前置条件，失败时用 `isError` + 稳定 `errorCode` + 可行动文案
- [ ] 破坏性 / 外发副作用考虑 `plan_*` / `execute_*` 拆分

**Can't recover + Bloat**

- [ ] 错误可分支：`rate_limit_exceeded` vs `validation_failed` vs `request_timeout`（后者提示「用同一 idempotency key 重试」）
- [ ] 非幂等 create 在 annotation 标 `idempotentHint: false`，并在 schema 要求 idempotency key
- [ ] annotation 仅作 Host 门控提示；鉴权与租户范围从 Server 会话推导，不信任模型传入的 tenantId
- [ ] 工具定义与默认响应是否在「够用」和「不挤爆 context」之间做过取舍；大词表是否可懒加载

---

## 6. 小结 (Takeaways)

「合法但错误」不是模型突然变笨，而是工具面把非法状态留在了可表示空间里，又把路由信息写得像两份能互相替代的文档。

- **Confusion + Bloat** 是主矛盾：加描述能降 confusion，也会加 bloat；用 schema/enum/defaults 往往能同时改善两者。
- **description 是路由契约**；协议错误与 `isError` 分工不同；annotations 是 hint，不是 ACL。
- **演进路径**清楚：Passthrough → Rich descriptions → Schema+defaults → Lazy taxonomy；再往上才是 introspection / agent-as-tool。
- **发工具前清单**对准四类 misuse；typed input 挡的是垃圾，constrained surface 挡的才是 misuse。

下一篇会落到两件更「运行时」的事：**trajectory eval**（用近邻任务集量化 wrong-tool / wrong-arg 率，而不是只看单次 demo），以及 **idempotency**（超时、扇出、重试下如何保证写操作只生效一次）。没有这两者，再漂亮的 schema 也会在生产里被双写打穿。

---

## 参考 (References)

1. Daniel Wells, Raian Osman — [MCP tool design: Practical approaches and tradeoffs](https://aws.amazon.com/blogs/machine-learning/mcp-tool-design-practical-approaches-and-tradeoffs/) (AWS Machine Learning Blog, 2026-07-09). Confusion / Bloat 框架与 V1–V6 对照。
2. berthelius (Frihet) — [Designing MCP tools an agent won't misuse](https://dev.to/frihet/designing-mcp-tools-an-agent-wont-misuse-1ah1) (DEV, 2025-08-09). Well-formed wrong 与四类 misuse、enum 约束、annotations、typed errors。
3. Model Context Protocol — [Tools (specification 2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/server/tools). `tools/list` / `tools/call`、protocol error vs `isError`、annotations 不可单独作为安全依据。
4. arXiv:2602.14878 — [Model Context Protocol (MCP) Tool Descriptions Are Smelly!](https://arxiv.org/html/2602.14878v1). 856 工具 / 103 Server；约 97.1% 描述含至少一种 smell；增强描述的收益与步数 / 回归代价。
