# AI Mail Relay

抓取我订阅的 arXiv 邮件，将当日 AI 相关论文筛选后，调用大模型生成摘要并重新转发给指定邮箱。

## 📚 文档导航

### 用户文档
- **[README.md](README.md)** - 项目介绍、安装、基本使用（本文档）
- **[DEPLOY.md](DEPLOY.md)** - 服务器部署指南、定时任务
- **[配置参考](docs/configuration.md)** - 所有配置选项的详细说明
- **[故障排查指南](docs/troubleshooting.md)** - 常见问题诊断和解决方案

### 开发者文档
- **[CLAUDE.md](CLAUDE.md)** - 项目架构、技术细节、开发指南
- **[CHANGELOG.md](CHANGELOG.md)** - 版本更新历史

---

## 功能概览
- **双模式获取论文**：支持直接从 arXiv API 获取（推荐）或从 IMAP 邮箱获取订阅邮件
- 解析论文信息，按类别 / 关键词筛选 AI 相关论文
- 调用多种大模型接口（OpenAI、DeepSeek、Claude、千问、字节等）生成 Markdown 摘要
- 多线程并发生成论文摘要，支持请求速率限制与退避重试
- 通过 SMTP 转发摘要邮件，并附带包含详细内容的附件

## 环境要求
- Python 3.10+
- **API 模式**（推荐）：只需 SMTP 邮箱账号用于发送邮件
- **邮箱模式**（可选）：需要 IMAP 和 SMTP 邮箱账号
- 至少一家支持的 LLM 服务 API Key（可通过 `LLM_BASE_URL` 指定自建代理）

## 安装
```bash
pip install -e .
```

## 配置方式

通过环境变量或 `.env` 文件提供配置。以下为主要配置项，**完整配置说明请查看 [配置参考文档](docs/configuration.md)**。

### 必需配置

```bash
# arXiv 获取模式
ARXIV_FETCH_MODE=api  # 推荐使用 API 模式

# SMTP 发送配置
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password  # Gmail 需要应用专用密码
SMTP_USE_TLS=true
MAIL_FROM_ADDRESS=your-email@gmail.com
MAIL_TO_ADDRESS=your-email@gmail.com

# LLM 配置
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-xxxxxxxxxxxxx
LLM_MODEL=gpt-4o-mini
```

### 新增配置（v1.1+）

```bash
# SMTP 超时和重试配置
SMTP_TIMEOUT=30              # 连接超时（秒），默认 30
SMTP_RETRY_ATTEMPTS=3        # 重试次数，默认 3
SMTP_RETRY_BASE_DELAY=2.0    # 基础延迟（秒），默认 2.0
```

### 主要配置项

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| **arXiv 获取** |
| `ARXIV_FETCH_MODE` | 获取模式（`api` 推荐 / `email`） | `api` |
| `ARXIV_API_MAX_RESULTS` | API 模式下最大获取论文数 | `200` |
| `ARXIV_ALLOWED_CATEGORIES` | AI 类别白名单（逗号分隔） | `cs.AI,cs.LG,cs.CV,...` |
| **SMTP 发送** |
| `SMTP_HOST` | SMTP 服务器地址 | 必需 |
| `SMTP_PORT` | SMTP 端口 | `587` |
| `SMTP_USER` | SMTP 用户名 | 必需 |
| `SMTP_PASSWORD` | SMTP 密码 / 授权码 | 必需 |
| `SMTP_USE_TLS` | 是否使用 STARTTLS | `true` |
| `SMTP_TIMEOUT` | 连接超时（秒）⭐ NEW | `30` |
| `SMTP_RETRY_ATTEMPTS` | 重试次数 ⭐ NEW | `3` |
| `SMTP_RETRY_BASE_DELAY` | 重试延迟（秒）⭐ NEW | `2.0` |
| **LLM 配置** |
| `LLM_PROVIDER` | 提供商（`openai`/`deepseek`/`claude`/`qwen`/`bytedance`） | `openai` |
| `LLM_API_KEY` | LLM API Key | 必需 |
| `LLM_MODEL` | 模型名称 | `gpt-4o-mini` |
| `LLM_MAX_CONCURRENT` | 并发线程数 | `4` |
| `LLM_RATE_LIMIT_RPM` | 每分钟最大请求数 | `20` |

📖 **完整配置列表**: 查看 [配置参考文档](docs/configuration.md)

## 使用说明
```bash
ai-mail-relay
```

程序执行流程：
1. **获取论文**：
   - **API 模式**（推荐）：直接从 arXiv API 获取指定类别的最新论文
   - **邮箱模式**：从 IMAP 邮箱读取未读的 arXiv 订阅邮件
2. 解析论文信息，按类别或关键词筛选 AI 相关论文
3. 将筛选出的论文提交给 LLM 生成摘要（支持多线程并发处理）
4. 通过 SMTP 发送邮件：正文为摘要，附件为详细内容（Markdown 文本）

### 论文获取模式对比

| 特性 | API 模式（推荐） | 邮箱模式 |
|------|----------------|---------|
| **配置复杂度** | 简单（无需 IMAP） | 复杂（需要 IMAP 凭据） |
| **可靠性** | 高（直接访问 arXiv） | 中（依赖邮件服务） |
| **运行频率** | 可多次运行 | 每天一次 |
| **论文覆盖** | 任意类别组合 | 仅订阅内容 |
| **测试友好** | 易于测试 | 需要真实邮件 |
| **速率限制** | 3 秒/请求 | 无 |

**配置示例**：

```bash
# API 模式（推荐）- 无需 IMAP 配置
ARXIV_FETCH_MODE=api
ARXIV_API_MAX_RESULTS=200
ARXIV_ALLOWED_CATEGORIES=cs.AI,cs.LG,cs.CV,cs.CL

# 邮箱模式 - 需要完整的 IMAP 配置
ARXIV_FETCH_MODE=email
IMAP_HOST=imap.gmail.com
IMAP_USER=your-email@gmail.com
IMAP_PASSWORD=your-app-password
```

### 并发控制说明

程序支持多线程并行调用 LLM API，提升摘要生成速度：

- **`LLM_MAX_CONCURRENT`**: 控制同时发起的 API 请求数量
  - 增加此值可加快处理速度，但需要注意 API 提供商的并发限制
  - 建议值：免费账号 2-4，付费账号 4-10

- **`LLM_RATE_LIMIT_RPM`**: 限制每分钟最大请求数
  - 避免触发 API 速率限制（例如 OpenAI 免费用户 3 RPM）
  - 设置为 0 表示不限制（仅依赖并发数控制）

- **`LLM_RETRY_ON_RATE_LIMIT`**: 遇到 429 错误时自动重试
  - 启用后会使用指数退避策略自动重试
  - 重试延迟：1秒 → 2秒 → 4秒...

**示例配置**：
```bash
# 适合 DeepSeek 免费账号（较高并发限制）
LLM_MAX_CONCURRENT=8
LLM_RATE_LIMIT_RPM=50

# 适合 OpenAI 免费账号（严格速率限制）
LLM_MAX_CONCURRENT=2
LLM_RATE_LIMIT_RPM=3

# 适合企业 API（无限制）
LLM_MAX_CONCURRENT=20
LLM_RATE_LIMIT_RPM=0
```

## 服务器部署

**一键部署脚本**（推荐）：

```bash
# 1. 运行部署脚本
./deploy/deploy.sh

# 2. 编辑配置文件
vim .env

# 3. 设置定时任务（默认每天 11:00, 12:00, 13:00 北京时间运行）
./deploy/setup_cron.sh
```

**详细部署文档**: 请查看 [DEPLOY.md](DEPLOY.md)（包含完整的部署指南和故障排查）

### 定时任务

程序支持通过 Cron 设置定时运行：

```bash
# 使用自动设置脚本
./deploy/setup_cron.sh

# 或手动添加 cron 任务
crontab -e
# 添加: 0 11,12,13 * * * cd /path/to/AI_mail_relay_app && ./deploy/run.sh
```

**日志查看**：
```bash
# 查看最新运行日志
tail -f logs/cron.log

# 查看所有运行记录
ls -lt logs/run_*.log
```

## 故障排查

遇到问题？请按以下步骤操作：

### 快速诊断

1. **运行诊断脚本**（服务器上）:
   ```bash
   ./deploy/diagnose.sh
   ```

2. **查看详细日志**:
   ```bash
   # 查看最新日志
   tail -100 logs/cron.log

   # 启用调试模式
   ai-mail-relay --log-level DEBUG
   ```

3. **查看完整故障排查文档**: 📖 [故障排查指南](docs/troubleshooting.md)

### 常见问题速查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| **SMTP 连接超时** | 云服务器防火墙封锁端口 | 1. 检查安全组出站规则<br>2. 运行 `./deploy/diagnose.sh`<br>3. 尝试端口 465 |
| **认证失败** | 未使用应用专用密码 | Gmail 用户需在 https://myaccount.google.com/apppasswords 生成应用密码 |
| **未收到邮件** | 可能无符合条件的论文 | 正常情况，检查 `ARXIV_ALLOWED_CATEGORIES` 配置 |
| **LLM API 失败** | API Key 错误或超限 | 检查 `LLM_API_KEY` 和账户额度 |

📖 **详细故障排查**: [docs/troubleshooting.md](docs/troubleshooting.md)

## 开发调试

### 日志调试
```bash
# 调整日志等级
ai-mail-relay --log-level DEBUG

# 或作为模块运行
python -m ai_mail_relay.main --log-level DEBUG
```

### 测试脚本
```bash
# 完整测试（API 模式，3 篇论文）
python test.py

# 测试 API 模式
python test.py --mode api

# 测试邮箱模式
python test.py --mode email

# 快速测试（跳过 LLM）
python test.py --no-llm

# 测试更多论文
python test.py --papers 5
```

### 配置调整
- 可在 `ARXIV_ALLOWED_CATEGORIES` 中自定义领域
- 调整 `ARXIV_MAX_DAYS_BACK` 控制回溯天数
- 设置 `LLM_MAX_CONCURRENT` 控制并发数
