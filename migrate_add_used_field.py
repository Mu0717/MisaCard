#!/usr/bin/env python3
"""
数据库迁移脚本：添加 is_used 和 used_time 字段
用于为现有数据库添加卡片使用状态相关字段
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from app.database import engine


def migrate():
    """添加 is_used 和 used_time 字段"""
    print("正在迁移数据库...")
    print(f"数据库引擎: {engine.url}")

    try:
        with engine.connect() as conn:
            # 检查字段是否已存在
            result = conn.execute(text("PRAGMA table_info(cards)"))
            columns = [row[1] for row in result]
            
            needs_migration = False
            
            if 'is_used' not in columns:
                print("添加 is_used 字段...")
                conn.execute(text("ALTER TABLE cards ADD COLUMN is_used BOOLEAN DEFAULT 0"))
                conn.commit()
                needs_migration = True
                print("✅ is_used 字段添加成功")
            else:
                print("✅ is_used 字段已存在，跳过")
            
            if 'used_time' not in columns:
                print("添加 used_time 字段...")
                conn.execute(text("ALTER TABLE cards ADD COLUMN used_time TIMESTAMP"))
                conn.commit()
                needs_migration = True
                print("✅ used_time 字段添加成功")
            else:
                print("✅ used_time 字段已存在，跳过")
            
            if needs_migration:
                print("\n✅ 数据库迁移成功！")
            else:
                print("\n✅ 数据库已是最新版本，无需迁移")
                
        return True
    except Exception as e:
        print(f"❌ 数据库迁移失败: {e}")
        return False


if __name__ == "__main__":
    migrate()
    print("\n完成！")

