# 服务器快速使用指南

在服务器上遇到问题？这份指南帮你快速解决。

---

## ⚡ 你遇到的错误

### 错误：Connection timed out

```
TimeoutError: [Errno 110] Connection timed out
```

**这是什么问题？**
服务器无法连接到 Gmail 的 IMAP 服务器（端口 993）。

**最可能的原因：**
云服务商的安全组阻止了出站连接。

---

## 🔧 立即解决（3 步）

### 第 1 步：运行诊断

```bash
cd ~/project/AI_mail_relay_app
chmod +x deploy/diagnose.sh
./deploy/diagnose.sh
```

这会告诉你具体是哪个端口无法访问。

### 第 2 步：配置安全组（最重要）

**如果你用的是阿里云：**

1. 登录 https://ecs.console.aliyun.com
2. 点击左侧 `实例与镜像` → `实例`
3. 找到你的服务器，点击右侧 `更多` → `网络和安全组` → `安全组配置`
4. 点击 `配置规则` → 切换到 `出方向` 标签
5. 点击 `添加规则`，填写：
   - **授权策略**: 允许
   - **协议类型**: TCP
   - **端口范围**: 993/993
   - **授权对象**: 0.0.0.0/0
   - 点击 `确定`
6. 再添加一条规则，端口改为 `587/587`（SMTP）

**如果你用的是腾讯云：**

1. 登录 https://console.cloud.tencent.com/cvm
2. 左侧菜单 → `安全组`
3. 找到你实例使用的安全组，点击 `修改规则`
4. 切换到 `出站规则` 标签
5. 点击 `添加规则`：
   - **类型**: 自定义
   - **来源**: 0.0.0.0/0
   - **协议端口**: TCP:993
   - 点击 `完成`
6. 再添加一条 TCP:587

**如果你用的是 AWS：**

1. EC2 控制台 → Security Groups
2. 选择实例的安全组
3. Outbound Rules → Edit outbound rules
4. Add rule:
   - Type: Custom TCP
   - Port: 993
   - Destination: 0.0.0.0/0
5. 再添加 587

### 第 3 步：重新测试

```bash
./deploy/diagnose.sh
```

应该会显示：
```
✓ 端口连接成功
```

然后运行：
```bash
./deploy/run.sh
```

---

## 📋 其他常见情况

### 情况 1：诊断通过，但还是失败

**可能原因**：Gmail 密码错误

Gmail **必须使用应用专用密码**，不能用账户密码！

**生成应用专用密码：**

1. 访问：https://myaccount.google.com/apppasswords
2. 选择 `邮件` 和 `其他设备`
3. 点击 `生成`
4. 复制 16 位密码（去掉空格）

**更新配置：**

```bash
vim ~/project/AI_mail_relay_app/.env
```

修改：
```env
IMAP_PASSWORD=你的16位密码（无空格）
SMTP_PASSWORD=你的16位密码（无空格）
```

保存后测试：
```bash
./deploy/run.sh
```

---

### 情况 2：显示 "No relevant arXiv emails found"

**这是正常的！** 不是错误。

含义：今天没有收到新的 arXiv 邮件。

**系统行为：**
- ✅ 不会发送空邮件
- ✅ 会在日志中记录
- ✅ 下次运行会继续检查

---

### 情况 3：显示 "No AI-related papers after filtering"

**这也是正常的！**

含义：今天的 arXiv 邮件中没有符合你过滤条件的 AI 论文。

**如果你想接收更多论文**，编辑配置：

```bash
vim ~/project/AI_mail_relay_app/.env
```

添加更多类别：
```env
ARXIV_ALLOWED_CATEGORIES=cs.AI,cs.LG,cs.CV,cs.CL,cs.RO,cs.IR,cs.NE,cs.MA,stat.ML,eess.AS
```

---

## 🔍 查看运行状态

### 查看最近的日志

```bash
cd ~/project/AI_mail_relay_app
tail -100 logs/cron.log
```

### 查看今天所有运行记录

```bash
ls logs/run_$(date +%Y-%m-%d)_*.log
```

### 查看最新一次运行的详细日志

```bash
ls -lt logs/run_*.log | head -1 | xargs cat
```

---

## ⏰ 管理定时任务

### 查看当前设置

```bash
crontab -l
```

### 修改运行时间

```bash
./deploy/setup_cron.sh
```

按提示输入新的时间，例如：
```
09:00,14:00,18:00
```

### 暂停定时任务

```bash
crontab -r
```

### 恢复定时任务

```bash
./deploy/setup_cron.sh
```

---

## 🆘 完整的故障排查

如果上面的方法都不行，查看完整文档：

```bash
cat ~/project/AI_mail_relay_app/TROUBLESHOOTING.md
```

或访问：
- 故障排查: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- 部署文档: [DEPLOY.md](DEPLOY.md)
- 项目说明: [README.md](README.md)

---

## 💡 记住

1. **连接超时** → 99% 是安全组问题，开放端口 993 和 587
2. **认证失败** → Gmail 必须用应用专用密码
3. **没有邮件** → 这是正常的，不用担心

运行诊断脚本可以快速定位问题！

```bash
./deploy/diagnose.sh
```
