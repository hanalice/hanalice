# Skill: GitHub Profile 个人门户工程规范

## 1. 背景与核心愿景 (Context & Vision)
打造一个以 GitHub Profile 为核心的“个人主页”。它既是一个名片，也是一个轻量级的博文发布站。
*   **设计原则：** 
    *   Apple 极简主义设计，浅色系，符合 Web 无障碍标准（Accessibility）。
    *   不要有深色系兼容明显问题。
    *   保持布局的极简。
*   **趣味性：** 引入每日自动轮换的带微动画的像素小人（Pixel Mascot）。
*   **工程性：** 100% GitHub 原生，零成本运维，数据驱动 README。
*   **不做的 (Out of Scope)**
    *   **不使用 GitHub Pages：** 保持 GitHub 原生环境，不引入前端框架。
    *   **不引入外部云服务：** 拒绝付费或需要维护的第三方数据库/服务器。
    *   **不处理 RSS：** 暂不生成订阅源。 


---

## 2. 仓库目录结构 (Directory Structure)
为了保证工程的整洁与可维护性，仓库必须遵循以下目录规范：
```text
/
├── README.template.md       # 主页真实数据源模板（占位符设计）
├── README.md                # 自动生成的个人门户主页 (勿手动修改)
├── posts/                   # 存放博文 Markdown 文件
├── assets/                  # 静态资源
│   ├── mascots/             # 像素小人图片库 (固定10个小人)
│   │   ├── 01.gif ... 10.gif
│   │   └── default_mascot.gif # 兜底小人（错误时默认显示）
├── scripts/                 # 自动化运维脚本 (Python/Node.js)
│   └── sync.py              # 同步博文与更新小人的核心逻辑
├── docs/                    # 项目文档
│   ├── ADR/                 # 架构决策记录 (Architecture Decision Records)
│   ├── knowledge/           # 错误知识库与踩坑指南
│   └── skills/              # 工程规范与 Skill 定义 (Prompt as Code)
├── .github/
│   ├── dependabot.yml       # 依赖自动更新配置
│   └── workflows/           # GitHub Actions 自动化流水线
└── Makefile / package.json  # 提供本地开发预览指令
```

---

## 3. 页面结构规范 (Layout)
主页 README 必须严格遵守“三段式”结构：
1.  **Header (自我介绍区)：** 极简 Banner + 每日像素小人 + 核心一句话简介。
2.  **Middle (能力背书区)：** 
    *   **核心项目：** 以 Case Study 形式展示 3 个核心项目，支持 YouTube/文章外链。
3.  **Footer (博文流区)：** 
    *   **Latest Stream：** 自动同步 `/posts` 目录下的博文列表。**使用分页/截断逻辑，主页仅渲染最新 10 篇文章。**
    *   **归档入口：** 提供一个 `[查看所有文章 (Archive)]` 的链接，方便查阅历史博文。
    *   **分类导航：** 自动生成的标签（Tags）分类云，方便快速搜索。
    *   **访客统计：** 底部嵌入极简 Visitor Badge。

---

## 4. 技术架构与自动化 (Technical & Automation)
### 4.1 内容管理 (CMS)
*   **真实数据源 (Single Source of Truth)：** 以 `README.template.md` 为核心模板，通过占位符注入动态内容并生成 `README.md`。禁止直接手动修改 `README.md` 以防冲突。
*   **博文存储：** 全 Markdown 格式，存放于 `/posts/*.md`。
*   **静态资源：** 存放于 `/assets/`，包含像素小人库和配图。

### 4.2 自动化流水线 (GitHub Actions)
*   **Blog Sync Action (每日 & Push 触发)：**
    *   **博文列表：** 解析博文日期和标签，替换 `README.template.md` 中的博文区块。**必须具备 Schema 校验能力**，遇到格式破损博文自动跳过并记录 Warning，不阻断正常流程。
    *   **标签生成：** 维护模板中的分类索引。
    *   **小人轮换：** 不覆盖修改图片文件，而是修改模板中的图片链接，使其在 10 个固定小人中轮换，避免 Git 历史膨胀。
*   **Image Compression Action (Push 触发)：**
    *   自动对 `assets/` 文件夹下新增的图片进行无损压缩，并自动 Commit 回仓库。**必须配置 `[skip ci]` 或特定路径过滤，避免触发死循环。**
*   **Link Checker Action (每月触发)：**
    *   检测所有外链有效性，若出现 404 则自动创建 Issue 提醒。
*   **故障通知机制：**
    *   核心 Action 运行失败时，自动发送邮件到指定邮箱，确保第一时间获悉并修复。
*   **健康度监控看板：**
    *   在主页源码的注释区域生成一个对用户不可见、但对 AI Agent 可见的健康度看板（例如 `<!-- STATUS: HEALTHY, LAST_SYNC: 2026-05-01 -->`），用于辅助诊断。

---

## 5. 运维与性能规范 (Ops & Performance)
*   **存储与 Git 历史：** 严格遵循 GitHub 免费额度，大小控制在 1GB 以内。**禁止 Action 频繁 Commit 二进制文件**，防止仓库无限膨胀变大。
*   **依赖更新：** 配置 `.github/dependabot.yml`，每月自动检查 Actions 版本及 Python/Node 依赖的版本并提出 PR，做到“零维护”。
*   **网络：** 图片利用 GitHub 官方 Camo 代理提升国内访问稳定性。
*   **统计：** 使用 HITS 或 Visitor Badge 统计流量，不注册账号，极简引入。
*   **社交分享：** 设置 `social-preview.png` 优化在 LinkedIn/Twitter 的预览效果。

---

## 6. 开发与测试规范 (Development & Testing)
*   **本地预览环境：** 必须提供轻量级的本地开发调试闭环。通过简单指令（如 `make preview` 或 `npm run dev`）在本地基于 `README.template.md` 快速生成并预览效果。
*   **缺省回退 (Fallback)：** 确保任何动态组件或服务失败时有兜底方案（例如小人挂掉时默认显示 `default_mascot.gif`），保持主页不破窗。

---

## 7. Antigravity 持续迭代规范 (Antigravity Iteration)
为确保 AI Agent (Antigravity) 能够安全、持续地接管并迭代此流水线，必须遵循以下工业级工程原则：
*   **Prompt as Code (规范先行)：** 任何新特性的增加或重大修改，**必须首先更新此工程规范文档**，通过审查后再去修改实际代码。
*   **问题与决策持久化：** 
    *   每次架构设计变更，必须在 `docs/ADR/` 下生成架构决策记录文档（如 `0001-xxx.md`）。
    *   遇到的核心错误或故障，必须将其现象、原因和解决防范沉淀到 `docs/knowledge/troubleshooting.md`，充当 AI 的本地记忆库。
*   **工业级脚本开发准则：**
    *   **架构与逻辑：** 脚本必须严格遵循 **“纯函数 + 单向数据流”** 的设计。提取、渲染和 I/O 操作必须解耦分离，并提供简单的本地测试脚手架验证逻辑。
    *   **解析安全：** 严禁使用脆弱的正则表达式去提取大段 Markdown 结构。必须采用统一的 AST (抽象语法树) 方案以提升鲁棒性。
    *   **低心智负担与锁定：** 倾向使用 Zero-Dependency (零第三方依赖) 方案（优先使用标准库）。若必须引入第三方库，必须严格锁定依赖的版本号（Dependency Pinning），防止由于破坏性更新导致流水线崩溃。

---

## 8. 安全与未来扩展 (Security & Scalability)
*   **最小权限原则 (Least Privilege)：** 所有 GitHub Actions 文件必须显式声明所需的最小 `permissions`（如只读、只写 issue 等），严禁授予默认全局权限。
*   **Secrets：** 所有未来涉及 API 的 Token 必须存放在 GitHub Secrets 中。
*   **双站并行（预留）：** 结构上支持未来一键部署至 GitHub Pages 变成动态 Web App。
