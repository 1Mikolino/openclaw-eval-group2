#!/bin/bash
# 最简单的 Cookie 持久化 Bug 复现脚本
# 只需 bash + curl，自动关闭浏览器

set -e

echo "=== OpenClaw 浏览器 Cookie Bug 复现 ==="
echo ""

# 配置
COOKIE_PATH="$HOME/.openclaw/browser/openclaw/user-data/Default/Cookies"
NETWORK_COOKIE_PATH="$HOME/.openclaw/browser/openclaw/user-data/Default/Network/Cookies"
CDP_PORT=9222

# 清理函数 - 确保浏览器会被关闭
cleanup() {
    echo ""
    echo "🧹 正在清理: 关闭浏览器..."
    openclaw browser stop 2>/dev/null || true
    sleep 1
    echo "✅ 浏览器已关闭，资源已释放"
}
trap cleanup EXIT

# 步骤 1: 停止已有浏览器
echo "[1/4] 准备环境..."
if openclaw browser status 2>&1 | grep -q "running"; then
    echo "  - 停止已运行的浏览器..."
    openclaw browser stop
    sleep 2
fi

# 步骤 2: 启动浏览器
echo "[2/4] 启动 OpenClaw 托管浏览器..."
openclaw browser start
sleep 3

# 验证浏览器已启动
if ! curl -s http://localhost:$CDP_PORT/json/version > /dev/null 2>&1; then
    echo "❌ 浏览器启动失败"
    exit 1
fi
echo "  ✓ 浏览器已启动"

# 步骤 3: 检查 cookie 持久化
echo "[3/4] 检查 Cookie 持久化状态..."

# 打开一个测试页面（这会自动创建一些 cookie）
echo "  - 打开测试页面..."
TAB_INFO=$(curl -s "http://localhost:$CDP_PORT/json/new?about:blank")
TAB_ID=$(echo "$TAB_INFO" | grep -o '"id": "[^"]*"' | head -1 | cut -d'"' -f4)
echo "  ✓ 已打开测试标签页: $TAB_ID"

# 等待一下让浏览器初始化
sleep 2

# 检查 cookie 文件
echo ""
echo "检查 Cookie 数据库文件:"
echo "================================"

BUG_FOUND=false

# 检查旧的 Cookies 文件
if [ -f "$COOKIE_PATH" ]; then
    SIZE=$(ls -lh "$COOKIE_PATH" | awk '{print $5}')
    if [ -s "$COOKIE_PATH" ]; then
        echo "✓ 找到: $COOKIE_PATH ($SIZE)"
        # 尝试用 sqlite3 读取
        if command -v sqlite3 &> /dev/null; then
            COUNT=$(sqlite3 "$COOKIE_PATH" "SELECT COUNT(*) FROM cookies;" 2>/dev/null || echo "0")
            echo "  Cookie 数量: $COUNT"
            if [ "$COUNT" -gt 0 ]; then
                BUG_FOUND=false
            fi
        fi
    else
        echo "✗ 文件存在但为空: $COOKIE_PATH"
        BUG_FOUND=true
    fi
else
    echo "✗ 不存在: $COOKIE_PATH"
    BUG_FOUND=true
fi

# 检查新的 Network/Cookies 文件
if [ -f "$NETWORK_COOKIE_PATH" ]; then
    SIZE=$(ls -lh "$NETWORK_COOKIE_PATH" | awk '{print $5}')
    echo "✓ 找到: $NETWORK_COOKIE_PATH ($SIZE)"
else
    echo "✗ 不存在: $NETWORK_COOKIE_PATH"
fi

# 步骤 4: 输出结果
echo ""
echo "[4/4] 复现结果"
echo "================================"

if [ "$BUG_FOUND" = true ]; then
    echo "❌ BUG 已复现: Cookie 未持久化到磁盘！"
    echo ""
    echo "问题说明:"
    echo "  Chrome 通过 CDP 控制时，cookie 只保存在内存中"
    echo "  不会写入到磁盘的 SQLite 数据库"
    echo ""
    echo "证据:"
    echo "  - $COOKIE_PATH 不存在或为空"
    echo "  - $NETWORK_COOKIE_PATH 不存在"
    echo ""
    echo "影响:"
    echo "  - 浏览器重启后所有登录会话丢失"
    echo "  - 每次都需要重新登录"
    echo "  - 自动化任务无法保持会话"
else
    echo "✓ 未复现 bug (cookie 已持久化)"
fi

echo ""
echo "================================"
echo "浏览器将在脚本退出时自动关闭"
echo "不会持续占用 CPU/内存 ✅"

# 脚本结束时会自动调用 cleanup 函数
