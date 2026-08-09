---
title: pnpm 安装 rspack 原生 binding 缺失导致 build 失败
date: 2026-08-08
tags: pnpm, rspack, native-binding, WSL, optional-dependencies
---

### 问题描述

在 WSL（Ubuntu 24.04）环境下，使用 pnpm 在 monorepo 根目录执行 `pnpm install` 后，进入子包 `apps/1000` 执行 `npm run build:rspack`，报错如下：

```
Error: Cannot find native binding.
Cannot find module './rspack.linux-x64-gnu.node'
Cannot find module '@rspack/binding-linux-x64-gnu'
```

**项目结构：**

```
rolldown-benchmarks/               ← monorepo 根目录
├── pnpm-workspace.yaml            ← pnpm 工作区配置（此次修复的关键文件）
├── node_modules/                  ← 所有依赖集中安装于此
│   └── .pnpm/
│       └── @rspack+binding-linux-x64-gnu@2.1.7/  ← 问题包所在
├── apps/
│   ├── 1000/                      ← 触发问题的子包
│   │   ├── package.json
│   │   └── rspack.config.mjs
│   ├── 3000/
│   ├── 5000/
│   ├── 10000/
│   ├── rome/
│   └── three10x/
└── examples/
```

依赖统一由根目录 `pnpm install` 管理，各子包通过 workspace 协议共享 `node_modules`。错误发生在 `@rspack/binding@2.1.7` 尝试加载原生 `.node` 二进制文件时，Node.js 进程直接抛出异常退出。

---

### 问题定位

**定位过程：**

1. **确认依赖目录结构**：检查 `node_modules/.pnpm/` 下与 rspack binding 相关的包，发现 `@rspack+binding-linux-x64-gnu@2.1.7` 目录**存在**，说明 pnpm lockfile 中有该依赖记录。

2. **深入检查包内容**：进入 `@rspack+binding-linux-x64-gnu@2.1.7/node_modules/` 目录，发现该目录**完全为空**——只有目录骨架，没有任何实际文件，更没有 `rspack.linux-x64-gnu.node` 二进制文件。

3. **检查 pnpm store**：在全局 pnpm store（`~/.local/share/pnpm/store/v11`）中搜索所有 `.node` 文件，**结果为空**，证实该原生包从未被真正下载到本地。

4. **检查 pnpm-workspace.yaml 配置**：发现项目中没有配置 `supportedArchitectures`，而 `@rspack/binding` 的 `optionalDependencies` 中列出了多个平台的 binding 包（darwin、win32、linux 各架构），pnpm 在未明确指定目标平台时，对 optional 依赖的下载出现了遗漏。

**定位依据：**

- `.node` 文件是 Node.js 原生插件（由 Rust/C++ 编译的动态链接库），必须有实际的二进制文件才能被 `require()` 加载；
- pnpm 对 `optionalDependencies` 的处理存在已知 bug（详见 [npm/cli#4828](https://github.com/npm/cli/issues/4828)，该 issue 正是 rspack 错误信息中引用的来源）：在未配置 `supportedArchitectures` 时，包管理器可能仅写入目录结构而跳过实际包内容的下载；
- pnpm store 中无任何 `.node` 文件是关键证据，排除了"文件损坏"或"链接断开"等次要原因，直接指向"从未下载"。

**定位结果：**

> pnpm 未配置 `supportedArchitectures`，在 optional dependencies 处理路径上出现 bug，导致 `@rspack/binding-linux-x64-gnu` 的包内容（含 `.node` 二进制）始终未被下载，最终构建时找不到原生模块。

---

### 问题总结

**修复方式：** 在 `pnpm-workspace.yaml` 中添加 `supportedArchitectures` 配置，明确声明当前平台，再执行 `pnpm install`：

```yaml
supportedArchitectures:
  os:
    - linux
  cpu:
    - x64
  libc:
    - glibc
```

pnpm 据此补充下载了 `@rspack/binding-linux-x64-gnu@2.1.7`，`rspack.linux-x64-gnu.node` 文件就位后，构建恢复正常（`Rspack compiled in 428 ms`）。

**经验结论：**

| 结论 | 说明 |
|------|------|
| pnpm 的 optional 依赖并不总是可靠 | 对包含原生二进制的 optional 包，建议在 workspace 配置中显式声明目标平台 |
| 排查此类问题的关键步骤 | 先检查包目录是否为空 → 再检查 pnpm store 是否有对应文件 → 最后看配置是否指定了目标架构 |
| WSL 环境需额外注意 | WSL 的平台识别在某些 pnpm 版本中存在边界情况，`libc: glibc` 的显式声明尤为重要 |

---

### 延伸：同项目中其他原生包为何没有出问题

本项目中多个工具（esbuild、@swc/core、lightningcss、rolldown、rollup）同样使用 `optionalDependencies` 分发跨平台原生二进制，但构建均正常。其原因分三类情况：

#### 情况一：有 postinstall 兜底（esbuild、@swc/core）

`pnpm-workspace.yaml` 中通过 `allowBuilds` 显式允许这两个包运行安装脚本：

```yaml
allowBuilds:
  '@swc/core': true
  esbuild: true
```

这两个包在主包（非平台子包）中内置了 `postinstall` 脚本，脚本会**主动验证**平台对应的二进制是否存在，若缺失则重新触发下载。因此即使 pnpm 的 optional 依赖解析出现问题，postinstall 也能将其修复。

`@rspack/binding` 没有配置 `allowBuilds`，也没有 postinstall 脚本，完全依赖 pnpm 将 `@rspack/binding-linux-x64-gnu` 正确安装到位。一旦 pnpm 出错，没有任何兜底。

#### 情况二：纯 optional 依赖分发，但安装成功（lightningcss、rolldown、rollup）

经实际验证，这三个包**同样没有 postinstall 脚本**，也没有在 `allowBuilds` 中声明，与 rspack 的分发机制完全相同：

| 包 | postinstall | .node 文件 |
|----|-------------|------------|
| `lightningcss-linux-x64-gnu` | 无 | ✅ 存在 |
| `@rolldown/binding-linux-x64-gnu` | 无 | ✅ 存在 |
| `@rollup/rollup-linux-x64-gnu` | 无 | ✅ 存在 |
| `@rspack/binding-linux-x64-gnu@2.1.7` | 无 | ❌ 修复前为空 |

这三个包之所以正常，推测原因是：**它们的当前版本在更早的某次 `pnpm install` 中已被成功下载并写入 pnpm store**，后续 install 直接从 store 硬链接，不再走有 bug 的下载逻辑。

而 `@rspack/binding-linux-x64-gnu@2.1.7` 这个**具体版本**从未成功进入 store（可能是版本切换后首次安装时恰好触发了 pnpm 的 optional 依赖处理 bug），导致目录结构建好但内容为空，且后续 install 因目录已存在而跳过，问题持续保留。

#### 情况三：pnpm 安装失败后不完整清理（bug 的本质）

pnpm 在安装 optional 依赖时，若某个包下载失败（网络超时、版本冲突、平台判断出错等），**不会回滚已创建的目录结构**，而是留下一个"半成品"：

```
node_modules/.pnpm/@rspack+binding-linux-x64-gnu@2.1.7/
└── node_modules/          ← 目录存在
    └── @rspack/
        └── binding-linux-x64-gnu/   ← 目录存在，但无任何文件
```

下次执行 `pnpm install` 时，由于目录已存在且 lockfile 未变，pnpm 误判为"已安装"并跳过，导致问题持续，而不会自动修复。

配置 `supportedArchitectures` 后，pnpm 被迫重新评估平台 binding 包的安装状态，发现内容缺失，才触发了真正的下载补全。
