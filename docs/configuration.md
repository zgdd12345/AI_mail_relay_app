# 配置参考 | Configuration Reference

本文档详细说明 AI Mail Relay 应用程序的所有配置选项。

This document provides a comprehensive reference for all AI Mail Relay configuration options.

> 说明：自当前版本起仅支持 **API 模式** 获取 arXiv 论文，邮箱模式已移除，相关 IMAP 配置不再使用。

---

## 目录 | Table of Contents

- [配置概述](#配置概述)
- [arXiv 获取配置](#arxiv-获取配置)
- [邮箱配置（Email 模式）](#邮箱配置email-模式)
- [SMTP 发送配置](#smtp-发送配置)
- [过滤配置](#过滤配置)
- [LLM 配置](#llm-配置)
- [完整配置示例](#完整配置示例)

---

## 配置概述

### 配置方式 | Configuration Methods

所有配置通过**环境变量**或项目根目录的 `.env` 文件设置。

优先级：环境变量 > `.env` 文件 > 默认值

### 配置文件位置 | Configuration File Location

```
AI_mail_relay_app/
├── .env                 # 主配置文件
├── .env.example        # 配置模板（如果存在）
└── src/ai_mail_relay/
    └── config.py       # 配置定义和验证
```

### 基本语法 | Basic Syntax

```bash
# .env 文件格式
KEY=value
KEY="value with spaces"
KEY='single quoted value'

# 布尔值
ENABLED=true    # true, yes, on, 1
DISABLED=false  # false, no, off, 0

# 数字
PORT=587
TIMEOUT=30

# 列表（逗号分隔）
CATEGORIES=cs.AI, cs.LG, cs.CV
```

---

## arXiv 获取配置

### ARXIV_FETCH_MODE

**描述：** arXiv 论文获取模式（固定为 `api`）

**类型：** 字符串

**默认值：** `api`

**可选值：**
- `api` - 从 arXiv API 直接获取（唯一支持）

**示例：**
```bash
ARXIV_FETCH_MODE=api
```

**说明：**
- 邮箱模式已移除，IMAP 相关配置不会生效

---

### ARXIV_API_MAX_RESULTS

**描述：** API 模式下每个类别的最大获取结果数

**类型：** 整数

**默认值：** `200`

**范围：** >= 1

**示例：**
```bash
ARXIV_API_MAX_RESULTS=300
```

**说明：**
- 值越大，获取的论文越多，但请求时间越长
- arXiv API 有速率限制（每次请求间隔 3 秒）
- 建议值：100-500

---

## 邮箱配置（Email 模式）

仅在 `ARXIV_FETCH_MODE=email` 时需要配置。

### IMAP_HOST

**描述：** IMAP 服务器地址

**类型：** 字符串

**必需：** 是（Email 模式）

**示例：**
```bash
IMAP_HOST=imap.gmail.com
```

**常用值：**
- Gmail: `imap.gmail.com`
- Outlook: `outlook.office365.com`
- QQ Mail: `imap.qq.com`

---

### IMAP_PORT

**描述：** IMAP 服务器端口

**类型：** 整数

**默认值：** `993`

**示例：**
```bash
IMAP_PORT=993
```

**说明：**
- 993: IMAP over SSL（标准）
- 143: IMAP with STARTTLS

---

### IMAP_USER

**描述：** IMAP 登录用户名（通常是邮箱地址）

**类型：** 字符串

**必需：** 是（Email 模式）

**示例：**
```bash
IMAP_USER=your-email@gmail.com
```

---

### IMAP_PASSWORD

**描述：** IMAP 登录密码

**类型：** 字符串

**必需：** 是（Email 模式）

**示例：**
```bash
IMAP_PASSWORD=your-app-specific-password
```

**注意：**
- Gmail 需要使用应用专用密码
- 生成地址：https://myaccount.google.com/apppasswords
- 复制 16 位应用密码到 `.env` 时请去掉中间的空格，否则 IMAP 登录会返回 5.7.8 BadCredentials

---

### IMAP_FOLDER

**描述：** 要读取的 IMAP 文件夹

**类型：** 字符串

**默认值：** `INBOX`

**示例：**
```bash
IMAP_FOLDER=INBOX
```

---

### MAIL_SENDER_FILTER

**描述：** 发件人过滤条件

**类型：** 字符串

**默认值：** `no-reply@arxiv.org`

**示例：**
```bash
MAIL_SENDER_FILTER=no-reply@arxiv.org
```

---

### MAIL_SUBJECT_KEYWORDS

**描述：** 邮件主题关键词过滤（逗号分隔）

**类型：** 列表

**默认值：** `arXiv, Daily, digest`

**示例：**
```bash
MAIL_SUBJECT_KEYWORDS=arXiv, Daily, digest
```

---

## SMTP 发送配置

所有模式都需要配置 SMTP 用于发送摘要邮件。

### SMTP_HOST

**描述：** SMTP 服务器地址

**类型：** 字符串

**必需：** 是

**示例：**
```bash
SMTP_HOST=smtp.gmail.com
```

**常用值：**
- Gmail: `smtp.gmail.com`
- Outlook: `smtp.office365.com`
- QQ Mail: `smtp.qq.com`
- SendGrid: `smtp.sendgrid.net`
- Mailgun: `smtp.mailgun.org`

---

### SMTP_PORT

**描述：** SMTP 服务器端口

**类型：** 整数

**默认值：** `587`

**示例：**
```bash
SMTP_PORT=587
```

**常用端口：**
- `587`: SMTP with STARTTLS（推荐）
- `465`: SMTP over SSL
- `25`: 不加密 SMTP（不推荐，通常被封锁）

---

### SMTP_USER

**描述：** SMTP 登录用户名

**类型：** 字符串

**必需：** 是

**示例：**
```bash
SMTP_USER=your-email@gmail.com
```

---

### SMTP_PASSWORD

**描述：** SMTP 登录密码

**类型：** 字符串

**必需：** 是

**示例：**
```bash
SMTP_PASSWORD=your-app-specific-password
```

**注意：**
- Gmail 需要使用应用专用密码
- 生成地址：https://myaccount.google.com/apppasswords
- 复制 16 位应用密码到 `.env` 时请去掉中间的空格，否则 SMTP 登录会返回 5.7.8 BadCredentials

---

### SMTP_USE_TLS

**描述：** 是否使用 STARTTLS 加密

**类型：** 布尔值

**默认值：** `true`

**示例：**
```bash
SMTP_USE_TLS=true
```

**端口配置建议：**
```bash
# 端口 587 使用 STARTTLS
SMTP_PORT=587
SMTP_USE_TLS=true

# 端口 465 使用 SSL
SMTP_PORT=465
SMTP_USE_TLS=false
```

---

### SMTP_TIMEOUT

**描述：** SMTP 连接超时时间（秒）

**类型：** 整数

**默认值：** `30`

**范围：** > 0

**示例：**
```bash
SMTP_TIMEOUT=60
```

**说明：**
- 网络较慢时可增大此值
- 建议范围：10-60 秒
- **新增功能**（v1.1+）

---

### SMTP_RETRY_ATTEMPTS

**描述：** SMTP 连接失败重试次数

**类型：** 整数

**默认值：** `3`

**范围：** >= 0

**示例：**
```bash
SMTP_RETRY_ATTEMPTS=5
```

**说明：**
- 0 表示不重试
- 建议范围：2-5 次
- **新增功能**（v1.1+）

---

### SMTP_RETRY_BASE_DELAY

**描述：** 重试基础延迟时间（秒），使用指数退避

**类型：** 浮点数

**默认值：** `2.0`

**范围：** > 0

**示例：**
```bash
SMTP_RETRY_BASE_DELAY=3.0
```

**说明：**
- 实际延迟 = base_delay * (2 ^ attempt_number)
- 示例（base_delay=2.0）:
  - 第1次重试: 等待 2.0 秒
  - 第2次重试: 等待 4.0 秒
  - 第3次重试: 等待 8.0 秒
- **新增功能**（v1.1+）

---

### MAIL_FROM_ADDRESS

**描述：** 发件人邮箱地址

**类型：** 字符串

**必需：** 是

**示例：**
```bash
MAIL_FROM_ADDRESS=your-email@gmail.com
```

**说明：**
- 通常与 `SMTP_USER` 相同
- 某些 SMTP 服务器允许不同的发件人地址

---

### MAIL_TO_ADDRESS

**描述：** 收件人邮箱地址

**类型：** 字符串

**必需：** 是

**示例：**
```bash
MAIL_TO_ADDRESS=recipient@example.com
```

**说明：**
- 可以与发件人相同（发给自己）
- 支持单个收件人

---

## 过滤配置

### ARXIV_ALLOWED_CATEGORIES

**描述：** 允许的 arXiv 分类列表（逗号分隔）

**类型：** 列表

**默认值：** `cs.AI, cs.LG, cs.CV, cs.CL, cs.RO, cs.IR, stat.ML, eess.AS`

**示例：**
```bash
ARXIV_ALLOWED_CATEGORIES=cs.AI, cs.LG, cs.CV, cs.CL
```

**常用分类：**
- `cs.AI`: 人工智能
- `cs.LG`: 机器学习
- `cs.CV`: 计算机视觉
- `cs.CL`: 计算与语言（NLP）
- `cs.RO`: 机器人学
- `cs.IR`: 信息检索
- `stat.ML`: 统计学习
- `eess.AS`: 音频与语音处理

**完整分类列表：** https://arxiv.org/category_taxonomy

---

### ARXIV_KEYWORDS

**描述：** 关键词过滤列表（逗号分隔）

**类型：** 列表

**默认值：** `artificial intelligence, machine learning, deep learning`

**示例：**
```bash
ARXIV_KEYWORDS=transformer, attention, neural network, reinforcement learning
```

**说明：**
- 不区分大小写
- 匹配标题或摘要
- 与分类过滤是"或"关系（满足任一条件即可）

---

### ARXIV_MAX_DAYS_BACK

**描述：** 向前查询天数

**类型：** 整数

**默认值：** `1`

**示例：**
```bash
ARXIV_MAX_DAYS_BACK=3
```

**说明：**
- 1 = 只获取昨天的论文（推荐）
- 7 = 获取最近一周的论文
- arXiv 通常在美国东部时间晚上 8 点发布前一天的论文

---

## LLM 配置

### LLM_PROVIDER

**描述：** LLM 服务提供商

**类型：** 字符串

**默认值：** `openai`

**可选值：**
- `openai` - OpenAI (GPT-4, GPT-3.5)
- `deepseek` - DeepSeek
- `claude` / `anthropic` - Anthropic Claude
- `qwen` - 阿里云通义千问
- `bytedance` - 字节跳动豆包

**示例：**
```bash
LLM_PROVIDER=openai
```

---

### LLM_API_KEY

**描述：** LLM API 密钥

**类型：** 字符串

**必需：** 是

**示例：**
```bash
LLM_API_KEY=sk-proj-xxxxxxxxxxxxx
```

**别名：** `OPENAI_API_KEY`（向后兼容）

**获取方式：**
- OpenAI: https://platform.openai.com/api-keys
- DeepSeek: https://platform.deepseek.com/api_keys
- Claude: https://console.anthropic.com/
- Qwen: https://dashscope.aliyun.com/
- ByteDance: https://console.volcengine.com/ark

---

### LLM_MODEL

**描述：** 使用的模型名称

**类型：** 字符串

**默认值：** `gpt-4o-mini`

**示例：**
```bash
# OpenAI
LLM_MODEL=gpt-4o-mini
LLM_MODEL=gpt-4-turbo
LLM_MODEL=gpt-3.5-turbo

# DeepSeek
LLM_MODEL=deepseek-chat

# Claude
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_MODEL=claude-3-haiku-20240307

# Qwen
LLM_MODEL=qwen-max
LLM_MODEL=qwen-turbo

# ByteDance
LLM_MODEL=ep-xxxxx-xxxxx
```

**别名：** `OPENAI_MODEL`（向后兼容）

---

### LLM_BASE_URL

**描述：** LLM API 基础 URL

**类型：** 字符串

**默认值：** `https://api.openai.com`

**示例：**
```bash
# OpenAI（默认）
LLM_BASE_URL=https://api.openai.com

# DeepSeek
LLM_BASE_URL=https://api.deepseek.com

# Claude
LLM_BASE_URL=https://api.anthropic.com

# Qwen
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# ByteDance
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

**别名：** `OPENAI_BASE_URL`（向后兼容）

**说明：**
- 大多数提供商会自动替换默认 OpenAI URL
- 仅在使用自定义端点或代理时需要修改

---

### SUMMARY_FORMAT

**描述：** 摘要输出格式

**类型：** 字符串

**默认值：** `markdown`

**示例：**
```bash
SUMMARY_FORMAT=markdown
```

---

### SUMMARY_MAX_TOKENS

**描述：** 每篇论文摘要的最大 token 数

**类型：** 整数

**默认值：** `1024`

**示例：**
```bash
SUMMARY_MAX_TOKENS=2048
```

**说明：**
- 值越大，摘要越详细，但成本越高
- 建议范围：512-2048

---

### LLM_REQUEST_TIMEOUT

**描述：** LLM API 请求超时时间（秒）

**类型：** 整数

**默认值：** `60`

**示例：**
```bash
LLM_REQUEST_TIMEOUT=120
```

---

### ANTHROPIC_VERSION

**描述：** Anthropic API 版本（仅 Claude）

**类型：** 字符串

**默认值：** `2023-06-01`

**示例：**
```bash
ANTHROPIC_VERSION=2023-06-01
```

---

### LLM_MAX_CONCURRENT

**描述：** 最大并发 LLM 请求数

**类型：** 整数

**默认值：** `4`

**范围：** >= 1

**示例：**
```bash
LLM_MAX_CONCURRENT=8
```

**说明：**
- 值越大，处理速度越快，但可能触发速率限制
- 建议值：2-10

---

### LLM_RATE_LIMIT_RPM

**描述：** 每分钟最大请求数（0 = 无限制）

**类型：** 整数

**默认值：** `20`

**范围：** >= 0

**示例：**
```bash
LLM_RATE_LIMIT_RPM=60
```

**说明：**
- 防止超出 API 提供商的速率限制
- 0 表示不限制

---

### LLM_RETRY_ON_RATE_LIMIT

**描述：** 遇到速率限制时是否自动重试

**类型：** 布尔值

**默认值：** `true`

**示例：**
```bash
LLM_RETRY_ON_RATE_LIMIT=true
```

---

### LLM_RETRY_ATTEMPTS

**描述：** LLM 请求失败重试次数

**类型：** 整数

**默认值：** `3`

**范围：** >= 0

**示例：**
```bash
LLM_RETRY_ATTEMPTS=5
```

---

### LLM_RETRY_BASE_DELAY

**描述：** LLM 重试基础延迟时间（秒）

**类型：** 浮点数

**默认值：** `1.0`

**范围：** > 0

**示例：**
```bash
LLM_RETRY_BASE_DELAY=2.0
```

---

## 完整配置示例

### 最小配置（API 模式 + OpenAI）

```bash
# .env

# arXiv 获取
ARXIV_FETCH_MODE=api

# SMTP 发送
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
SMTP_USE_TLS=true
MAIL_FROM_ADDRESS=your-email@gmail.com
MAIL_TO_ADDRESS=your-email@gmail.com

# LLM
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-xxxxxxxxxxxxx
LLM_MODEL=gpt-4o-mini
```

### 完整配置（所有选项）

```bash
# .env - 完整配置示例

# ========================================
# arXiv 获取配置
# ========================================
ARXIV_FETCH_MODE=api
ARXIV_API_MAX_RESULTS=200

# ========================================
# 邮箱配置（仅 Email 模式需要）
# ========================================
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your-email@gmail.com
IMAP_PASSWORD=your-app-specific-password
IMAP_FOLDER=INBOX
MAIL_SENDER_FILTER=no-reply@arxiv.org
MAIL_SUBJECT_KEYWORDS=arXiv, Daily, digest

# ========================================
# SMTP 发送配置
# ========================================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
SMTP_USE_TLS=true
SMTP_TIMEOUT=30
SMTP_RETRY_ATTEMPTS=3
SMTP_RETRY_BASE_DELAY=2.0
MAIL_FROM_ADDRESS=your-email@gmail.com
MAIL_TO_ADDRESS=your-email@gmail.com

# ========================================
# 过滤配置
# ========================================
ARXIV_ALLOWED_CATEGORIES=cs.AI, cs.LG, cs.CV, cs.CL, cs.RO
ARXIV_KEYWORDS=transformer, attention, neural network
ARXIV_MAX_DAYS_BACK=1

# ========================================
# LLM 配置
# ========================================
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-xxxxxxxxxxxxx
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com
SUMMARY_FORMAT=markdown
SUMMARY_MAX_TOKENS=1024
LLM_REQUEST_TIMEOUT=60

# 并发和速率限制
LLM_MAX_CONCURRENT=4
LLM_RATE_LIMIT_RPM=20
LLM_RETRY_ON_RATE_LIMIT=true
LLM_RETRY_ATTEMPTS=3
LLM_RETRY_BASE_DELAY=1.0

# Claude 特定配置
ANTHROPIC_VERSION=2023-06-01
```

### 不同 LLM 提供商示例

#### OpenAI
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-xxxxxxxxxxxxx
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com
```

#### DeepSeek
```bash
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-xxxxxxxxxxxxx
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
```

#### Claude (Anthropic)
```bash
LLM_PROVIDER=claude
LLM_API_KEY=sk-ant-xxxxxxxxxxxxx
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_BASE_URL=https://api.anthropic.com
ANTHROPIC_VERSION=2023-06-01
```

#### Qwen (阿里云)
```bash
LLM_PROVIDER=qwen
LLM_API_KEY=sk-xxxxxxxxxxxxx
LLM_MODEL=qwen-max
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

#### ByteDance (豆包)
```bash
LLM_PROVIDER=bytedance
LLM_API_KEY=xxxxxxxxxxxxx
LLM_MODEL=ep-xxxxx-xxxxx
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

---

## 配置验证

### 运行验证

应用程序在启动时自动验证配置：

```bash
ai-mail-relay --log-level DEBUG
```

### 常见验证错误

**缺少必需配置：**
```
ValueError: Missing required SMTP configuration: SMTP_HOST, SMTP_PASSWORD
```

**无效的模式：**
```
ValueError: Invalid ARXIV_FETCH_MODE 'invalid'. Valid options: email, api
```

**无效的数值：**
```
ValueError: SMTP_TIMEOUT must be > 0
```

---

## 相关文档 | Related Documentation

- [故障排查指南](troubleshooting.md) - 常见问题诊断和解决
- [README](../README.md) - 项目概述和快速开始
- [CLAUDE.md](../CLAUDE.md) - 开发者指南和架构说明
