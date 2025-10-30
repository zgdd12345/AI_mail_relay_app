# AI Mail Relay 服务器部署指南

本文档介绍如何在服务器上部署 AI Mail Relay 并设置定时任务。

## 📋 部署前准备

### 系统要求
- **操作系统**: Linux / macOS
- **Python 版本**: 3.10 或更高
- **网络**: 能够访问 IMAP/SMTP 服务器和 LLM API

### 必需信息
1. **邮箱账号**: 用于接收 arXiv 邮件的 IMAP 账号
2. **SMTP 账号**: 用于发送摘要邮件（可与 IMAP 相同）
3. **LLM API Key**: DeepSeek / OpenAI / Claude 等任一 API 密钥

### Gmail 用户注意
Gmail 需要使用"应用专用密码"而非账户密码：
1. 访问 https://myaccount.google.com/apppasswords
2. 生成应用专用密码（16位，去掉空格）
3. 在 `.env` 中使用生成的密码

---

## 🚀 快速部署（3 步完成）

### 第 1 步：上传代码到服务器

```bash
# 方式 1: 使用 Git
git clone <your-repo-url>
cd AI_mail_relay_app

# 方式 2: 使用 scp 上传
scp -r AI_mail_relay_app user@server:/path/to/
ssh user@server
cd /path/to/AI_mail_relay_app
```

### 第 2 步：运行部署脚本

```bash
./deploy/deploy.sh
```

这个脚本会自动完成：
- ✅ 检查 Python 版本
- ✅ 创建虚拟环境
- ✅ 安装所有依赖
- ✅ 创建 `.env` 配置文件
- ✅ 创建日志目录
- ✅ 测试程序运行

### 第 3 步：配置环境变量

编辑 `.env` 文件，填写实际配置：

```bash
vim .env  # 或使用 nano .env
```

**必须配置的项目**：
```env
# IMAP 配置
IMAP_HOST=imap.gmail.com
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_app_password

# SMTP 配置
SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# 邮件地址
MAIL_FROM_ADDRESS=your_email@gmail.com
MAIL_TO_ADDRESS=your_email@gmail.com

# LLM 配置
LLM_PROVIDER=deepseek
LLM_API_KEY=your_api_key_here
LLM_MODEL=deepseek-chat
```

保存后测试运行：

```bash
./deploy/run.sh
```

---

## ⏰ 设置定时任务

### 自动设置（推荐）

运行 Cron 设置脚本：

```bash
./deploy/setup_cron.sh
```

按提示操作：
1. 输入运行时间（格式：`HH:MM,HH:MM,HH:MM`）
2. 默认为 `11:00,12:00,13:00`（北京时间）
3. 按 Enter 确认

**示例输出**：
```
运行时间 [直接按 Enter 使用默认值]: 09:00,14:00,18:00

设置的运行时间: 09:00,14:00,18:00

  ✓ 09:00 -> cron: 0 9 * * *
  ✓ 14:00 -> cron: 0 14 * * *
  ✓ 18:00 -> cron: 0 18 * * *

Cron 任务设置成功！
```

### 手动设置

编辑 crontab：

```bash
crontab -e
```

添加以下内容（替换 `/path/to/` 为实际路径）：

```cron
# AI Mail Relay - 每天 11:00, 12:00, 13:00 运行
0 11 * * * cd /path/to/AI_mail_relay_app && /path/to/AI_mail_relay_app/deploy/run.sh >> /path/to/AI_mail_relay_app/logs/cron.log 2>&1
0 12 * * * cd /path/to/AI_mail_relay_app && /path/to/AI_mail_relay_app/deploy/run.sh >> /path/to/AI_mail_relay_app/logs/cron.log 2>&1
0 13 * * * cd /path/to/AI_mail_relay_app && /path/to/AI_mail_relay_app/deploy/run.sh >> /path/to/AI_mail_relay_app/logs/cron.log 2>&1
```

**Cron 时间格式说明**：
```
* * * * *
│ │ │ │ │
│ │ │ │ └─ 星期 (0-7, 0和7都表示周日)
│ │ │ └─── 月份 (1-12)
│ │ └───── 日期 (1-31)
│ └─────── 小时 (0-23)
└───────── 分钟 (0-59)
```

**常用时间示例**：
- `0 9 * * *` - 每天 09:00
- `30 14 * * *` - 每天 14:30
- `0 */6 * * *` - 每 6 小时一次
- `0 9 * * 1-5` - 工作日 09:00

---

## 📊 日志管理

### 日志文件位置

```
logs/
├── cron.log           # Cron 任务总日志
└── run_YYYY-MM-DD_HH-MM-SS.log  # 每次运行的详细日志
```

### 查看日志

```bash
# 查看最新的运行日志
ls -lt logs/run_*.log | head -1 | xargs cat

# 实时查看 Cron 日志
tail -f logs/cron.log

# 查看最近 10 条日志
tail -20 logs/cron.log

# 查看今天的所有日志
ls logs/run_$(date +%Y-%m-%d)_*.log
```

### 日志清理

运行脚本会自动清理 30 天前的日志。手动清理：

```bash
# 删除 30 天前的日志
find logs -name "run_*.log" -mtime +30 -delete

# 删除所有日志
rm -f logs/*.log
```

---

## 🔧 运维管理

### 查看 Cron 任务

```bash
# 查看当前所有 Cron 任务
crontab -l

# 只查看 AI Mail Relay 相关任务
crontab -l | grep -A 5 "AI Mail Relay"
```

### 修改运行时间

```bash
# 重新运行设置脚本
./deploy/setup_cron.sh

# 或手动编辑
crontab -e
```

### 暂停定时任务

```bash
# 方式 1: 注释掉 Cron 任务
crontab -e
# 在任务前加 #

# 方式 2: 临时删除所有任务
crontab -r
```

### 恢复定时任务

```bash
# 重新运行设置脚本
./deploy/setup_cron.sh
```

### 手动运行

```bash
# 测试运行（查看输出）
./deploy/run.sh

# 后台运行
nohup ./deploy/run.sh > /dev/null 2>&1 &
```

### 更新代码

```bash
# 停止 Cron 任务
crontab -r

# 拉取最新代码
git pull

# 重新安装
source venv/bin/activate
pip install -e .

# 恢复 Cron 任务
./deploy/setup_cron.sh
```

---

## 🐛 故障排查

### 问题 1: 定时任务未执行

**检查步骤**：

1. 确认 Cron 服务运行：
```bash
# Linux
sudo systemctl status cron

# macOS
sudo launchctl list | grep cron
```

2. 检查 Cron 任务：
```bash
crontab -l
```

3. 查看系统日志：
```bash
# Linux
grep CRON /var/log/syslog

# macOS
log show --predicate 'process == "cron"' --last 1h
```

### 问题 2: 程序运行失败

**检查步骤**：

1. 查看运行日志：
```bash
tail -100 logs/cron.log
```

2. 手动运行测试：
```bash
./deploy/run.sh
```

3. 检查配置文件：
```bash
cat .env | grep -v "^#" | grep -v "^$"
```

### 问题 3: 时区问题

程序会自动设置 `TZ=Asia/Shanghai`，但如果遇到时区问题：

```bash
# 检查系统时区
date
timedatectl  # Linux

# 临时设置时区
export TZ=Asia/Shanghai

# 永久设置时区（Linux）
sudo timedatectl set-timezone Asia/Shanghai
```

### 问题 4: 权限问题

```bash
# 确保脚本可执行
chmod +x deploy/*.sh

# 确保日志目录可写
chmod 755 logs
```

---

## 📝 高级配置

### 自定义运行时间

在 `.env` 文件中可以添加更多配置项（需要修改代码支持）：

```env
# 示例：只在工作日运行
# 需要在 cron 表达式中添加: 0 11 * * 1-5
```

### 邮件发送失败重试

可以在 `deploy/run.sh` 中添加重试逻辑：

```bash
# 重试 3 次
for i in {1..3}; do
    python -m ai_mail_relay.main && break
    sleep 60
done
```

### 使用 systemd (Linux 推荐)

创建 systemd service 和 timer 代替 cron：

```bash
# 创建 service 文件
sudo vim /etc/systemd/system/ai-mail-relay.service

# 创建 timer 文件
sudo vim /etc/systemd/system/ai-mail-relay.timer

# 启用并启动
sudo systemctl enable ai-mail-relay.timer
sudo systemctl start ai-mail-relay.timer
```

---

## 📞 支持

如遇问题：
1. 查看日志文件
2. 检查 [CLAUDE.md](CLAUDE.md) 了解代码架构
3. 查看 [README.md](README.md) 了解功能说明

---

## ✅ 部署检查清单

- [ ] Python 3.10+ 已安装
- [ ] 运行 `./deploy/deploy.sh` 成功
- [ ] `.env` 文件已正确配置
- [ ] 手动运行 `./deploy/run.sh` 成功
- [ ] 收到测试邮件
- [ ] Cron 任务已设置
- [ ] 日志目录可写
- [ ] 系统时区为北京时间

---

**部署完成！程序将在每天 11:00、12:00、13:00（北京时间）自动运行。** 🎉
