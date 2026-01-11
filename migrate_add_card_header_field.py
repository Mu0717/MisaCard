#!/usr/bin/env python3
"""
数据库迁移脚本：添加备注卡头字段
为 cards 表添加 card_header 字段
"""
import sqlite3
import os

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
        
        if 'card_header' not in columns:
            migrations_needed.append("card_header")
        
        if not migrations_needed:
            print("✅ 数据库已是最新版本，无需迁移")
            conn.close()
            return True
        
        print(f"需要添加字段: {', '.join(migrations_needed)}")
        
        # 添加 card_header 字段
        if 'card_header' in migrations_needed:
            print("正在添加 card_header 字段...")
            cursor.execute("""
                ALTER TABLE cards 
                ADD COLUMN card_header TEXT
            """)
            print("✓ card_header 字段添加成功")
        
        conn.commit()
        
        # 验证迁移
        cursor.execute("PRAGMA table_info(cards)")
        columns_after = [row[1] for row in cursor.fetchall()]
        
        if 'card_header' in columns_after:
            print("\n✅ 数据库迁移完成！")
            print("新增字段:")
            print("  - card_header (文本，可为空，用于备注卡头/来源/批次等)")
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
    print("数据库迁移工具：添加备注卡头字段")
    print("=" * 60)
    print()
    
    success = migrate()
    
    print()
    if success:
        print("🎉 迁移成功！现在可以重启应用程序。")
    else:
        print("⚠️  迁移失败，请检查错误信息。")
    print("=" * 60)
