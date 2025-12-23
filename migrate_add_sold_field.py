#!/usr/bin/env python3
"""
数据库迁移脚本：添加售卖状态字段
为 cards 表添加 is_sold 和 sold_time 字段
"""
import sqlite3
import os

# 数据库文件路径
# 数据库文件路径
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "data", "cards.db")
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, "cards.db")


def migrate():
    """执行数据库迁移"""
    print(f"开始迁移数据库: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ 错误: 数据库文件不存在: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(cards)")
        columns = [row[1] for row in cursor.fetchall()]
        
        migrations_needed = []
        
        if 'is_sold' not in columns:
            migrations_needed.append("is_sold")
        
        if 'sold_time' not in columns:
            migrations_needed.append("sold_time")
        
        if not migrations_needed:
            print("✅ 数据库已是最新版本，无需迁移")
            conn.close()
            return True
        
        print(f"需要添加字段: {', '.join(migrations_needed)}")
        
        # 添加 is_sold 字段
        if 'is_sold' in migrations_needed:
            print("正在添加 is_sold 字段...")
            cursor.execute("""
                ALTER TABLE cards 
                ADD COLUMN is_sold BOOLEAN DEFAULT 0
            """)
            print("✓ is_sold 字段添加成功")
        
        # 添加 sold_time 字段
        if 'sold_time' in migrations_needed:
            print("正在添加 sold_time 字段...")
            cursor.execute("""
                ALTER TABLE cards 
                ADD COLUMN sold_time TIMESTAMP
            """)
            print("✓ sold_time 字段添加成功")
        
        conn.commit()
        
        # 验证迁移
        cursor.execute("PRAGMA table_info(cards)")
        columns_after = [row[1] for row in cursor.fetchall()]
        
        if 'is_sold' in columns_after and 'sold_time' in columns_after:
            print("\n✅ 数据库迁移完成！")
            print("新增字段:")
            print("  - is_sold (布尔值，默认 False)")
            print("  - sold_time (时间戳，默认 NULL)")
            conn.close()
            return True
        else:
            print("\n❌ 迁移验证失败")
            conn.close()
            return False
            
    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移工具：添加售卖状态字段")
    print("=" * 60)
    print()
    
    success = migrate()
    
    print()
    if success:
        print("🎉 迁移成功！现在可以重启应用程序。")
    else:
        print("⚠️  迁移失败，请检查错误信息。")
    print("=" * 60)

