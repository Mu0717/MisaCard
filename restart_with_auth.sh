#!/bin/bash
# 重启服务脚本（带鉴权功能）

echo "============================================================"
echo "MisaCard Manager - 重启服务（鉴权功能）"
echo "============================================================"
echo ""

# 1. 检查并安装依赖
echo "[1/3] 检查依赖包..."
if pip show python-jose > /dev/null 2>&1; then
    echo "  ✓ python-jose 已安装"
else
    echo "  正在安装 python-jose..."
    pip install python-jose[cryptography]
    if [ $? -eq 0 ]; then
        echo "  ✓ python-jose 安装成功"
    else
        echo "  ✗ python-jose 安装失败"
        exit 1
    fi
fi

echo ""

# 2. 验证配置
echo "[2/3] 验证配置..."

if [ -f ".env" ]; then
    echo "  ✓ 找到 .env 文件"
else
    echo "  ⚠ 未找到 .env 文件，将使用默认配置"
    echo "  默认密码: 003717"
fi

echo ""

# 3. 启动服务
echo "[3/3] 启动服务..."
echo ""
echo "============================================================"
echo "服务信息:"
echo "  - 地址: http://0.0.0.0:8000"
echo "  - API 文档: http://localhost:8000/docs"
echo "  - 默认密码: 003717"
echo ""
echo "功能权限:"
echo "  ✓ 无需密码: 查询、激活"
echo "  ✗ 需要密码: 其他所有功能"
echo "============================================================"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 启动 uvicorn
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
