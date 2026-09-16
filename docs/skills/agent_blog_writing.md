# Skill: Agent 技术博文写作规范

> 适用于 `hanalice/hanalice` 仓库 `posts/` 下的技术博文。  
> 标杆范文：`posts/mcp_tool_design_valid_but_wrong.md`。  
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
- 审阅 Agent：对照本文 §3–§7 与验收清单，通过则 `published`（允许推送），否则回 `writing` 并写修改意见  

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

默认六段（可按坑调整，但不得缺「现象 / 根因 / 可落地」）：

```text
1. 问题现象 (Problem Symptoms) — 2～3 短案例 A/B/C
2. 根因分析 (Root Cause Analysis) — 可命名框架 + 表
3. 机制 / 协议要点 — 只用规范专名；比喻不作术语
4. 设计演进或 BAD/GOOD
5. 发版前清单
6. 小结 + 下一坑预告
参考 (References)
```

Frontmatter **必须**完整（缺任一字段不得进 `in_review`）：

```yaml
---
title: 中文标题（含失败面或机制名）
date: YYYY-MM-DD
tags: Tag1, Tag2, Tag3
description: 一两句说清失败面 + 结论（约 80～160 字，供卡片摘要 / meta / OG）
---
```

### 3.1 `description` 强制要求（P1 / SEO 文章层）

- **必填**：不得省略；不得指望 sync 从正文「碰巧截对」  
- **内容**：失败现象 + 可检索结论；避免口号、避免复述标题  
- **长度**：约 80～160 汉字（或等价信息密度）；首页卡片会截断展示  
- **样板**：`posts/mcp_tool_design_valid_but_wrong.md`、`posts/agent_write_idempotency.md`  
- **开头**：正文前 2～3 句仍须结论先行，可与 description 呼应但不必逐字相同  
- **互链**：文内/文末至少链到 1 篇相关已发文（仓库相对路径 `posts/….md` 即可，sync 会改成 Pages `.html`）

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
| **写稿 Writer** | 取一条 `ready`；按本文写 `posts/*.md`（含强制 `description`）；本地成稿 | 读写 posts + backlog 状态 |
| **审阅 Reviewer** | 按 §7 验收；给修改意见或批准发布 | 只读 posts；写 backlog 状态与审阅记录 |
| **协调 Coordinator** | 排期、拉通 Scout→Writer→Reviewer；**仅审过才 push**；更新 backlog→`published` | 编排；推送；不代替三人写稿/审稿 |

用户 Alice **不必**日常进群：默认由 Coordinator 闭环。她只在改优先级、否决推送、或改规范时介入。

**群聊：** 频道 `Blog Pipeline` = Scout + Writer + Reviewer + Coordinator（同室同步，避免私聊扇出）。

**发布硬规则：** Reviewer 未批准 → Coordinator 不得 push。本地改完再一次推送（偏好）。

---

## 7. 验收清单 (Acceptance)

- [ ] 踩坑/排查/对照，非概念贴  
- [ ] 架构师经验之谈 + 具体失败案例  
- [ ] frontmatter 齐全：`title` / `date` / `tags` / **`description`**；路径在 `posts/`  
- [ ] `description` 含失败面 + 结论（非口号、非复述标题）  
- [ ] 开头 2～3 句可当 snippet；标题含可搜失败面/机制名  
- [ ] 至少 1 条系列/相关已发文互链  
- [ ] 含 BAD/GOOD 或 Vn 或清单  
- [ ] 规范专名；引用可追溯  
- [ ] 对应 backlog 条目已从 `ready` 推进  
- [ ] 审阅通过后再推送  

---

## 8. 发布流程 (Publish)

1. Writer 本地成稿于 WSL `/home/alice/workspace/homepage`  
2. Reviewer 通过  
3. 协调者一次 commit/push 到 `hanalice/hanalice` `main`  
4. `blog-sync` 更新 README；backlog 标 `published`  
5. 不提交 `.cursor/`  

---

## 9. 文档关系

| 文档 | 管什么 |
| --- | --- |
| 本文 | 写什么、怎么写、流水线、验收 |
| `docs/blog-backlog.md` | **滚动选题**（持续变化） |
| `github_profile_engineering.md` | 仓库/Actions/用语 §8 |
