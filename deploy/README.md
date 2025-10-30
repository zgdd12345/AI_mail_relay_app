# Deploy 目录说明

本目录包含所有服务器部署相关的脚本文件。

## 📁 文件说明

### `deploy.sh`
**一键部署脚本** - 自动完成环境配置

功能：
- ✅ 检查 Python 版本
- ✅ 创建虚拟环境
- ✅ 安装所有依赖
- ✅ 生成 `.env` 配置文件
- ✅ 创建日志目录
- ✅ 测试程序运行

使用：
```bash
./deploy/deploy.sh
```

### `run.sh`
**运行脚本** - 执行程序并记录日志

功能：
- 激活虚拟环境
- 设置北京时间时区
- 运行主程序
- 记录详细日志
- 自动清理旧日志

使用：
```bash
# 手动运行
./deploy/run.sh

# Cron 定时运行（自动）
```

### `setup_cron.sh`
**Cron 定时任务设置脚本** - 配置自动运行时间

功能：
- 交互式设置运行时间
- 自动生成 Cron 表达式
- 备份现有 Cron 任务
- 添加新的定时任务

使用：
```bash
./deploy/setup_cron.sh

# 按提示输入时间，例如:
# 11:00,12:00,13:00  (默认值)
# 09:00,18:00        (自定义)
```

## 🚀 快速部署流程

### 第 1 步：部署环境
```bash
./deploy/deploy.sh
```

### 第 2 步：配置参数
```bash
vim .env  # 填写邮箱和 API 密钥
```

### 第 3 步：测试运行
```bash
./deploy/run.sh
```

### 第 4 步：设置定时任务
```bash
./deploy/setup_cron.sh
```

## 📊 日志管理

### 日志文件位置
```
../logs/
├── cron.log                      # Cron 任务总日志
└── run_2025-10-30_11-00-00.log  # 单次运行详细日志
```

### 查看日志
```bash
# 实时查看
tail -f ../logs/cron.log

# 查看最新一次运行
ls -t ../logs/run_*.log | head -1 | xargs cat

# 查看今天的日志
ls ../logs/run_$(date +%Y-%m-%d)_*.log
```

### 日志自动清理
- 程序运行时自动删除 30 天前的日志
- 手动清理: `find ../logs -name "run_*.log" -mtime +30 -delete`

## ⚙️ Cron 时间配置示例

```bash
# 每天特定时间运行
0 11 * * *   # 每天 11:00
30 14 * * *  # 每天 14:30

# 多个时间点
0 9,14,18 * * *   # 每天 09:00, 14:00, 18:00

# 工作日运行
0 9 * * 1-5   # 工作日 09:00

# 每隔几小时
0 */6 * * *   # 每 6 小时

# 特定日期
0 9 1 * *     # 每月 1 号 09:00
```

## 🔧 常用运维命令

### 查看 Cron 任务
```bash
crontab -l
```

### 修改运行时间
```bash
# 重新运行设置脚本
./deploy/setup_cron.sh

# 或手动编辑
crontab -e
```

### 停止定时任务
```bash
crontab -r  # 删除所有任务

# 或编辑并注释掉相关行
crontab -e
```

### 检查程序状态
```bash
# 查看最近的运行记录
tail -20 ../logs/cron.log

# 检查是否有错误
grep -i error ../logs/cron.log
```

## 📝 注意事项

1. **时区设置**: 脚本自动设置 `TZ=Asia/Shanghai`，确保北京时间运行
2. **权限**: 确保脚本可执行 (`chmod +x *.sh`)
3. **路径**: Cron 使用绝对路径，脚本会自动处理
4. **日志**: 定期检查日志文件，确保程序正常运行
5. **环境**: 虚拟环境必须存在，否则无法运行

## 🆘 故障排查

### 问题：Cron 任务未执行

1. 检查 Cron 服务状态
```bash
# Linux
sudo systemctl status cron

# macOS
launchctl list | grep cron
```

2. 查看系统日志
```bash
# Linux
grep CRON /var/log/syslog

# macOS
log show --predicate 'process == "cron"' --last 1h
```

### 问题：程序运行失败

1. 查看详细日志
```bash
cat ../logs/cron.log
```

2. 手动测试
```bash
./deploy/run.sh
```

3. 检查配置
```bash
cat ../.env
```

## 📚 更多信息

- **完整部署文档**: [../DEPLOY.md](../DEPLOY.md)
- **代码架构说明**: [../CLAUDE.md](../CLAUDE.md)
- **功能说明**: [../README.md](../README.md)
