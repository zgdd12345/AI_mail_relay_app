#!/bin/bash
# 网络连接诊断脚本 - 检查 IMAP/SMTP 连接

echo "=========================================="
echo "  AI Mail Relay 网络诊断工具"
echo "=========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

# 检查 .env 文件
if [ ! -f "$ENV_FILE" ]; then
    echo "✗ 错误: .env 文件不存在"
    echo "请先运行: ./deploy/deploy.sh"
    exit 1
fi

# 读取配置
IMAP_HOST=$(grep "^IMAP_HOST=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ')
IMAP_PORT=$(grep "^IMAP_PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ')
SMTP_HOST=$(grep "^SMTP_HOST=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ')
SMTP_PORT=$(grep "^SMTP_PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ')

IMAP_PORT=${IMAP_PORT:-993}
SMTP_PORT=${SMTP_PORT:-587}

echo "配置信息:"
echo "  IMAP: $IMAP_HOST:$IMAP_PORT"
echo "  SMTP: $SMTP_HOST:$SMTP_PORT"
echo ""

# 测试端口连接
test_connection() {
    local host=$1
    local port=$2
    local name=$3

    echo "测试 $name ($host:$port)"

    # 使用 Python socket 测试（最可靠）
    if timeout 10 python3 -c "
import socket
import sys
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect(('$host', $port))
    s.close()
    print('  ✓ 端口连接成功')
    sys.exit(0)
except socket.timeout:
    print('  ✗ 连接超时 (防火墙可能阻止了此端口)')
    sys.exit(1)
except Exception as e:
    print(f'  ✗ 连接失败: {e}')
    sys.exit(1)
" 2>&1; then
        return 0
    else
        return 1
    fi
}

echo "=========================================="
echo "端口连接测试"
echo "=========================================="
echo ""

IMAP_OK=0
SMTP_OK=0

if test_connection "$IMAP_HOST" "$IMAP_PORT" "IMAP"; then
    IMAP_OK=1
fi
echo ""

if test_connection "$SMTP_HOST" "$SMTP_PORT" "SMTP"; then
    SMTP_OK=1
fi
echo ""

echo "=========================================="
echo "诊断结果"
echo "=========================================="
echo ""

if [ $IMAP_OK -eq 1 ] && [ $SMTP_OK -eq 1 ]; then
    echo "✓ 所有端口连接正常"
    echo ""
    echo "网络连接没有问题。如果程序仍然失败，请检查:"
    echo "  1. .env 文件中的邮箱账号和密码"
    echo "  2. Gmail 用户必须使用应用专用密码"
    echo "     访问: https://myaccount.google.com/apppasswords"
else
    echo "✗ 检测到网络连接问题"
    echo ""

    if [ $IMAP_OK -eq 0 ]; then
        echo "❌ IMAP 端口 $IMAP_PORT 无法访问"
        echo ""
        echo "可能的原因:"
        echo "  1. 服务器防火墙阻止了出站连接到端口 993"
        echo "  2. 云服务商安全组未开放出站规则"
        echo "  3. 网络提供商限制访问外部邮件服务器"
        echo ""
        echo "解决方案:"
        echo "  【阿里云/腾讯云/AWS 用户】"
        echo "  1. 登录云控制台"
        echo "  2. 进入 '安全组' 设置"
        echo "  3. 添加出站规则: 允许 TCP 端口 993"
        echo ""
        echo "  【检查本地防火墙】"
        echo "  sudo iptables -L OUTPUT -n -v"
        echo ""
    fi

    if [ $SMTP_OK -eq 0 ]; then
        echo "❌ SMTP 端口 $SMTP_PORT 无法访问"
        echo ""
        echo "可能的原因:"
        echo "  1. 服务器防火墙阻止了出站连接到端口 587"
        echo "  2. 云服务商限制 SMTP 端口（防止垃圾邮件）"
        echo "  3. 网络提供商屏蔽了邮件端口"
        echo ""
        echo "解决方案:"
        echo "  1. 检查云服务商安全组，允许出站到 TCP 587"
        echo "  2. 尝试使用端口 465 (SMTP over SSL)"
        echo "     修改 .env: SMTP_PORT=465"
        echo ""
    fi
fi

echo "=========================================="
echo ""
