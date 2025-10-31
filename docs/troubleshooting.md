# 故障排查指南 | Troubleshooting Guide

本文档提供 AI Mail Relay 应用程序常见问题的诊断和解决方案。

This document provides diagnostic and solution guidance for common AI Mail Relay application issues.

---

## 目录 | Table of Contents

- [SMTP 连接问题](#smtp-连接问题)
- [网络诊断工具](#网络诊断工具)
- [常见错误代码](#常见错误代码)
- [Gmail 特定问题](#gmail-特定问题)
- [云服务器配置](#云服务器配置)
- [日志分析](#日志分析)

---

## SMTP 连接问题

### 症状 | Symptoms

应用程序在发送邮件时失败，出现以下错误之一：

- `TimeoutError: [Errno 110] Connection timed out`
- `ConnectionRefusedError: [Errno 111] Connection refused`
- `SMTPException`
- `OSError`

### 诊断步骤 | Diagnostic Steps

#### 1. 运行诊断工具 | Run Diagnostic Tool

```bash
./deploy/diagnose.sh
```

此脚本将：
- 测试到 SMTP 服务器的网络连接
- 检查端口可访问性
- 提供针对性的解决建议

#### 2. 手动测试网络连接 | Manual Network Testing

**测试 DNS 解析 | Test DNS Resolution:**
```bash
nslookup smtp.gmail.com
```

**测试端口连通性 | Test Port Connectivity:**
```bash
# 使用 netcat
nc -zv smtp.gmail.com 587

# 或使用 telnet
telnet smtp.gmail.com 587

# 或使用 curl
curl -v telnet://smtp.gmail.com:587
```

**检查防火墙规则 | Check Firewall Rules:**
```bash
# 查看出站规则
sudo iptables -L OUTPUT -n -v

# 查看所有规则
sudo iptables -L -n -v
```

#### 3. 检查配置文件 | Check Configuration

验证 `.env` 文件中的 SMTP 配置：

```bash
# 必需配置项
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
SMTP_USE_TLS=true

# 可选超时和重试配置
SMTP_TIMEOUT=30              # 连接超时（秒）
SMTP_RETRY_ATTEMPTS=3        # 重试次数
SMTP_RETRY_BASE_DELAY=2.0    # 基础延迟（秒）
```

---

## 网络诊断工具

### 诊断脚本功能 | Diagnostic Script Features

`./deploy/diagnose.sh` 提供：

1. **配置验证** - 检查 `.env` 文件中的配置完整性
2. **端口测试** - 测试 SMTP/IMAP 端口连通性
3. **模式感知诊断** - 根据 API/Email 模式提供不同建议
4. **详细错误报告** - 包含具体错误原因和解决方案

### 示例输出 | Sample Output

```
==========================================
  AI Mail Relay 网络诊断工具
==========================================

配置信息:
  IMAP: imap.gmail.com:993
  SMTP: smtp.gmail.com:587
  arXiv 获取模式: api

==========================================
端口连接测试
==========================================

测试 SMTP (smtp.gmail.com:587)
  ✓ 端口连接成功

==========================================
诊断结果
==========================================

✓ SMTP 端口连接正常 (API 模式不需要 IMAP)
```

---

## 常见错误代码

### TimeoutError [Errno 110]

**含义：** 服务器无法建立 TCP 连接

**可能原因：**
1. 防火墙阻止出站连接
2. 云服务商安全组未配置出站规则
3. 网络路由问题
4. SMTP 服务器不可达

**解决方案：**
```bash
# 1. 检查云服务商安全组
# 登录控制台 → 安全组 → 添加出站规则
# 协议: TCP, 端口: 587, 目标: 0.0.0.0/0

# 2. 调整超时设置
echo "SMTP_TIMEOUT=60" >> .env

# 3. 尝试使用其他端口
echo "SMTP_PORT=465" >> .env
echo "SMTP_USE_TLS=false" >> .env
```

### ConnectionRefusedError [Errno 111]

**含义：** 端口被阻止或服务未监听

**可能原因：**
1. 目标端口被防火墙主动拒绝
2. ISP 屏蔽 SMTP 端口
3. SMTP 服务器配置错误

**解决方案：**
```bash
# 1. 切换到 SSL 端口
SMTP_PORT=465
SMTP_USE_TLS=false

# 2. 使用 VPN 或代理
# (如果 ISP 封锁端口)

# 3. 考虑使用第三方 SMTP 服务
# SendGrid, Mailgun, Amazon SES 等
```

### SMTPAuthenticationError

**含义：** 认证失败

**可能原因：**
1. 用户名或密码错误
2. Gmail 未使用应用专用密码
3. 账户启用了 2FA 但未生成应用密码

**解决方案：**
```bash
# Gmail 用户：生成应用专用密码
# 1. 访问 https://myaccount.google.com/apppasswords
# 2. 选择 "邮件" 和 "其他设备"
# 3. 生成密码并复制到 .env
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
```

### SMTPException (General)

**含义：** SMTP 协议错误

**可能原因：**
1. TLS/SSL 模式配置错误
2. 端口与加密模式不匹配

**解决方案：**
```bash
# 端口 587 使用 STARTTLS
SMTP_PORT=587
SMTP_USE_TLS=true

# 端口 465 使用 SSL
SMTP_PORT=465
SMTP_USE_TLS=false

# 端口 25 (不推荐，通常被封锁)
SMTP_PORT=25
SMTP_USE_TLS=false
```

---

## Gmail 特定问题

### 应用专用密码 | App-Specific Passwords

Gmail 要求使用应用专用密码而非账户密码。

**设置步骤：**

1. **启用两步验证**
   - 访问 https://myaccount.google.com/security
   - 启用"两步验证"

2. **生成应用密码**
   - 访问 https://myaccount.google.com/apppasswords
   - 选择应用：邮件
   - 选择设备：其他（自定义名称）
   - 生成密码

3. **更新配置**
   ```bash
   # 使用生成的 16 位密码（含空格）
   SMTP_PASSWORD=xxxx xxxx xxxx xxxx
   ```

### "不够安全的应用"访问

如果看到此错误，说明您的 Google 账户设置阻止了应用访问。

**解决方案：**
- **推荐：** 使用应用专用密码（见上文）
- **不推荐：** 启用"不够安全的应用"访问（Google 已逐步停止支持）

---

## 云服务器配置

### 阿里云 | Alibaba Cloud

**安全组配置：**

1. 登录阿里云控制台
2. 导航到 "云服务器 ECS" → "安全组"
3. 选择实例的安全组
4. 点击"配置规则" → "出方向"
5. 添加规则：
   - 协议类型: TCP
   - 端口范围: 587/tcp (或 465/tcp)
   - 授权对象: 0.0.0.0/0
   - 优先级: 1
   - 操作: 允许

**命令行配置：**
```bash
# 使用阿里云 CLI
aliyun ecs AuthorizeSecurityGroupEgress \
  --SecurityGroupId sg-xxxxx \
  --IpProtocol tcp \
  --PortRange 587/587 \
  --DestCidrIp 0.0.0.0/0
```

### 腾讯云 | Tencent Cloud

**安全组配置：**

1. 登录腾讯云控制台
2. 导航到 "云服务器" → "安全组"
3. 选择实例关联的安全组
4. 点击"修改规则" → "出站规则"
5. 添加规则：
   - 类型: 自定义
   - 协议端口: TCP:587
   - 来源: 0.0.0.0/0
   - 策略: 允许

### AWS (Amazon Web Services)

**Security Group 配置：**

1. 登录 AWS Console
2. 导航到 EC2 → Security Groups
3. 选择实例的 Security Group
4. 点击 "Outbound rules" → "Edit outbound rules"
5. 添加规则：
   - Type: Custom TCP
   - Port range: 587
   - Destination: 0.0.0.0/0

**使用 AWS CLI：**
```bash
aws ec2 authorize-security-group-egress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 587 \
  --cidr 0.0.0.0/0
```

### 其他云提供商 | Other Cloud Providers

大多数云提供商默认限制出站 SMTP 端口以防止垃圾邮件。查找"安全组"、"防火墙规则"或"网络 ACL"设置。

---

## 超时和重试配置

### 配置参数 | Configuration Parameters

应用程序提供以下可调参数来处理网络不稳定：

```bash
# .env 文件配置

# 连接超时（秒）
# 默认: 30
# 建议范围: 10-60
SMTP_TIMEOUT=30

# 重试次数
# 默认: 3
# 建议范围: 0-5
SMTP_RETRY_ATTEMPTS=3

# 基础重试延迟（秒）
# 默认: 2.0
# 建议范围: 1.0-5.0
SMTP_RETRY_BASE_DELAY=2.0
```

### 重试策略 | Retry Strategy

应用程序使用**指数退避**策略：

```
尝试 1: 立即
尝试 2: 等待 base_delay * 2^0 = 2.0 秒
尝试 3: 等待 base_delay * 2^1 = 4.0 秒
尝试 4: 等待 base_delay * 2^2 = 8.0 秒
```

### 智能错误处理 | Smart Error Handling

**可重试错误：** 自动重试
- 网络超时 (`socket.timeout`, `TimeoutError`)
- 网络错误 (`OSError`)
- 临时 SMTP 错误 (`SMTPException`)

**不可重试错误：** 立即失败
- 认证失败 (`SMTPAuthenticationError`)

---

## 日志分析

### 启用调试日志 | Enable Debug Logging

```bash
ai-mail-relay --log-level DEBUG
```

### 日志文件位置 | Log File Location

```
logs/run_YYYY-MM-DD_HH-MM-SS.log
```

### 关键日志模式 | Key Log Patterns

**成功连接：**
```
INFO [ai_mail_relay.mail_sender] Sending digest email with 100 papers
INFO [ai_mail_relay.mail_sender] Email sent successfully
```

**连接超时：**
```
WARNING [ai_mail_relay.mail_sender] SMTP connection timeout (attempt 1/4): [Errno 110] Connection timed out
INFO [ai_mail_relay.mail_sender] Retrying in 2.0 seconds...
```

**认证失败：**
```
ERROR [ai_mail_relay.mail_sender] SMTP authentication failed: (535, b'5.7.8 Username and Password not accepted')
```

**最终失败：**
```
ERROR [ai_mail_relay.mail_sender] Failed to send email after 4 attempts. Last error: [Errno 110] Connection timed out
ERROR [root] Failed to complete mail relay run
```

---

## 替代方案

### 使用 API 模式避免 IMAP 问题

如果只有 IMAP 连接问题：

```bash
# .env 文件
ARXIV_FETCH_MODE=api
```

API 模式直接从 arXiv API 获取论文，不需要 IMAP 连接。

### 使用第三方 SMTP 服务

如果 Gmail SMTP 被封锁，考虑使用专业邮件发送服务：

**SendGrid:**
```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_USE_TLS=true
```

**Mailgun:**
```bash
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@your-domain.mailgun.org
SMTP_PASSWORD=your-mailgun-password
SMTP_USE_TLS=true
```

**Amazon SES:**
```bash
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=your-ses-smtp-username
SMTP_PASSWORD=your-ses-smtp-password
SMTP_USE_TLS=true
```

---

## 仍然有问题？| Still Having Issues?

1. **检查完整配置**
   ```bash
   cat .env | grep -E "^SMTP_|^MAIL_"
   ```

2. **从不同网络测试**
   - 排除 ISP 级别的封锁

3. **查看完整日志**
   ```bash
   tail -f logs/run_*.log
   ```

4. **提交问题报告**
   - 包含匿名化的日志
   - 描述网络环境（云提供商、地区）
   - 运行 `./deploy/diagnose.sh` 的输出

---

## 相关文档 | Related Documentation

- [配置参考](configuration.md) - 所有配置选项的详细说明
- [README](../README.md) - 项目概述和快速开始
- [CLAUDE.md](../CLAUDE.md) - 开发者指南和架构说明
