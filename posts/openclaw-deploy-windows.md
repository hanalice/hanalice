---
title: Windows 环境部署 OpenClaw + Ollama 完整指南
date: 2026-04-15
tags: OpenClaw, Ollama, WSL2
---

本文档总结了在 Windows 11 下通过 WSL2 部署 OpenClaw，并调用本地 Ollama 模型的全过程，包括所有遇到问题的解决方案。

## 目录
1. [环境准备](#1-环境准备)
2. [安装 Ollama（Windows 端）](#2-安装-ollamawindows-端)
3. [安装 Docker Desktop（可选但推荐）](#3-安装-docker-desktop可选但推荐)
4. [安装 OpenClaw（WSL 端）](#4-安装-openclawwsl-端)
5. [网络打通：WSL 访问 Windows Ollama](#5-网络打通wsl-访问-windows-ollama)
6. [配置 OpenClaw](#6-配置-openclaw)
7. [启动与测试](#7-启动与测试)
8. [踩坑与解决](#8-踩坑与解决)
9. [性能优化建议](#9-性能优化建议)
10. [最终配置参考](#10-最终配置参考)

---

## 1. 环境准备

### 1.1 开启 WSL2 并安装 Ubuntu
在 Windows 端运行以下命令以开启并安装 WSL 容器环境：

```powershell
# 以管理员身份打开 PowerShell
wsl --install
```

> [!NOTE]
> 安装完成后请重启电脑。您也可以从 Microsoft Store 安装所需的 Ubuntu 22.04 或 24.04 镜像。

### 1.2 安装 Node.js（使用 nvm）
```bash
# 在 WSL Ubuntu 终端中安装 nvm 引擎
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# 重新打开终端并安装 Node.js 22 LTS
nvm install 22
nvm use 22
node --version   # 应显示 v22.x
```

### 1.3 安装必要工具
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install curl git -y
```

---

## 2. 安装 Ollama（Windows 端）

### 2.1 下载安装
- 访问 [ollama.com](https://ollama.com) 下载并运行 Windows 安装包。
- 安装后启动 Ollama，Windows 系统托盘中应出现 Ollama 的标志性小图标。

### 2.2 配置监听地址（关键步骤）
Ollama 默认只监听 `127.0.0.1`，WSL 将无法直接进行跨局域网调用。需将监听变更为所有网络接口：

1. **退出 Ollama**：在系统右下角托盘处右键 Ollama 图标并选择 **Quit**。
2. **添加系统环境变量**：
   - 打开 Windows 控制面板，搜索并进入“编辑系统环境变量”或“环境变量”。
   - 在“系统变量”栏下点击“新建”：
     - **变量名**：`OLLAMA_HOST`
     - **变量值**：`0.0.0.0:11434`
3. **重新启动 Ollama**。

### 2.3 放行防火墙
**很多文章都要求放行防火墙，根据我的测试，以下防火墙策略验证是不需要的。**
```powershell
# 以管理员身份运行 PowerShell 放行对应端口
netsh advfirewall firewall add rule name="Ollama" dir=in action=allow protocol=TCP localport=11434
```

### 2.4 下载模型
```powershell
# 在 Windows PowerShell 中拉取适用模型
ollama pull qwen2.5:7b   # 7B 精准度模型（运行需要 8GB+ 内存空间）
ollama pull qwen2.5:3b   # 3B 实用模型（推荐，兼备效率与速度）
ollama pull llama3.2:3b  # 备选通用语言模型
```

### 2.5 验证安装
```powershell
ollama list
# 正常应显示您已成功下载的所有模型列表
```

---

## 3. 安装 Docker Desktop（可选但推荐）

### 3.1 下载安装
- 访问 [docker.com](https://docker.com) 下载 Docker Desktop for Windows。
- 安装并保持后台开启状态。

### 3.2 配置 WSL 集成（解决网络问题）
1. 打开 Docker Desktop Settings。
2. 进入 **General** 选项卡，确认勾选以下配置：
   - [x] Use the WSL 2 based engine
   - [x] Add the `.docker.internal` names to the host's `/etc/hosts` file
3. 进入 **Resources** → **WSL Integration**，确保您的 Ubuntu 发行版启用状态被激活。
4. 点击 **Apply & Restart** 保存生效。

### 3.3 验证
```bash
# 在 WSL 终端内测试访问 Windows Host 资源
curl http://host.docker.internal:11434/api/tags
# 应正确返回获取的模型列表 JSON 结构
```

---

## 4. 安装 OpenClaw（WSL 端）

### 4.1 一键安装
```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

### 4.2 验证安装
```bash
openclaw --version
# 应显示版本号如 2026.3.24
```

### 4.3 创建配置目录
```bash
mkdir -p ~/.openclaw/logs
```

---

## 5. 网络打通：WSL 访问 Windows Ollama

WSL2 默认使用 NAT 网络拓扑，无法直接使用 localhost 访问 Windows 服务。以下为您提供三种解决方案：

### 5.1 方案一：使用 host.docker.internal（强烈推荐）
```bash
# 验证网络通道连通性
curl http://host.docker.internal:11434/api/tags
```
- **优点**：解析地址固定，不因系统重启而频繁变动。
- **前提**：已安装并正确配置了 Docker Desktop（见第 3 节）。

### 5.2 方案二：使用 WSL 默认网关 IP
```bash
# 自动抓取获取的主机网关 IP
ip route | grep default | awk '{print $3}'
# 假设获取到的 IP 为 172.21.112.1，进行连接测试
curl http://172.21.112.1:11434/api/tags
```
- **缺点**：该 IP 在 WSL 重启或系统宿主机重启后可能发生漂移变化。

### 5.3 方案三：启用 WSL 镜像网络模式（Win11 22H2+）
在 Windows 主机下创建/编辑 `C:\Users\<您的用户名>\.wslconfig` 文件：

```ini
[wsl2]
networkingMode=mirrored
memory=8GB
processors=4
```
在 PowerShell 中运行 `wsl --shutdown` 重启 WSL 后，即可共享本地环回口网络。在 WSL 终端中直接运行：
```bash
curl http://localhost:11434/api/tags
```

---

## 6. 配置 OpenClaw

### 6.1 编辑配置文件
```bash
nano ~/.openclaw/openclaw.json
```

### 6.2 最小配置模板（使用 OpenAI 兼容模式 - 推荐）
```json
{
  "gateway": {
    "mode": "local",
    "port": 18789,
    "bind": "loopback",
    "auth": {
      "mode": "token",
      "token": "your-secret-token-here"
    }
  },
  "models": {
    "mode": "merge",
    "providers": {
      "ollama": {
        "baseUrl": "http://host.docker.internal:11435/v1",
        "apiKey": "ollama",
        "api": "openai-completions",
        "models": [
          {
            "id": "qwen2.5:3b",
            "name": "Qwen2.5 3B (Local)",
            "reasoning": false,
            "input": ["text"],
            "contextWindow": 8192,
            "maxTokens": 4096,
            "cost": {
              "input": 0,
              "output": 0,
              "cacheRead": 0,
              "cacheWrite": 0
            }
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "ollama/qwen2.5:3b"
      },
      "timeoutSeconds": 600
    }
  }
}
```

### 6.3 配置文件说明

| 字段 | 说明 | 推荐值 |
| :--- | :--- | :--- |
| `baseUrl` | Ollama 服务 API 入口 | `http://host.docker.internal:11435/v1` |
| `api` | 调用 API 类型 | `openai-completions`（高稳定性）或 `ollama`（原生接口） |
| `contextWindow` | 上下文关联窗口大小 | `4096` - `8192`（过大容易拖慢计算与推理速度） |
| `timeoutSeconds` | 请求连接超时时间 | `600`（10分钟，避免复杂逻辑请求提前中断） |

---

## 7. 启动与测试

### 7.1 启动网关
```bash
# 启动 OpenClaw 后台网关服务
openclaw gateway start

# 检查网关服务当前的后台存活状态
openclaw gateway status

# 查看详细服务状态汇总
openclaw status
```

### 7.2 测试对话
```bash
# 发送单次调试消息进行测试
openclaw agent --agent main --message "Hello, introduce yourself"

# 调出极简终端交互式面板 (Text User Interface)
openclaw tui
```

### 7.3 验证模型调用
```bash
# 前台实时追踪服务生成日志
openclaw logs --follow

# 也可以临时停止后台服务，改在前台以 debug 模式启动方便排错：
openclaw gateway stop
openclaw gateway --verbose
```

---

## 8. 踩坑与解决

### 8.1 端口 11434 被占用
- **现象**：`netstat -ano | findstr :11434` 返回多个 PID 占用导致 Ollama 无法提供服务。
- **解决**：改换其他空闲端口（例如 `11435`）：
  ```powershell
  # 修改环境变量，重新分配端口变量
  # OLLAMA_HOST=0.0.0.0:11435
  # 退出并重启 Ollama 服务
  # 并在 OpenClaw 的 JSON 配置文件中更改对应的服务接口端口号
  ```

### 8.2 WSL curl 通但 OpenClaw 报 `fetch failed`
- **原因**：调用的后端 API 接口路径规则不匹配。
- **解决**：
  1. 保证使用 OpenAI 兼容层模式规范（即配置 `api: "openai-completions"`）。
  2. 保证配置的 `baseUrl` 严格以 `/v1` 结尾。

### 8.3 `host.docker.internal` 域名无法解析
- **原因**：Docker Desktop 的网络映射配置被重置。
- **解决**：
  1. 打开 Docker Desktop Settings 面板。
  2. 依次选择 **General** → 确保勾选 **"Add the *.docker.internal names to the host's /etc/hosts file"**。
  3. 保存并点击 **Apply & Restart**。

### 8.4 网关启动失败：`gateway mode not set`
- **现象**：提示 `Gateway start blocked: set gateway.mode=local`。
- **解决**：确保在配置文件最前方的 `gateway` 节点内已显示声明了其运行模式及端口：
  ```json
  "gateway": {
    "mode": "local",
    "port": 18789
  }
  ```

### 8.5 curl ollama chat api 可以正常返回，但是openclaw Agent 提示卡死连接超时
- **原因**：物理 CPU 算力局限（例如强行在低性能 CPU 下调度 7B 大模型且上下文关联较多导致推理时间过长）。
  
- **解决**：
  ```bash
  # 1. 换用体量更小更迅速的模型
  ollama pull qwen2.5:3b

  # 2. 定期清理庞大的本地会话历史缓存
  rm -rf ~/.openclaw/agents/main/sessions/*.jsonl*

  # 3. 适当放宽连接超时限制
  # 建议在 JSON 的 agents.defaults 中加入 "timeoutSeconds": 1800 以防提前挂断

  # 4. 最大输出Token 减少配置
  {...,"maxTokens": 2048,}

  # 5. 终极大法，换在线模型
  在openclaw.json中修改models.providers[].<在线模型>， agents.defaults.model.primary: <在线模型>
  ```

### 8.6 会话文件锁冲突报错
- **现象**：终端抛出类似 `session file locked` 异常。
- **解决**：
  ```bash
  rm ~/.openclaw/agents/main/sessions/*.lock
  ```

### 8.7 网关抛出认证错误
- **现象**：提示 `gateway url override requires explicit credentials`。
- **解决**：
  - 在配置文件内设置安全模式为 `auth.mode: "none"`（仅建议在局域网/测试环境使用）。
  - 或者在运行命令时手动携带身份令牌 `--token your-token`。

### 8.8 curl 直接调用快，但使用 OpenClaw 慢
- **原因**：OpenClaw 保持了连贯记忆，会在每次推理时将所有的会话历史上下文打包装载发送，导致数据负担递增。
- **解决**：
  - 定期清空历史记录。
  - 调小配置文件内的 `contextWindow` 缓存。
  - 更换为在本地具备更高推理吞吐量的模型。

---

## 9. 性能优化建议

### 9.1 选择合适模型

| 模型 | 大小 | 速度 | 内存需求 | 推荐场景 |
| :--- | :--- | :--- | :--- | :--- |
| `qwen2.5:3b` | 3B | 极快 | 4GB+ | 日常普通聊天、轻量测试 |
| `qwen2.5:7b` | 7B | 较慢 | 8GB+ | 复杂代码、长文本逻辑推理（推荐 GPU 驱动） |
| `llama3.2:3b` | 3B | 快 | 4GB+ | 英文会话与简单日常通用任务 |

### 9.2 启用 GPU 加速（NVIDIA 设备）
```powershell
# 1. 宿主端更新官方最新的 NVIDIA 驱动并部署好 CUDA 环境
# 2. 重启一次 Windows Ollama，应用会自动识别并加载底层硬件显卡加速
ollama ps
# 确认输出的 PROCESSOR 一栏中显示为 GPU 代替 CPU 即可
```

### 9.3 调整 Ollama 上下文窗口
```bash
# 编写自定义 Modelfile 手动限制上下文缓存，减少运算时负担
ollama create my-qwen -f - <<EOF
FROM qwen2.5:3b
PARAMETER num_ctx 4096
EOF

# 运行自定义封装的小模型
ollama run my-qwen
```

### 9.4 OpenClaw 性能调优
可在 `openclaw.json` 中配置以对内存及计算资源进行合理控制：
```json
{
  "agents": {
    "defaults": {
      "maxConcurrent": 2,           // 限制并发运行的进程数
      "timeoutSeconds": 600,        // 配置超时时间
      "compaction": {
        "mode": "safeguard",
        "maxTokens": 4000           // 自动对超过该长度的会话历史进行轻量化压缩
      }
    }
  }
}
```

---

## 10. 最终配置参考

### 10.1 完整配置文件 `~/.openclaw/openclaw.json`
```json
{
  "gateway": {
    "mode": "local",
    "port": 18789,
    "bind": "loopback",
    "auth": {
      "mode": "token",
      "token": "your-secure-token-here"
    }
  },
  "models": {
    "mode": "merge",
    "providers": {
      "ollama": {
        "baseUrl": "http://host.docker.internal:11435/v1",
        "apiKey": "ollama",
        "api": "openai-completions",
        "models": [
          {
            "id": "qwen2.5:3b",
            "name": "Qwen2.5 3B",
            "reasoning": false,
            "input": ["text"],
            "contextWindow": 8192,
            "maxTokens": 4096,
            "cost": {
              "input": 0,
              "output": 0,
              "cacheRead": 0,
              "cacheWrite": 0
            }
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "ollama/qwen2.5:3b"
      },
      "timeoutSeconds": 600,
      "maxConcurrent": 2,
      "compaction": {
        "mode": "safeguard",
        "maxTokens": 4000
      }
    }
  }
}
```

### 10.2 快速测试命令
```bash
# 执行完整运行状态自检
openclaw doctor

# 重启后台服务网关
openclaw gateway restart

# 手动发送一条调试消息
openclaw agent --message "Hello" --agent main

# 打印输出最新的 50 条服务运行日志
openclaw logs --tail 50

# 唤醒 OpenClaw 自带的 WebDashboard 浏览器端控制面板
openclaw dashboard
# 使用浏览器打开 http://127.0.0.1:18789
```

### 10.3 故障排查流程
- **检查网关状态**：`openclaw gateway status`
- **前台启动服务追踪日志**：`openclaw gateway --verbose`
- **测试底层连接是否畅通**：`curl http://host.docker.internal:11435/api/tags`
- **校验您的 JSON 配置文件格式是否损坏**：`python3 -m json.tool ~/.openclaw/openclaw.json`
- **读取系统服务运行日志**：`journalctl --user -u openclaw-gateway -f`

---

## 附录：常用命令速查

| 操作 | 命令 |
| :--- | :--- |
| **启动网关** | `openclaw gateway start` |
| **停止网关** | `openclaw gateway stop` |
| **重启网关** | `openclaw gateway restart` |
| **查看服务综合状态** | `openclaw status` |
| **发送终端单次消息** | `openclaw agent --message "text"` |
| **进入 TUI 交互控制台** | `openclaw tui` |
| **打开 Dashboard 面板** | `openclaw dashboard` |
| **追踪获取尾部日志** | `openclaw logs --tail 50` |
| **诊断与一键配置修复** | `openclaw doctor --repair` |

---

- **文档版本**：`1.0`
- **最后更新**：`2026-05-25`
- **适用版本**：`OpenClaw 2026.3.24+`, `Ollama 0.1.29+`, `Windows 11 + WSL2`