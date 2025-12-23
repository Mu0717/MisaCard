#!/bin/bash
set -e

echo "=========================================="
echo "MisaCard Manager - 容器启动"
echo "=========================================="

# 检查数据库是否存在
DB_FILE="/app/data/cards.db"
if [ -f "$DB_FILE" ]; then
    echo "✓ 发现现有数据库: $DB_FILE"
    
    # 运行数据库迁移
    echo ""
    echo "==> 检查并执行数据库迁移..."
    
    # 检查 is_sold 字段是否存在
    HAS_SOLD_FIELD=$(python3 -c "
import sqlite3
import os
try:
    conn = sqlite3.connect('$DB_FILE')
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(cards)')
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    print('yes' if 'is_sold' in columns else 'no')
except Exception as e:
    print('error')
" 2>/dev/null || echo "error")

    if [ "$HAS_SOLD_FIELD" = "no" ]; then
        echo "! 检测到需要迁移: 添加售卖状态字段"
        if [ -f "migrate_add_sold_field.py" ]; then
            echo "==> 运行迁移脚本..."
            python3 migrate_add_sold_field.py
            echo "✓ 迁移完成"
        else
            echo "⚠ 警告: 找不到迁移脚本，但数据库缺少字段"
            echo "⚠ 应用可能无法正常运行！"
        fi
    elif [ "$HAS_SOLD_FIELD" = "yes" ]; then
        echo "✓ 售卖状态字段已存在"
    else
        echo "⚠ 无法检查数据库结构(is_sold)，跳过该项检查"
    fi

    # 检查 is_external 字段是否存在
    HAS_EXTERNAL_FIELD=$(python3 -c "
import sqlite3
import os
try:
    conn = sqlite3.connect('$DB_FILE')
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(cards)')
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    print('yes' if 'is_external' in columns else 'no')
except Exception as e:
    print('error')
" 2>/dev/null || echo "error")

    if [ "$HAS_EXTERNAL_FIELD" = "no" ]; then
        echo "! 检测到需要迁移: 添加外部卡标识字段"
        if [ -f "migrate_add_external_field.py" ]; then
            echo "==> 运行迁移脚本..."
            python3 migrate_add_external_field.py
            echo "✓ 迁移完成"
        else
            echo "⚠ 警告: 找不到迁移脚本(migrate_add_external_field.py)，但数据库缺少字段"
        fi
    elif [ "$HAS_EXTERNAL_FIELD" = "yes" ]; then
        echo "✓ 外部卡标识字段已存在"
    fi
else
    echo "! 首次启动，将自动初始化数据库"
fi

echo ""
echo "=========================================="
echo "启动应用服务..."
echo "=========================================="
echo ""

# 启动应用
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

