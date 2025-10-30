#!/bin/bash
# 设置 Cron 定时任务脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RUN_SCRIPT="$PROJECT_DIR/deploy/run.sh"

echo "=========================================="
echo "  AI Mail Relay Cron 定时任务设置"
echo "=========================================="
echo ""

# 检查运行脚本是否存在
if [ ! -f "$RUN_SCRIPT" ]; then
    echo "✗ 错误: 运行脚本不存在: $RUN_SCRIPT"
    echo "请先运行 deploy.sh 进行部署"
    exit 1
fi

echo "项目目录: $PROJECT_DIR"
echo "运行脚本: $RUN_SCRIPT"
echo ""

# 默认运行时间（北京时间）
DEFAULT_TIMES="11:00,12:00,13:00"

echo "请设置定时运行时间（北京时间，24小时制）"
echo "格式: HH:MM,HH:MM,HH:MM"
echo "默认: $DEFAULT_TIMES (每天 11:00、12:00、13:00)"
echo ""
read -p "运行时间 [直接按 Enter 使用默认值]: " RUN_TIMES

# 使用默认值或用户输入
RUN_TIMES=${RUN_TIMES:-$DEFAULT_TIMES}

echo ""
echo "设置的运行时间: $RUN_TIMES"
echo ""

# 解析时间并生成 cron 表达式
CRON_ENTRIES=""
IFS=',' read -ra TIMES <<< "$RUN_TIMES"

for TIME in "${TIMES[@]}"; do
    # 去除空格
    TIME=$(echo "$TIME" | xargs)

    # 验证时间格式
    if [[ ! "$TIME" =~ ^([0-1][0-9]|2[0-3]):([0-5][0-9])$ ]]; then
        echo "✗ 错误: 无效的时间格式: $TIME"
        echo "请使用 HH:MM 格式（例如: 09:00）"
        exit 1
    fi

    # 分离小时和分钟
    HOUR=$(echo "$TIME" | cut -d: -f1)
    MINUTE=$(echo "$TIME" | cut -d: -f2)

    # 生成 cron 表达式（北京时间）
    # 格式: 分钟 小时 日 月 星期 命令
    CRON_LINE="$MINUTE $HOUR * * * cd $PROJECT_DIR && $RUN_SCRIPT >> $PROJECT_DIR/logs/cron.log 2>&1"
    CRON_ENTRIES="$CRON_ENTRIES$CRON_LINE"$'\n'

    echo "  ✓ $TIME -> cron: $MINUTE $HOUR * * *"
done

echo ""
echo "=========================================="
echo "  生成的 Cron 任务:"
echo "=========================================="
echo "$CRON_ENTRIES"
echo ""

# 备份现有 crontab
echo "✓ 备份现有 crontab..."
crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || true

# 移除旧的 AI Mail Relay 任务
echo "✓ 移除旧的 AI Mail Relay 任务..."
(crontab -l 2>/dev/null | grep -v "ai-mail-relay\|AI_mail_relay_app/deploy/run.sh") | crontab - 2>/dev/null || true

# 添加新任务
echo "✓ 添加新的 Cron 任务..."
(crontab -l 2>/dev/null; echo ""; echo "# AI Mail Relay - 自动生成，请勿手动编辑"; echo "$CRON_ENTRIES") | crontab -

echo ""
echo "=========================================="
echo "  Cron 任务设置成功！"
echo "=========================================="
echo ""
echo "当前的 Cron 任务列表:"
echo "------------------------------------------"
crontab -l | grep -A 10 "AI Mail Relay"
echo ""
echo "运行时间: $RUN_TIMES (北京时间)"
echo "日志文件: $PROJECT_DIR/logs/cron.log"
echo "运行日志: $PROJECT_DIR/logs/run_*.log"
echo ""
echo "管理 Cron 任务:"
echo "  - 查看任务: crontab -l"
echo "  - 编辑任务: crontab -e"
echo "  - 删除任务: crontab -r"
echo "  - 查看日志: tail -f $PROJECT_DIR/logs/cron.log"
echo ""
echo "注意: 请确保系统时区设置为 Asia/Shanghai (北京时间)"
echo "检查时区: timedatectl (Linux) 或 date (Mac)"
echo ""
