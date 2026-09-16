# 故障排查知识库 (Troubleshooting Knowledge Base)

本知识库用于记录项目自动化流水线在运行和迭代过程中遇到的所有典型故障、原因分析及解决方案。
**重要提示：每次发生导致流水线崩溃或页面破损的核心故障并完成修复后，AI Agent (Antigravity) 必须更新此文档。**

---

## 案例 1：Git 历史膨胀导致 Action 运行变慢或仓库过大 (预防案例)

*   **现象 (Symptom)**：每次触发自动更新任务，脚本都会覆盖生成新的二进制图片并 commit，导致 `.git` 文件夹体积日积月累无限增大。
*   **根本原因 (Root Cause)**：自动化流水线在未做控制的情况下高频提交二进制文件更改。
*   **解决方案 (Solution)**：
    1.  放弃修改物理文件，改为通过占位符修改 `README.md` 中指向 10 个固定静态小人图片的链接。
    2.  如果涉及图片压缩的 Action 操作，在 commit 时必须添加 `[skip ci]` tag，否则 Commit 行为会二次触发 Push 流水线，陷入死循环。
*   **预防与规范**：已纳入 `github_profile_engineering.md` 的运维规范，严禁脚本高频覆写二进制文件。

---

## 案例 2：文章页导航与正文左右对不齐

*   **现象 (Symptom)**：单篇博文页上，「hanalice」比正文更靠右；右侧目录超出导航「GitHub」的右缘。
*   **根本原因 (Root Cause)**：导航 / 页脚仍用 `--max: 980px`，带目录的 `.site-main--with-toc` 却是 `1180px`，居中后左右各偏约 100px。
*   **解决方案 (Solution)**：有目录的文章给 `body` 加上 `has-toc-layout`，让 `.site-nav`、`.site-main--with-toc`、`.site-footer` 共用 `--max-with-toc`。
*   **预防与规范**：加宽正文容器时，同步加宽同一页的 nav / footer，或抽成同一个 max-width 变量。

---

## 案例 3：`.gitignore` 写了 `public/`，git log / status 仍出现 public 改动

*   **现象 (Symptom)**：`.gitignore` 已包含 `public/`，但 `git status` 仍列出 `public/**`，`git log -- public` 也能看到历史提交。
*   **根本原因 (Root Cause)**：gitignore 只阻止**未跟踪**文件被加入；已经 commit 过的文件会继续被跟踪。历史提交也不会被 gitignore 改写。
*   **解决方案 (Solution)**：`git rm -r --cached public/` 从索引移除（保留工作区文件）。Pages 改由 `pages.yml` 在 CI 里跑 `sync.py` 再上传 artifact，不再把 `public/` commit 回仓库。
*   **预防与规范**：生成产物进 `.gitignore` 的同时，必须从索引撤跟踪，并改掉 `git add public/` 的流水线。不要用历史改写去“擦掉 git log”，除非明确要求 force-push。

---

> **给 AI 的提示 (Note for Antigravity)**: 
> 任何新的未知故障处理完毕后，请按照上述 `现象、根本原因、解决方案、预防` 的格式，增补到本文件底部。
