---
title: Dockerfile 快速上手：构建并运行你的第一个容器
date: 2017-07-18
tags: Docker, DevOps, Container, Tutorial
---

Docker 是现代开发中不可或缺的工具。通过 `Dockerfile`，我们可以将环境配置“代码化”，确保在任何地方运行的结果都是一致的。

本文将通过一个简单的例子，演示如何使用 Dockerfile 创建一个基于 Ubuntu 的 Apache Web 服务器。

### 1. 编写进阶版 Dockerfile

为了支持代码打包和生产环境的安全要求，我们将 Dockerfile 升级如下：

```dockerfile
# 使用官方轻量级镜像或指定版本
FROM ubuntu:20.04

# 设置环境变量（用于调试和排查问题）
ENV APP_VERSION=1.0.1
ENV APP_MD5=ce5ce0aed83e70ac2b009ae5894bdd2a

# 避免交互式安装时的提示
ENV DEBIAN_FRONTEND=noninteractive

# 安装 Apache
RUN apt-get update && \
    apt-get install -y apache2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# [关键步骤] 将本地代码打包到 Web 目录下
# 假设你的网页源码在本地 ./src 目录
COPY ./src /var/www/html/

# --- 安全加固 (Security) ---

# 1. 权限控制：修改 Web 目录所有者
RUN chown -R www-data:www-data /var/www/html

# 2. 最小权限原则：切换到非 root 用户运行
# 注意：在 80 端口运行时需要额外配置，通常生产环境会改用 8080
USER www-data

# 启动服务
CMD ["/usr/sbin/apache2ctl", "-D", "FOREGROUND"]
```

---

### 2. 核心功能详解

#### 2.1 代码打包 (COPY)
使用 `COPY ./src /var/www/html/` 指令，你可以将本地开发好的代码直接“打进”镜像。这样镜像分发到任何地方，都自带了代码。
*   **提示**：建议配合 `.dockerignore` 文件，排除掉 `.git`、`node_modules` 等无关的大文件，减小镜像体积。

#### 2.2 调试元数据 (ENV)
通过 `ENV` 注入 `APP_VERSION` 和 `APP_MD5`。
*   **实战技巧**：在容器运行后，你可以通过 `docker exec -it <container_id> env` 快速查看这些信息。如果线上环境出现“已知问题库”中的 Bug，你可以第一时间确认当前运行的是否为受影响的版本。

#### 2.3 安全策略 (Security)
*   **非 root 用户**：默认情况下容器以 root 运行，这存在安全隐患。使用 `USER www-data` 可以显著降低被攻击后的提权风险。
*   **Secrets 管理**：**切记不要将数据库密码等敏感信息写在 Dockerfile 的 ENV 中。** 应该在运行时通过 `docker run --env-file` 或 GitHub Secrets 等 CI/CD 工具注入环境变量。

---

### 3. 构建与运行

构建镜像：
```bash
docker build -t webserver:1.0.1 .
```

运行并传入环境变量（可选覆盖）：
```bash
docker run -d \
  -p 8080:80 \
  --name web-prod \
  -e DEBUG_MODE=true \
  webserver:1.0.1
```

---

### 总结

通过 `COPY` 实现持续集成，通过 `ENV` 实现可追踪性，通过 `USER` 实现安全加固。这套组合拳能让你的镜像更专业、更健壮。

