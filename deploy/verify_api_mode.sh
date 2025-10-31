#!/bin/bash
# API 模式部署验证脚本
# 用于确保服务器上 API 模式可以正常运行

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         API 模式部署验证                                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

cd "$PROJECT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 计数器
PASSED=0
FAILED=0
WARNINGS=0

# 检查函数
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

echo "1. 检查 Python 环境"
echo "────────────────────────────────────────────────────────────────"

# 检查虚拟环境
if [ -d "venv" ]; then
    check_pass "虚拟环境存在"
    source venv/bin/activate
else
    check_fail "虚拟环境不存在，请先运行 ./deploy/deploy.sh"
    exit 1
fi

# 检查 Python 版本
PYTHON_VERSION=$(python --version 2>&1 | grep -oP '\d+\.\d+')
if [ "$(echo "$PYTHON_VERSION >= 3.10" | bc)" -eq 1 ]; then
    check_pass "Python 版本: $(python --version)"
else
    check_fail "Python 版本过低: $(python --version)，需要 >= 3.10"
fi

# 检查依赖
if python -c "import httpx" 2>/dev/null; then
    check_pass "httpx 已安装"
else
    check_fail "httpx 未安装，请运行: pip install -e ."
fi

echo ""
echo "2. 检查配置文件"
echo "────────────────────────────────────────────────────────────────"

# 检查 .env 文件
if [ -f ".env" ]; then
    check_pass ".env 文件存在"

    # 检查关键配置
    if grep -q "^ARXIV_FETCH_MODE=api" .env; then
        check_pass "API 模式已启用"
    else
        check_warn "API 模式未启用，当前可能使用邮箱模式"
    fi

    # 检查 SMTP 配置（API 模式仍需要发送邮件）
    if grep -q "^SMTP_HOST=" .env && grep -q "^SMTP_USER=" .env; then
        check_pass "SMTP 配置存在"
    else
        check_fail "SMTP 配置缺失，API 模式仍需 SMTP 发送邮件"
    fi

    # 检查 LLM 配置
    if grep -q "^LLM_API_KEY=" .env || grep -q "^OPENAI_API_KEY=" .env; then
        check_pass "LLM API 密钥已配置"
    else
        check_fail "LLM API 密钥缺失"
    fi

else
    check_fail ".env 文件不存在"
fi

echo ""
echo "3. 检查网络连接"
echo "────────────────────────────────────────────────────────────────"

# 检查 DNS 解析
if host export.arxiv.org >/dev/null 2>&1; then
    check_pass "DNS 解析正常 (export.arxiv.org)"
else
    check_fail "DNS 解析失败"
fi

# 检查 arXiv API 连接
if curl -s --connect-timeout 10 https://export.arxiv.org/api/query?search_query=cat:cs.AI\&max_results=1 >/dev/null; then
    check_pass "arXiv API 连接正常"
else
    check_fail "无法连接 arXiv API，请检查防火墙设置"
fi

# 检查 SMTP 连接
SMTP_HOST=$(grep "^SMTP_HOST=" .env 2>/dev/null | cut -d'=' -f2)
SMTP_PORT=$(grep "^SMTP_PORT=" .env 2>/dev/null | cut -d'=' -f2)
SMTP_PORT=${SMTP_PORT:-587}

if [ -n "$SMTP_HOST" ]; then
    if timeout 5 bash -c "echo > /dev/tcp/$SMTP_HOST/$SMTP_PORT" 2>/dev/null; then
        check_pass "SMTP 连接正常 ($SMTP_HOST:$SMTP_PORT)"
    else
        check_fail "无法连接 SMTP 服务器 ($SMTP_HOST:$SMTP_PORT)"
    fi
fi

echo ""
echo "4. 测试 API 模式功能"
echo "────────────────────────────────────────────────────────────────"

# 运行快速测试
echo "正在运行 API 模式测试（跳过 LLM 和邮件发送）..."
if python test.py --no-llm --no-email --papers 2 2>&1 | grep -q "✅ 所有测试完成"; then
    check_pass "API 模式功能测试通过"
else
    check_fail "API 模式功能测试失败"
fi

echo ""
echo "5. 检查日志目录"
echo "────────────────────────────────────────────────────────────────"

if [ -d "logs" ]; then
    check_pass "日志目录存在"

    # 检查日志权限
    if [ -w "logs" ]; then
        check_pass "日志目录可写"
    else
        check_fail "日志目录不可写"
    fi
else
    mkdir -p logs
    check_pass "已创建日志目录"
fi

echo ""
echo "6. 检查 Cron 配置（如果已设置）"
echo "────────────────────────────────────────────────────────────────"

if crontab -l 2>/dev/null | grep -q "ai-mail-relay\|run.sh"; then
    check_pass "Cron 任务已配置"
    echo "当前 Cron 配置："
    crontab -l | grep "ai-mail-relay\|run.sh" | sed 's/^/  /'
else
    check_warn "Cron 任务未配置，如需定时运行请执行: ./deploy/setup_cron.sh"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "验证结果汇总"
echo "════════════════════════════════════════════════════════════════"
echo -e "${GREEN}通过: $PASSED${NC}"
echo -e "${RED}失败: $FAILED${NC}"
echo -e "${YELLOW}警告: $WARNINGS${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有关键检查通过，API 模式可以在服务器上稳定运行！${NC}"
    echo ""
    echo "建议："
    echo "  1. 运行完整测试: python test.py --papers 3"
    echo "  2. 设置定时任务: ./deploy/setup_cron.sh"
    echo "  3. 监控日志: tail -f logs/cron.log"
    exit 0
else
    echo -e "${RED}✗ 发现 $FAILED 个问题，请修复后再部署${NC}"
    echo ""
    echo "故障排查："
    echo "  1. 运行诊断: ./deploy/diagnose.sh"
    echo "  2. 查看文档: cat DEPLOY.md"
    echo "  3. 检查配置: cat .env"
    exit 1
fi
