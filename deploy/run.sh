#!/bin/bash
# AI Mail Relay 运行脚本（带日志和智能错误处理）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_VENV="$PROJECT_DIR/mailrelay"

# 设置环境
cd "$PROJECT_DIR"
export TZ=Asia/Shanghai
# 确保 src 在 PYTHONPATH 中，避免未安装可编辑模式时报模块缺失
export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"

# 激活虚拟环境（优先使用项目 mailrelay，若已在 Conda/virtualenv 中则跳过）
if [ -n "$VIRTUAL_ENV" ] || [ -n "$CONDA_PREFIX" ]; then
    echo "检测到已激活的 Python 环境，跳过项目 mailrelay 环境"
elif [ -f "$PROJECT_VENV/bin/activate" ]; then
    source "$PROJECT_VENV/bin/activate"
else
    echo "错误: mailrelay 虚拟环境不存在，请先运行 deploy.sh"
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

# 捕获输出并检查关键信息
OUTPUT=$(python -m ai_mail_relay.main --log-level INFO 2>&1)
EXIT_CODE=$?

# 输出到屏幕和日志
echo "$OUTPUT" | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 检测运行模式
MODE="未知"
if echo "$OUTPUT" | grep -q "Using arXiv API mode"; then
    MODE="API"
elif echo "$OUTPUT" | grep -q "Using email mode"; then
    MODE="邮箱"
fi

# 分析运行结果
if [ $EXIT_CODE -eq 0 ]; then
    # 检查是否跳过了邮件发送
    if echo "$OUTPUT" | grep -q "no-paper notification"; then
        echo "状态: 成功 (无论文，已发送提醒邮件)" | tee -a "$LOG_FILE"
        echo "模式: $MODE" | tee -a "$LOG_FILE"
        if echo "$OUTPUT" | grep -q "No papers found for"; then
            echo "原因: 未获取到论文数据" | tee -a "$LOG_FILE"
        elif echo "$OUTPUT" | grep -q "No AI-related papers after filtering"; then
            echo "原因: 过滤后没有 AI 相关论文" | tee -a "$LOG_FILE"
        elif echo "$OUTPUT" | grep -q "No unique papers after deduplication"; then
            echo "原因: 去重后没有唯一论文" | tee -a "$LOG_FILE"
        fi
    elif echo "$OUTPUT" | grep -q "skipping email sending"; then
        echo "状态: 成功 (无需发送邮件)" | tee -a "$LOG_FILE"
        echo "模式: $MODE" | tee -a "$LOG_FILE"
        if echo "$OUTPUT" | grep -q "No relevant arXiv emails found"; then
            echo "原因: 未找到相关 arXiv 邮件" | tee -a "$LOG_FILE"
        elif echo "$OUTPUT" | grep -q "No papers found\|No papers parsed"; then
            echo "原因: 未找到或解析论文" | tee -a "$LOG_FILE"
        elif echo "$OUTPUT" | grep -q "No AI-related papers"; then
            echo "原因: 过滤后没有 AI 相关论文" | tee -a "$LOG_FILE"
        elif echo "$OUTPUT" | grep -q "No unique papers"; then
            echo "原因: 去重后没有唯一论文" | tee -a "$LOG_FILE"
        fi
    elif echo "$OUTPUT" | grep -q "Successfully sent digest email"; then
        PAPER_COUNT=$(echo "$OUTPUT" | grep "Successfully sent digest email" | grep -oP '\d+(?= papers)' || echo "未知")
        echo "状态: 成功 (已发送 $PAPER_COUNT 篇论文摘要)" | tee -a "$LOG_FILE"
        echo "模式: $MODE" | tee -a "$LOG_FILE"
    else
        echo "状态: 成功" | tee -a "$LOG_FILE"
        echo "模式: $MODE" | tee -a "$LOG_FILE"
    fi
else
    # 检查具体错误类型
    echo "状态: 失败 (退出代码: $EXIT_CODE)" | tee -a "$LOG_FILE"
    echo "模式: $MODE" | tee -a "$LOG_FILE"

    if echo "$OUTPUT" | grep -q "Failed to fetch from arXiv API"; then
        echo "错误类型: arXiv API 访问失败" | tee -a "$LOG_FILE"
        echo "建议: 检查网络连接和防火墙设置" | tee -a "$LOG_FILE"
        echo "运行验证: ./deploy/verify_api_mode.sh" | tee -a "$LOG_FILE"
    elif echo "$OUTPUT" | grep -q "Connection timed out\|TimeoutError"; then
        echo "错误类型: 网络连接超时" | tee -a "$LOG_FILE"
        echo "建议: 检查防火墙和网络连接" | tee -a "$LOG_FILE"
        echo "运行诊断: ./deploy/diagnose.sh" | tee -a "$LOG_FILE"
    elif echo "$OUTPUT" | grep -q "AUTHENTICATIONFAILED\|Invalid credentials"; then
        echo "错误类型: 邮箱认证失败" | tee -a "$LOG_FILE"
        echo "建议: 检查 .env 中的邮箱密码 (Gmail 需要应用专用密码)" | tee -a "$LOG_FILE"
    elif echo "$OUTPUT" | grep -q "Configuration error"; then
        echo "错误类型: 配置错误" | tee -a "$LOG_FILE"
        echo "建议: 检查 .env 文件配置是否完整" | tee -a "$LOG_FILE"
    fi
fi

echo "日志文件: $LOG_FILE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 清理旧日志（保留最近 30 天）
find logs -name "run_*.log" -mtime +30 -delete 2>/dev/null || true

# 即使失败也返回 0，避免 cron 发送错误邮件
# 因为"没有邮件"不是真正的错误
if [ $EXIT_CODE -eq 0 ]; then
    exit 0
else
    # 记录错误但不影响 cron
    echo "注意: 程序执行遇到错误，但 cron 任务将继续运行" >> "$LOG_FILE"
    exit 0
fi
