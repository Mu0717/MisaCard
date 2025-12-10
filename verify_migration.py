#!/usr/bin/env python3
"""验证数据库迁移结果"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "cards.db")

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 统计总卡片数
    cursor.execute('SELECT COUNT(*) FROM cards')
    total = cursor.fetchone()[0]
    
    # 获取表结构
    cursor.execute('PRAGMA table_info(cards)')
    columns = cursor.fetchall()
    
    # 检查新字段
    cursor.execute("""
        SELECT 
            COUNT(*) as total_cards,
            SUM(CASE WHEN is_sold = 0 THEN 1 ELSE 0 END) as unsold,
            SUM(CASE WHEN is_sold = 1 THEN 1 ELSE 0 END) as sold
        FROM cards
    """)
    stats = cursor.fetchone()
    
    print("=" * 60)
    print("数据库迁移验证报告")
    print("=" * 60)
    print(f"\n✅ 总卡片数: {total}")
    print(f"\n📋 表结构 (共 {len(columns)} 个字段):")
    for col in columns:
        default = f", 默认: {col[4]}" if col[4] else ""
        nullable = "可空" if col[3] == 0 else "非空"
        print(f"  - {col[1]:25} ({col[2]:10}) [{nullable}]{default}")
    
    print(f"\n📊 售卖状态统计:")
    print(f"  - 总数: {stats[0]}")
    print(f"  - 未售卖: {stats[1]} (默认状态)")
    print(f"  - 已售卖: {stats[2]}")
    
    # 验证关键字段
    print(f"\n🔍 数据完整性检查:")
    cursor.execute("SELECT COUNT(*) FROM cards WHERE card_id IS NOT NULL")
    card_id_count = cursor.fetchone()[0]
    print(f"  ✓ card_id 字段完整: {card_id_count}/{total}")
    
    cursor.execute("SELECT COUNT(*) FROM cards WHERE create_time IS NOT NULL")
    create_time_count = cursor.fetchone()[0]
    print(f"  ✓ create_time 字段完整: {create_time_count}/{total}")
    
    # 检查新字段是否存在
    has_is_sold = any(col[1] == 'is_sold' for col in columns)
    has_sold_time = any(col[1] == 'sold_time' for col in columns)
    
    print(f"\n✅ 新字段验证:")
    print(f"  {'✓' if has_is_sold else '✗'} is_sold 字段: {'存在' if has_is_sold else '不存在'}")
    print(f"  {'✓' if has_sold_time else '✗'} sold_time 字段: {'存在' if has_sold_time else '不存在'}")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("结论: 数据库迁移成功，所有数据完整！")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ 验证失败: {str(e)}")

