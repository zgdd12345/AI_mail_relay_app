# Deploy 部署脚本目录

本目录包含所有服务器部署和运维相关的脚本。

## 📦 脚本清单

### 核心部署脚本

| 脚本 | 用途 | 使用场景 |
|------|------|---------|
| `deploy.sh` | 一键部署 | 首次部署时运行 |
| `run.sh` | 执行程序 | 手动运行或 Cron 调用 |
| `setup_cron.sh` | 配置定时任务 | 设置自动运行时间 |

### 验证和诊断脚本

| 脚本 | 用途 | 使用场景 |
|------|------|---------|
| `verify_api_mode.sh` | API 模式验证 | 部署后验证配置 |
| `diagnose.sh` | 网络诊断 | 排查连接问题 |
| `health_check.sh` | 健康检查 | 定期监控状态 |

---

## 🚀 快速部署（4 步）

### 1️⃣ 运行部署脚本
```bash
./deploy/deploy.sh
```
自动完成：Python 检查、虚拟环境、依赖安装、配置文件生成

### 2️⃣ 编辑配置文件
```bash
vim .env
```
配置 API 模式（推荐）：
```env
ARXIV_FETCH_MODE=api
SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
LLM_PROVIDER=deepseek
LLM_API_KEY=your_api_key
```

### 3️⃣ 验证配置
```bash
./deploy/verify_api_mode.sh  # API 模式验证（推荐）
# 或
./deploy/run.sh               # 完整测试
```

### 4️⃣ 设置定时任务
```bash
./deploy/setup_cron.sh
```
按提示输入运行时间（默认：11:00,12:00,13:00）

---

## 📋 脚本详细说明

### deploy.sh - 一键部署

**功能**：
- 检查 Python 3.10+ 版本
- 创建虚拟环境
- 安装项目依赖
- 生成 .env 配置模板
- 创建日志目录

**使用**：
```bash
./deploy/deploy.sh
```

---

### run.sh - 程序执行

**功能**：
- 激活虚拟环境
- 设置北京时区（Asia/Shanghai）
- 运行主程序并记录日志
- 智能分析运行结果（成功/失败/跳过）
- 自动清理 30 天前的旧日志

**输出**：
- 屏幕显示：运行状态、模式（API/邮箱）、论文数量
- 日志文件：`logs/run_YYYY-MM-DD_HH-MM-SS.log`

**使用**：
```bash
# 手动运行
./deploy/run.sh

# Cron 自动调用（setup_cron.sh 配置后）
```

---

### setup_cron.sh - 定时任务配置

**功能**：
- 交互式设置运行时间
- 自动生成 Cron 表达式
- 备份现有 Cron 任务
- 清理旧任务并添加新任务

**使用**：
```bash
./deploy/setup_cron.sh

# 示例输入：
运行时间: 09:00,14:00,18:00  # 自定义
运行时间: [按 Enter]          # 使用默认 11:00,12:00,13:00
```

**管理**：
```bash
crontab -l           # 查看当前任务
crontab -e           # 编辑任务
./deploy/setup_cron.sh  # 重新设置
```

---

### verify_api_mode.sh - API 模式验证 ⭐

**功能**：
- 检查 Python 环境和依赖
- 验证 .env 配置完整性
- 测试 arXiv API 连接
- 测试 SMTP 连接
- 运行快速功能测试
- 检查日志目录权限
- 检查 Cron 配置（如已设置）

**输出**：
- ✅ 绿色：通过
- ❌ 红色：失败
- ⚠️  黄色：警告

**使用**：
```bash
./deploy/verify_api_mode.sh
```

**建议**：在部署完成后、设置 Cron 前运行此脚本

---

### diagnose.sh - 网络诊断

**功能**：
- 测试 IMAP 端口连接（993）
- 测试 SMTP 端口连接（587）
- DNS 解析检查
- 提供具体解决建议

**使用**：
```bash
./deploy/diagnose.sh
```

**适用场景**：
- 连接超时错误
- 认证失败
- 网络问题排查

---

### health_check.sh - 健康检查

**功能**：
- 检查 arXiv API 可访问性
- 检查 SMTP 连接
- 监控日志更新情况
- 记录到 `logs/health_check.log`

**使用**：
```bash
# 手动检查
./deploy/health_check.sh

# 定时检查（添加到 cron）
crontab -e
# 添加：0 * * * * cd /path/to/AI_mail_relay_app && ./deploy/health_check.sh
```

**日志查看**：
```bash
tail -f logs/health_check.log
```

---

## 📊 日志管理

### 日志文件

```
logs/
├── cron.log                      # Cron 总日志
├── run_2025-10-31_09-00-00.log  # 单次运行日志
└── health_check.log              # 健康检查日志
```

### 日志命令

```bash
# 实时查看 Cron 日志
tail -f logs/cron.log

# 查看最新一次运行
ls -t logs/run_*.log | head -1 | xargs cat

# 查看今天的运行记录
ls logs/run_$(date +%Y-%m-%d)_*.log

# 查看健康检查
tail -20 logs/health_check.log

# 检查错误
grep -i "error\|failed" logs/run_*.log
```

### 日志清理

- **自动清理**：`run.sh` 自动删除 30 天前的日志
- **手动清理**：`find logs -name "run_*.log" -mtime +30 -delete`

---

## ⚙️ Cron 时间配置

### 常用时间格式

```bash
# 格式：分 时 日 月 周
0 9 * * *      # 每天 09:00
30 14 * * *    # 每天 14:30
0 9,14,18 * * *  # 每天 09:00, 14:00, 18:00
0 */6 * * *    # 每 6 小时
0 9 * * 1-5    # 工作日 09:00
```

### 时区说明

- 脚本自动设置 `TZ=Asia/Shanghai`
- Cron 时间 = 北京时间
- 建议在 arXiv 发布后运行（09:00 之后）

---

## 🔧 故障排查

### 1. Cron 未执行

```bash
# 检查 Cron 服务
sudo systemctl status cron  # Linux
launchctl list | grep cron  # macOS

# 查看 Cron 日志
tail -f logs/cron.log

# 检查 Cron 任务
crontab -l
```

### 2. 程序运行失败

```bash
# 查看详细错误
cat logs/cron.log

# 手动测试
./deploy/run.sh

# 运行诊断
./deploy/diagnose.sh
```

### 3. API 连接问题

```bash
# 完整验证
./deploy/verify_api_mode.sh

# 测试 API 连接
curl -I https://export.arxiv.org/api/query

# 检查防火墙
sudo iptables -L -n | grep 443
```

---

## 📚 相关文档

- **[../DEPLOY.md](../DEPLOY.md)** - 完整部署指南和故障排查
- **[../README.md](../README.md)** - 项目介绍和使用说明
- **[../CLAUDE.md](../CLAUDE.md)** - 架构说明和技术细节

---

## 💡 最佳实践

1. **首次部署**：按照 4 步流程完整执行
2. **验证配置**：使用 `verify_api_mode.sh` 确保配置正确
3. **定期检查**：将 `health_check.sh` 添加到 Cron
4. **日志监控**：定期查看 `logs/cron.log`
5. **时间设置**：建议设置在 09:00 之后（arXiv 发布后）

---

**快速开始**：`./deploy/deploy.sh` → 编辑 `.env` → `./deploy/verify_api_mode.sh` → `./deploy/setup_cron.sh` ✅
