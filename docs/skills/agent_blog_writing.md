# Skill: Agent 技术博文写作规范

> 适用于 `hanalice/hanalice` 仓库 `posts/` 下的技术博文。  
> **结构标杆范文：** `posts/durable_agent_execution.md`（问题→根因→机制/解法→同一案例错对→清单→小结+参考）。  
> **语气与深度参考：** `posts/mcp_tool_design_valid_but_wrong.md`、`posts/agent_write_idempotency.md`（仍须含 `description`）。  
> 用语细则另见同目录 `github_profile_engineering.md` §8。  
> **选题来源：** 滚动文件 `docs/blog-backlog.md`（由选题 Agent 持续补充，**不是**本文内的固定列表）。

---

## 1. 定位与读者 (Positioning)

| 项 | 要求 |
| --- | --- |
| 作者人设 | **经验丰富的 Agent 架构师**：写生产里踩过的坑与可复用的设计决策，不是教程作者科普入门 |
| 读者 | 正在做 Agent / MCP / 工具调用 / 评估 / 长跑编排的工程师 |
| 文章类型 | **踩坑帖 / 排查帖** 优先；允许「对照实验 + 设计演进」 |
| 禁止 | 概念清单、「什么是 Agent」、无案例的框架对比、只有口号没有机制 |

一句话检验：删掉所有专有名词品牌名之后，文章是否仍在讲一个**可复现的失败机制**和**可落地的改法**？若否，重写。

---

## 2. 选题标准与滚动 Backlog (Topic Gate + Living Backlog)

### 2.1 准入门槛（每条选题必须满足）

1. **有失败形态**：能写成「现象 → 误判 → 根因 → 修复」  
2. **有机制可拆**：协议 / 运行时 / 评估至少一层说透  
3. **有对照或清单**：坏 vs 好、V1→Vn、checklist 至少一种  
4. **不与已发文重复**：查 `posts/` 与 `tags/`；同主题须推进到新失败面  

不满足则标为 `rejected`，并写一句原因，供选题 Agent 学习。

### 2.2 滚动 backlog（单一事实源）

- 文件：`docs/blog-backlog.md`  
- **禁止**把「当前热门选题列表」写死在本规范正文；规范只定义门槛与格式  
- 状态机：`idea` → `ready` → `writing` → `in_review` → `published` | `rejected` | `parked`  
- 选题 Agent：**只负责**调研并追加/更新 backlog（可改优先级，不直接写 `posts/`）  
- 写稿 Agent：只从状态为 `ready` 的条目取最高优先级一条，改为 `writing`  
- 审阅 Agent：对照本文 §3–§7 与验收清单；**Approve = ship-ready**（不够深则 request changes，不软通过）；通过后 Coordinator **立即** push，不重等 Alice「批准 push」

### 2.3 backlog 条目模板

```markdown
### [ready] 2026-09-16 | P0 | trajectory-eval-false-green
- **工作标题：** …
- **失败面：** …
- **为何够深（非科普）：** …
- **拟用案例 / 对照：** …
- **相关已发文：** 无 / 链接
- **参考线索：** URL 或关键词
- **备注：** …
```

---

## 3. 文章结构模板 (Structure)

**默认六段，以后所有新博文按此写**（可按坑微调小节名，但不得缺「现象 / 根因 / 机制解法 / 同一案例错对 / 清单 / 小结+参考」）：

```text
1. 问题现象 (Problem Symptoms)
   — 先罗列 2～3 个短案例 A/B/C；每个「看起来合理」却失败
2. 根因分析 (Root Cause Analysis)
   — 可命名分层 / 对照表；说清误判（把多层保证叠成一个词）
3. 机制 / 解法要点 (Mechanism / Solutions)
   — 可复用的改法与边界（专名在前）；不是产品说明书，不是入门教程
4. 同一条业务链：怎么接、错在哪、改完怎么走
   — 案例+代码贯穿同一业务 ID；先错后对；每处改动回扣第 3 节哪条解法
5. 发版前清单 (Pre-Ship Checklist)
   — 可勾选；对准可注入的失败点，不靠「演示看起来绿」
6. 小结 (Takeaways) + 系列位置 / 下一坑预告
参考 (References) — 可追溯官方文档与站内互链
```

**结构标杆：** 对照 `posts/durable_agent_execution.md` 第 1–6 节与参考，不要再以 MCP 篇当结构模板（MCP / 幂等篇只作语气与深度参考）。

### 3.1 第 4 节硬规则（连续性）

- **同一条业务线贯穿**：同一 `thread_id` / 业务主键（如退款单）从错法写到改法再到崩溃点  
- **先错后对**：读者必须能看出「错误长什么样」和「正确长什么样」  
- **解法可回溯**：每个修复点用表或旁注标明对应第 3 节哪一条（如「B / 3.1」）  
- **代码可对照**：BAD 与 GOOD 不是两套无关 demo；改动处要看得见  

### 3.2 Frontmatter 与 SEO

Frontmatter **必须**完整（缺任一字段不得进 `in_review`）：

```yaml
---
title: 中文标题（含失败面或机制名）
date: YYYY-MM-DD
tags: Tag1, Tag2, Tag3
description: 一两句说清失败面 + 结论（约 80～160 字，供卡片摘要 / meta / OG）
---
```

- **`description` 必填**：失败现象 + 可检索结论；避免口号、避免复述标题；约 80～160 汉字  
- **开头**：正文前 2～3 句结论先行，可与 description 呼应但不必逐字相同  
- **互链**：文内/文末至少链到 1 篇相关已发文（仓库相对路径 `posts/….md`）

---

## 4. 人设与语气 (Voice)

| 要 | 不要 |
| --- | --- |
| 「我们在生产里看到…」 | 「本文将介绍基本概念」 |
| 承认 tradeoff | 「用了 XX 就完美」 |
| 专名在前、通行译名在后 | 自造隐喻顶替专名 |
| 结论先行 | 长铺垫 |

---

## 5. 证据与诚实度 (Evidence)

- 案例可复现；不编造论文数据与官方原话  
- BAD 例子须「看起来合理」  
- 安全边界写清（如 annotations ≠ ACL）  

---

## 6. 四 Agent 流水线 (Pipeline)

| 角色 | 职责 | 读写 |
| --- | --- | --- |
| **选题 Scout** | 调研 Agent 领域新坑；写入/更新 `docs/blog-backlog.md` | 读写 backlog；只读 `posts/` |
| **写稿 Writer** | 取一条 `ready`；**按本文 §3 六段结构**写 `posts/*.md`（含强制 `description`）；本地成稿 | 读写 posts + backlog 状态 |
| **审阅 Reviewer** | 按 §7 验收；Approve = ship-ready；不够深则 request changes，不软通过 | 只读 posts；写 backlog 状态与审阅记录 |
| **协调 Coordinator** | 排期、拉通 Scout→Writer→Reviewer；**Reviewer Approve 后立即 push**（不等 Alice「批准 push」）；更新 backlog→`published`；群里留题名 + commit/PR | 编排；推送；不代替三人写稿/审稿 |

**节奏：** 自动写稿日 Mon/Wed/Fri（Asia/Shanghai）；周末留给 Alice **审已推送正文**，她可手工改再提交。  
**群聊：** 频道 `Blog Pipeline` = Scout + Writer + Reviewer + Coordinator。

**发布硬规则：** Reviewer 未批准 → Coordinator 不得 push。Approve 之后 → **立即** push，不二次等人批准。

---

## 7. 验收清单 (Acceptance)

- [ ] 踩坑/排查/对照，非概念贴  
- [ ] 架构师经验之谈 + 具体失败案例  
- [ ] **结构齐全**：现象 → 根因 → 机制/解法要点 → 同一案例错对 → 发版清单 → 小结 + 参考  
- [ ] **案例连续**：第 4 节同一业务线；先错后对；修复点回扣第 3 节解法  
- [ ] frontmatter 齐全：`title` / `date` / `tags` / **`description`**；路径在 `posts/`  
- [ ] `description` 含失败面 + 结论（非口号、非复述标题）  
- [ ] 开头 2～3 句可当 snippet；标题含可搜失败面/机制名  
- [ ] 至少 1 条系列/相关已发文互链  
- [ ] 含可勾选发版清单（对准可注入失败点）  
- [ ] 规范专名；引用可追溯  
- [ ] 对应 backlog 条目已从 `ready` 推进  
- [ ] Approve = ship-ready；通过后 Coordinator 立即 push  

---

## 8. 发布流程 (Publish)

1. Writer 本地成稿于 WSL `/home/alice/workspace/homepage`（或流水线约定路径）  
2. Reviewer 通过（Approve = ship-ready）  
3. Coordinator **立即** commit/push 到 `hanalice/hanalice` `main`  
4. `blog-sync` / Pages Action 更新站点；backlog 标 `published`  
5. Alice 周末等人审已发文；有问题再手工改提交  
6. 不提交 `.cursor/`  

---

## 9. 文档关系

| 文档 | 管什么 |
| --- | --- |
| 本文 | 写什么、怎么写、流水线、验收 |
| `docs/blog-backlog.md` | **滚动选题**（持续变化） |
| `github_profile_engineering.md` | 仓库/Actions/用语 §8 |
| `posts/durable_agent_execution.md` | **结构标杆** |
