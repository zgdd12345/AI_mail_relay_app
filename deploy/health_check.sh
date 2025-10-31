#!/bin/bash
# 健康检查脚本 - 用于监控 API 模式运行状态

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# 设置日志文件
HEALTH_LOG="logs/health_check.log"
mkdir -p logs

# 时间戳
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# 执行检查
check_arxiv_api() {
    if curl -s --connect-timeout 5 https://export.arxiv.org/api/query?search_query=cat:cs.AI\&max_results=1 >/dev/null 2>&1; then
        echo "[$TIMESTAMP] ✓ arXiv API 可访问" >> "$HEALTH_LOG"
        return 0
    else
        echo "[$TIMESTAMP] ✗ arXiv API 不可访问" >> "$HEALTH_LOG"
        return 1
    fi
}

check_smtp() {
    SMTP_HOST=$(grep "^SMTP_HOST=" .env 2>/dev/null | cut -d'=' -f2)
    SMTP_PORT=$(grep "^SMTP_PORT=" .env 2>/dev/null | cut -d'=' -f2)
    SMTP_PORT=${SMTP_PORT:-587}

    if [ -n "$SMTP_HOST" ]; then
        if timeout 5 bash -c "echo > /dev/tcp/$SMTP_HOST/$SMTP_PORT" 2>/dev/null; then
            echo "[$TIMESTAMP] ✓ SMTP 连接正常" >> "$HEALTH_LOG"
            return 0
        else
            echo "[$TIMESTAMP] ✗ SMTP 连接失败" >> "$HEALTH_LOG"
            return 1
        fi
    fi
    return 0
}

check_logs() {
    # 检查最近的运行日志
    LATEST_LOG=$(ls -t logs/run_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        LOG_TIME=$(stat -c %Y "$LATEST_LOG" 2>/dev/null || stat -f %m "$LATEST_LOG" 2>/dev/null)
        CURRENT_TIME=$(date +%s)
        AGE=$((CURRENT_TIME - LOG_TIME))

        # 如果最新日志超过 48 小时
        if [ $AGE -gt 172800 ]; then
            echo "[$TIMESTAMP] ⚠ 最新日志超过 48 小时: $LATEST_LOG" >> "$HEALTH_LOG"
            return 1
        else
            echo "[$TIMESTAMP] ✓ 日志正常更新" >> "$HEALTH_LOG"
            return 0
        fi
    else
        echo "[$TIMESTAMP] ⚠ 未找到运行日志" >> "$HEALTH_LOG"
        return 1
    fi
}

# 执行所有检查
FAILED=0

check_arxiv_api || ((FAILED++))
check_smtp || ((FAILED++))
check_logs || ((FAILED++))

# 汇总结果
if [ $FAILED -eq 0 ]; then
    echo "[$TIMESTAMP] ✓ 所有健康检查通过" >> "$HEALTH_LOG"
    exit 0
else
    echo "[$TIMESTAMP] ✗ $FAILED 项健康检查失败" >> "$HEALTH_LOG"
    exit 1
fi
