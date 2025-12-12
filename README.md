# AI Mail Relay

通过 arXiv API 获取每日 AI 相关论文，筛选后调用大模型生成摘要并转发给指定邮箱。

## 📚 文档导航

### 用户文档
- **[README.md](README.md)** - 项目介绍、安装、基本使用（本文档）
- **[DEPLOY.md](DEPLOY.md)** - 服务器部署指南、定时任务
- **[配置参考](docs/configuration.md)** - 所有配置选项的详细说明
- **[故障排查指南](docs/troubleshooting.md)** - 常见问题诊断和解决方案

### 开发者文档
- **[CLAUDE.md](CLAUDE.md)** - 项目架构、技术细节、开发指南
- **[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)** - 文献管理与用户管理系统开发计划
- **[CHANGELOG.md](CHANGELOG.md)** - 版本更新历史

---

## 功能概览
- **API 获取论文**：从 arXiv API 获取每日论文
- 解析论文信息，按类别 / 关键词筛选 AI 相关论文
- 调用多种大模型接口（OpenAI、DeepSeek、Claude、千问、字节等）生成 Markdown 摘要
- 多线程并发生成论文摘要，支持请求速率限制与退避重试
- 通过 SMTP 转发摘要邮件，并附带包含详细内容的附件
- 若当天无论文，自动发送提醒邮件，便于监控任务状态
- **文献管理**：持久化存储论文，跨运行去重，避免重复处理（v2.0+）
- **多用户订阅**：支持多用户按分类/关键词订阅，个性化邮件投递（v2.0+）
- **实验性分析**：embedding 缓存 + 聚类 + 趋势报告（`ai-mail-relay analyze ...`）

## 环境要求
- Python 3.10+
- 只需 SMTP 邮箱账号用于发送邮件
- 至少一家支持的 LLM 服务 API Key（可通过 `LLM_BASE_URL` 指定自建代理）

## 安装
```bash
pip install -e .
```

## 配置方式

通过环境变量或 `.env` 文件提供配置。以下为主要配置项，**完整配置说明请查看 [配置参考文档](docs/configuration.md)**。

### 必需配置

```bash
# arXiv 获取模式（固定为 API）
ARXIV_FETCH_MODE=api

# SMTP 发送配置
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password  # Gmail 需要应用专用密码
SMTP_USE_TLS=true
MAIL_FROM_ADDRESS=your-email@gmail.com
MAIL_TO_ADDRESS=your-email@gmail.com
# 提示：Gmail 应用专用密码请填 16 位不含空格的字符，否则会返回 5.7.8 BadCredentials

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
| `ARXIV_FETCH_MODE` | 获取模式（仅支持 `api`） | `api` |
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

### 分析配置（实验性）

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `EMBEDDING_PROVIDER` | embedding 提供商（`qwen`/`local`） | `qwen` |
| `EMBEDDING_MODEL` | embedding 模型名称 | `text-embedding-v3` |
| `EMBEDDING_DIM` | embedding 维度 | `1024` |
| `EMBEDDING_BATCH_SIZE` | 单次批量大小 | `25` |
| `EMBEDDING_FALLBACK_LOCAL` | Qwen 调用失败时是否回退本地 deterministic embedding | `true` |
| `CLUSTER_MIN_PAPERS` | 一个聚类的最小论文数 | `3` |
| `CLUSTER_SIMILARITY_THRESHOLD` | cosine 相似度阈值 | `0.75` |
| `CLUSTER_MAX_PER_FIELD` | 每个一级领域最多保留的聚类数 | `20` |
| `TREND_LLM_MAX_PAPERS` | 趋势分析最多采样论文数 | `50` |
| `ANALYSIS_REPORT_DIR` | 报告输出目录 | `./reports` |
| `ANALYSIS_REPORT_FORMAT` | 报告格式 | `markdown` |

> 提示：若未配置 `QWEN_API_KEY`，分析模块会回退到本地 deterministic embedding（仅用于开发验证）。
> 推荐将上述变量与 `QWEN_API_KEY` 一并写入 `.env`（参考 `.env.example`）。

`.env` 片段示例：
```bash
EMBEDDING_PROVIDER=qwen
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024
EMBEDDING_BATCH_SIZE=25
EMBEDDING_FALLBACK_LOCAL=true
QWEN_API_KEY=sk-xxxx
```

## 数据库配置（v2.0+）

应用使用 SQLite 数据库存储已处理的论文，防止重复处理。

### 初始化数据库
```bash
ai-mail-relay db init
```

### 查看数据库状态
```bash
ai-mail-relay db status
```

### 备份数据库
```bash
ai-mail-relay db backup
ai-mail-relay db backup --output /path/to/backup.db
```

### 数据库配置选项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_ENABLED` | 启用数据库存储 | `true` |
| `DATABASE_PATH` | SQLite 数据库路径 | `./data/ai_mail_relay.db` |
| `MULTI_USER_MODE` | 启用多用户模式（需创建用户与订阅） | `false` |
| `SKIP_DELIVERED_PAPERS` | 多用户模式下跳过已投递论文 | `true` |

## 用户管理（多用户模式）

### 添加用户
```bash
ai-mail-relay user add --email "user@example.com" --name "张三"
```

### 管理订阅
```bash
# 添加分类订阅
ai-mail-relay user subscribe --email "user@example.com" --categories "cs.AI,cs.LG"

# 添加关键词订阅
ai-mail-relay user subscribe --email "user@example.com" --keywords "transformer,LLM"

# 查看订阅
ai-mail-relay user subscriptions --email "user@example.com"

# 取消订阅
ai-mail-relay user unsubscribe --email "user@example.com" --categories "cs.CV"
```

### 用户列表
```bash
ai-mail-relay user list
ai-mail-relay user show --email "user@example.com"
```

## 使用说明
```bash
ai-mail-relay
```

程序执行流程：
1. **获取论文**：通过 arXiv API 获取指定类别的最新论文
2. 解析论文信息，按类别或关键词筛选 AI 相关论文
3. 将筛选出的论文提交给 LLM 生成摘要（支持多线程并发处理）
4. 通过 SMTP 发送邮件：正文为摘要，附件为详细内容（Markdown 文本）

**配置示例（仅 API 模式）：**

```bash
ARXIV_FETCH_MODE=api
ARXIV_API_MAX_RESULTS=200
ARXIV_ALLOWED_CATEGORIES=cs.AI,cs.LG,cs.CV,cs.CL
```

## 分析 CLI（实验性）

> 需先执行 `ai-mail-relay db init` 并确保数据库中已有目标日期论文。

示例：
```bash
ai-mail-relay analyze embed --date-range 2025-12-10
ai-mail-relay analyze cluster --date-range 2025-12-10
ai-mail-relay analyze trend --date-range 2025-12-01:2025-12-10 --period weekly
ai-mail-relay analyze report --date-range 2025-12-10 --format html --output reports/report-2025-12-10.html
```

- `analyze embed`：批量生成/缓存 embedding（`--force` 可覆盖重算）
- `analyze cluster`：按 research_field 粗分组 + embedding 细聚类，并写入数据库
- `analyze trend`：输出领域分布与 LLM 趋势摘要，自动对比上一期快照（如有）
- `analyze report`：聚类 + 趋势生成报告，支持 `--format markdown|html|json`（默认取 `ANALYSIS_REPORT_FORMAT`，输出到 `ANALYSIS_REPORT_DIR`）

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

# 3. 设置定时任务（默认每天 08:00 北京时间运行）
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
# 添加: 0 8 * * * cd /path/to/AI_mail_relay_app && ./deploy/run.sh
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

# 快速测试（跳过 LLM）
python test.py --no-llm

# 测试更多论文
python test.py --papers 5
```

### 配置调整
- 可在 `ARXIV_ALLOWED_CATEGORIES` 中自定义领域
- 调整 `ARXIV_MAX_DAYS_BACK` 控制回溯天数
- 设置 `LLM_MAX_CONCURRENT` 控制并发数
