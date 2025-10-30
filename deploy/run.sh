#!/bin/bash
# AI Mail Relay 运行脚本（带日志）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 设置环境
cd "$PROJECT_DIR"
export TZ=Asia/Shanghai

# 激活虚拟环境
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "错误: 虚拟环境不存在，请先运行 deploy.sh"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 生成日志文件名（带时间戳）
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="logs/run_${TIMESTAMP}.log"

# 运行程序并记录日志
echo "========================================" | tee -a "$LOG_FILE"
echo "AI Mail Relay 运行于: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

python -m ai_mail_relay.main --log-level INFO 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=$?

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "运行完成，退出代码: $EXIT_CODE" | tee -a "$LOG_FILE"
echo "日志文件: $LOG_FILE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 清理旧日志（保留最近 30 天）
find logs -name "run_*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
