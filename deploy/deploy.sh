#!/bin/bash
# AI Mail Relay 一键部署脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "  AI Mail Relay 部署脚本"
echo "=========================================="
echo ""

# 检查 Python 版本
echo "✓ 检查 Python 版本..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo "✗ 错误: 需要 Python 3.10 或更高版本 (当前: $PYTHON_VERSION)"
    exit 1
fi
echo "  Python 版本: $PYTHON_VERSION ✓"
echo ""

# 创建虚拟环境
echo "✓ 创建 Python 虚拟环境..."
cd "$PROJECT_DIR"

if [ -d "venv" ]; then
    echo "  虚拟环境已存在，跳过创建"
else
    python3 -m venv venv
    echo "  虚拟环境创建成功 ✓"
fi
echo ""

# 激活虚拟环境
echo "✓ 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "✓ 安装依赖包..."
pip install --upgrade pip -q
pip install -e . -q
echo "  依赖安装完成 ✓"
echo ""

# 检查配置文件
echo "✓ 检查配置文件..."
if [ ! -f ".env" ]; then
    echo "  警告: .env 文件不存在"
    echo "  正在从 .env.example 创建..."
    cp .env.example .env
    echo ""
    echo "  ⚠️  请编辑 .env 文件并填写实际配置！"
    echo "  配置文件路径: $PROJECT_DIR/.env"
    echo ""
    read -p "按 Enter 键继续（确认已配置 .env）..."
else
    echo "  .env 文件存在 ✓"
fi
echo ""

# 创建日志目录
echo "✓ 创建日志目录..."
mkdir -p logs
echo "  日志目录: $PROJECT_DIR/logs ✓"
echo ""

# 测试运行
echo "✓ 测试程序运行..."
if python -m ai_mail_relay.main --log-level INFO 2>&1 | head -5; then
    echo "  程序测试成功 ✓"
else
    echo "  ⚠️  程序测试遇到问题，请检查配置"
fi
echo ""

echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "下一步:"
echo "1. 编辑配置文件: $PROJECT_DIR/.env"
echo "2. 设置定时任务: cd deploy && ./setup_cron.sh"
echo "3. 手动运行测试: ./deploy/run.sh"
echo ""
