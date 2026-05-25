# ADR 0001: 确立 Antigravity Harness (AI 托管) 工程规范

## 状态 (Status)
已接受 (Accepted) - 2026-05-01

## 背景 (Context)
当前的 GitHub Profile README 项目采用原生 Markdown 和 GitHub Actions 搭建，目标是“极简、原生、零成本维护”。随着架构设计逐渐完善，我们期望后续的功能迭代与日常维护能够完全交由 AI Agent (Antigravity) 负责执行。为了保证 AI 能够安全、可靠地修改代码和架构，并且不破坏现有功能的稳定性，我们需要为它设定极其严格的工程上下文、约束条件和知识记忆边界。

## 决策 (Decision)
我们决定将项目正式升级为兼容 Antigravity Harness 要求的工业级流水线，并在核心规范文档 `docs/skills/github_profile_engineering.md` 中固化以下关键原则：

1. **Prompt as Code (规范先行)**：AI 在动手修改代码或增加新特性前，必须先更新工程规范，使得一切思考显式化，方便审核与回溯。
2. **决策与知识持久化**：引入 `docs/ADR/` 记录架构级决策，引入 `docs/knowledge/` 记录所有的故障排错指南，防止 AI “失忆”和“重复犯错”。
3. **技术边界与防卫性编程**：
    - **逻辑解耦**：脚本必须遵循“纯函数 + 单向数据流”设计，核心 I/O 必须被剥离出来。
    - **安全解析**：采用稳定统一的 AST (抽象语法树) 处理 Markdown，彻底抛弃脆弱的 Regex 正则提取方式。
    - **依赖稳定**：依赖严格锁定 (Dependency Pinning) 以及零外部依赖倾向 (Zero-Dependency)，将环境引发的变数降至最低。
    - **安全提权**：GitHub Actions 强制遵守最小权限原则 (Least Privilege)，禁用默认全局权限。
    - **自诊监控**：在 README 代码的注释区域植入供 AI 自检的“隐藏健康看板”。

## 后果 (Consequences)
- **正面影响**：AI 修改代码时将有清晰明确的“宪法”可依。即使项目沉寂半年后再次唤醒 AI 进行开发，AI 也能瞬间通过读取 ADR 和工程规范文档恢复上下文，实现 100% 工业级的代码稳定性。
- **负面影响**：初期开发门槛有所提升，每次变更需要严格履行修改文档的流程，不能再进行“随意打补丁”式的快捷开发。
