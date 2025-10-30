# 故障排查指南

本文档帮助你快速诊断和解决 AI Mail Relay 运行中的常见问题。

---

## 🔍 快速诊断

### 运行诊断脚本

```bash
cd ~/project/AI_mail_relay_app
chmod +x deploy/diagnose.sh
./deploy/diagnose.sh
```

这将自动检测：
- ✅ IMAP 端口连接（993）
- ✅ SMTP 端口连接（587）
- ✅ 网络连通性

---

## ❌ 常见错误及解决方案

### 1. **Connection timed out (连接超时)**

**错误信息**:
```
TimeoutError: [Errno 110] Connection timed out
```

**原因**: 服务器无法连接到 Gmail IMAP/SMTP 服务器

**解决方案**:

#### 方案 A: 检查云服务商安全组（最常见）

**阿里云 ECS:**
1. 登录阿里云控制台
2. 进入 `云服务器 ECS` → `实例`
3. 点击实例 → `更多` → `网络和安全组` → `安全组配置`
4. 点击`配置规则` → `出方向`
5. 添加规则:
   - 授权策略: 允许
   - 优先级: 1
   - 协议类型: TCP
   - 端口范围: 993/TCP (IMAP) 和 587/TCP (SMTP)
   - 授权对象: 0.0.0.0/0

**腾讯云:**
1. 登录腾讯云控制台
2. 进入`云服务器` → `安全组`
3. 选择实例的安全组 → `添加规则`
4. 出站规则:
   - 类型: 自定义
   - 端口: 993, 587
   - 源: 0.0.0.0/0

**AWS EC2:**
1. EC2 控制台 → Security Groups
2. 选择实例的安全组 → Outbound Rules
3. Add Rule:
   - Type: Custom TCP
   - Port: 993, 587
   - Destination: 0.0.0.0/0

#### 方案 B: 检查服务器防火墙

```bash
# 查看防火墙规则
sudo iptables -L OUTPUT -n -v

# 如果有限制，允许出站连接
sudo iptables -A OUTPUT -p tcp --dport 993 -j ACCEPT
sudo iptables -A OUTPUT -p tcp --dport 587 -j ACCEPT

# 保存规则
sudo iptables-save > /etc/iptables/rules.v4
```

#### 方案 C: 测试连接

```bash
# 测试 IMAP 连接
telnet imap.gmail.com 993
# 或
timeout 10 python3 -c "import socket; s=socket.socket(); s.settimeout(10); s.connect(('imap.gmail.com', 993)); print('连接成功')"

# 测试 SMTP 连接
telnet smtp.gmail.com 587
```

---

### 2. **AUTHENTICATIONFAILED (认证失败)**

**错误信息**:
```
imaplib.IMAP4.error: b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)'
```

**原因**: Gmail 账号密码错误或未使用应用专用密码

**解决方案**:

#### Gmail 用户（必须）:

1. **启用两步验证**
   - 访问: https://myaccount.google.com/security
   - 找到"两步验证"并启用

2. **生成应用专用密码**
   - 访问: https://myaccount.google.com/apppasswords
   - 应用选择: `邮件`
   - 设备选择: `其他（自定义名称）`
   - 输入名称: `AI Mail Relay`
   - 点击`生成`
   - 复制 16 位密码（去掉空格）

3. **更新 .env 文件**
   ```bash
   vim ~/project/AI_mail_relay_app/.env
   ```

   修改:
   ```env
   IMAP_PASSWORD=你的16位应用专用密码（无空格）
   SMTP_PASSWORD=你的16位应用专用密码（无空格）
   ```

4. **测试**
   ```bash
   ./deploy/run.sh
   ```

---

### 3. **No relevant arXiv emails found (未找到邮件)**

**日志输出**:
```
INFO [ai_mail_relay.pipeline] No relevant arXiv emails found, skipping email sending
```

**状态**: ✅ 这是正常的！不是错误。

**含义**:
- 今天没有收到新的 arXiv 邮件
- 或所有邮件已经被处理过（标记为已读）

**处理**:
- 不需要任何操作
- 系统会在下次运行时继续检查
- **不会发送空邮件**

---

### 4. **No AI-related papers after filtering (没有AI论文)**

**日志输出**:
```
INFO [ai_mail_relay.pipeline] No AI-related papers after filtering, skipping email sending
```

**状态**: ✅ 这是正常的！不是错误。

**含义**:
- 今天的 arXiv 邮件中没有符合过滤条件的 AI 论文

**处理**:
- 检查 `.env` 中的过滤条件是否太严格:
  ```env
  ARXIV_ALLOWED_CATEGORIES=cs.AI,cs.LG,cs.CV,cs.CL,cs.RO,cs.IR,stat.ML,eess.AS
  ```
- 可以添加更多类别或放宽关键词过滤

---

### 5. **Configuration error (配置错误)**

**错误信息**:
```
ERROR [root] Configuration error: Missing required IMAP configuration
```

**原因**: `.env` 文件缺少必需的配置项

**解决方案**:

```bash
# 检查配置文件
cat ~/project/AI_mail_relay_app/.env

# 必须包含以下项:
IMAP_HOST=imap.gmail.com
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_app_password

SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password

MAIL_FROM_ADDRESS=your_email@gmail.com
MAIL_TO_ADDRESS=your_email@gmail.com

LLM_API_KEY=your_llm_api_key
```

如果缺少配置，从模板复制:
```bash
cp .env.example .env
vim .env  # 填写实际配置
```

---

### 6. **LLM API 错误**

**错误信息**:
```
LLMProviderError: LLM request failed
```

**可能原因**:
- API 密钥无效
- API 余额不足
- 网络连接问题

**解决方案**:

1. **检查 API 密钥**
   ```bash
   grep "LLM_API_KEY" .env
   ```

2. **测试 API 连接**
   ```bash
   # DeepSeek
   curl -X POST https://api.deepseek.com/v1/chat/completions \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"test"}]}'
   ```

3. **检查余额**
   - DeepSeek: https://platform.deepseek.com/usage
   - OpenAI: https://platform.openai.com/usage

---

## 🔧 调试技巧

### 查看详细日志

```bash
# 查看最新运行日志
ls -lt logs/run_*.log | head -1 | xargs cat

# 实时查看 Cron 日志
tail -f logs/cron.log

# 查看今天的所有运行记录
ls logs/run_$(date +%Y-%m-%d)_*.log
```

### 手动测试运行

```bash
# 带详细输出
./deploy/run.sh

# 或直接运行 Python
source venv/bin/activate
python -m ai_mail_relay.main --log-level DEBUG
```

### 测试邮件连接

创建测试脚本 `test_email.py`:
```python
import imaplib
import smtplib
from dotenv import load_dotenv
import os

load_dotenv()

# 测试 IMAP
try:
    imap = imaplib.IMAP4_SSL(os.getenv('IMAP_HOST'), int(os.getenv('IMAP_PORT', 993)))
    imap.login(os.getenv('IMAP_USER'), os.getenv('IMAP_PASSWORD'))
    print("✓ IMAP 连接成功")
    imap.logout()
except Exception as e:
    print(f"✗ IMAP 连接失败: {e}")

# 测试 SMTP
try:
    smtp = smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT', 587)))
    smtp.starttls()
    smtp.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD'))
    print("✓ SMTP 连接成功")
    smtp.quit()
except Exception as e:
    print(f"✗ SMTP 连接失败: {e}")
```

运行:
```bash
source venv/bin/activate
python test_email.py
```

---

## 📞 获取帮助

### 检查清单

在寻求帮助前，请确认:

- [ ] 运行了 `./deploy/diagnose.sh`
- [ ] 检查了 `.env` 文件配置
- [ ] Gmail 用户使用了应用专用密码
- [ ] 查看了最新的日志文件
- [ ] 尝试了手动运行 `./deploy/run.sh`
- [ ] 检查了云服务商安全组设置

### 收集诊断信息

```bash
# 生成诊断报告
./deploy/diagnose.sh > diagnostic_report.txt
tail -100 logs/cron.log >> diagnostic_report.txt
cat .env | grep -v "PASSWORD\|API_KEY" >> diagnostic_report.txt
```

---

## 🎯 快速参考

### 重启定时任务

```bash
# 查看当前任务
crontab -l

# 重新设置
./deploy/setup_cron.sh
```

### 更新代码

```bash
cd ~/project/AI_mail_relay_app
git pull
source venv/bin/activate
pip install -e .
```

### 清理日志

```bash
# 删除 30 天前的日志
find logs -name "run_*.log" -mtime +30 -delete

# 删除所有日志
rm -f logs/*.log
```

---

**提示**: 大多数问题都与网络连接和邮箱认证有关。先运行诊断脚本！
