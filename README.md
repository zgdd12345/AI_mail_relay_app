# AI Mail Relay

抓取我订阅的 arXiv 邮件，将当日 AI 相关论文筛选后，调用大模型生成摘要并重新转发给指定邮箱。

## 功能概览
- 连接 IMAP 邮箱，获取当天所有未读的 arXiv 订阅邮件
- 解析邮件中的论文信息，按类别 / 关键词筛选 AI 相关论文
- 调用多种大模型接口（OpenAI、DeepSeek、Claude、千问、字节等）生成 Markdown 摘要
- 通过 SMTP 转发摘要邮件，并附带包含详细内容的附件

## 环境要求
- Python 3.10+
- IMAP/SMTP 邮箱账号（支持 TLS）
- 至少一家支持的 LLM 服务 API Key（可通过 `LLM_BASE_URL` 指定自建代理）

## 安装
```bash
pip install -e .
```

## 配置方式
通过环境变量或 `.env` 文件提供以下配置：

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `IMAP_HOST` | IMAP 服务器地址 |  |
| `IMAP_PORT` | IMAP 端口 | `993` |
| `IMAP_USER` | IMAP 用户名 |  |
| `IMAP_PASSWORD` | IMAP 密码 / 授权码 |  |
| `IMAP_FOLDER` | 读取的邮箱目录 | `INBOX` |
| `MAIL_SENDER_FILTER` | 发件人过滤 | `no-reply@arxiv.org` |
| `MAIL_SUBJECT_KEYWORDS` | 主题关键词，逗号分隔 | `arXiv,Daily,digest` |
| `SMTP_HOST` | SMTP 服务器地址 |  |
| `SMTP_PORT` | SMTP 端口 | `587` |
| `SMTP_USER` | SMTP 用户名 |  |
| `SMTP_PASSWORD` | SMTP 密码 / 授权码 |  |
| `SMTP_USE_TLS` | 是否使用 STARTTLS | `true` |
| `MAIL_FROM_ADDRESS` | 转发邮件 From |  |
| `MAIL_TO_ADDRESS` | 转发目标邮箱 |  |
| `LLM_PROVIDER` | 大模型提供商（`openai`/`deepseek`/`claude`/`anthropic`/`qwen`/`bytedance`） | `openai` |
| `LLM_API_KEY` | LLM API Key（兼容 `OPENAI_API_KEY`） |  |
| `LLM_MODEL` | 模型名称（兼容 `OPENAI_MODEL`） | `gpt-4o-mini` |
| `LLM_BASE_URL` | 接口地址（兼容 `OPENAI_BASE_URL`） | `https://api.openai.com` |
| `SUMMARY_MAX_TOKENS` | 摘要最大 tokens | `1024` |
| `ARXIV_ALLOWED_CATEGORIES` | AI 类别白名单 | `cs.AI,cs.LG,cs.CV,cs.CL,cs.RO,cs.IR,stat.ML,eess.AS` |
| `ARXIV_KEYWORDS` | 关键字过滤（备用） | `artificial intelligence,machine learning,deep learning` |
| `ARXIV_MAX_DAYS_BACK` | 回溯天数（含当天） | `1` |
| `LLM_REQUEST_TIMEOUT` | LLM 请求超时（秒） | `60` |
| `ANTHROPIC_VERSION` | Claude 接口版本（Anthropic 专用） | `2023-06-01` |

> **提示**：  
> - DeepSeek 默认自动切换为 `https://api.deepseek.com/v1/chat/completions`  
> - 阿里千问默认使用 `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`  
> - 字节火山豆包默认使用 `https://ark.cn-beijing.volces.com/api/v3/chat/completions`  
> - 也可通过自定义 `LLM_BASE_URL` 指向私有代理或其他兼容接口

## 使用说明
```bash
ai-mail-relay
```

程序执行流程：
1. 从指定 IMAP 目录读取未读邮件并过滤 arXiv 摘要
2. 解析邮件正文获取论文条目，按类别或关键词筛选
3. 将筛选出的论文提交给 LLM 生成摘要
4. 通过 SMTP 发送邮件：正文为摘要，附件为详细内容（Markdown 文本）

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

**详细部署文档**: 请查看 [DEPLOY.md](DEPLOY.md)

**服务器遇到问题？**: 快速查看 [QUICKSTART_SERVER.md](QUICKSTART_SERVER.md) 立即解决常见错误

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

1. **运行诊断脚本** (服务器上):
   ```bash
   ./deploy/diagnose.sh
   ```

2. **查看详细日志**:
   ```bash
   tail -100 logs/cron.log
   ```

3. **查看故障排查文档**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### 常见问题速查

| 问题 | 解决方案 |
|------|---------|
| 连接超时 | 检查云服务商安全组，允许出站到端口 993, 587 |
| 认证失败 | Gmail 需要应用专用密码，访问 https://myaccount.google.com/apppasswords |
| 没有邮件 | 正常情况，系统不会发送空邮件 |

## 开发调试
- 日志等级可通过 `--log-level` 调整
- 本地调试: `python -m ai_mail_relay.main --log-level DEBUG`
- 测试少量论文: `python test_limited.py`（只处理前 3 篇）
- 可在 `ARXIV_ALLOWED_CATEGORIES` 中自定义领域
