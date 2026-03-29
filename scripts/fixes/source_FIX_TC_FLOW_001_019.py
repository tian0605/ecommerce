import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, Optional

class DatabaseUpdateError(Exception):
    """数据库更新异常"""
    pass

def fix_update_operation(
    table_name: str,
    data: Dict[str, Any],
    where_clause: Dict[str, Any],
    db_path: str = "ecommerce.db"
) -> bool:
    """
    修复电商运营数据更新操作
    
    参数:
        table_name: 表名
        data: 要更新的数据字典
        where_clause: 更新条件字典
        db_path: 数据库路径
    
    返回:
        bool: 更新是否成功
    """
    conn = None
    try:
        # 1. 参数验证
        if not table_name or not isinstance(table_name, str):
            raise DatabaseUpdateError("表名不能为空")
        
        if not data or not isinstance(data, dict):
            raise DatabaseUpdateError("更新数据不能为空")
        
        if not where_clause or not isinstance(where_clause, dict):
            raise DatabaseUpdateError("更新条件不能为空")
        
        # 2. 建立数据库连接
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 3. 构建更新语句
        set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
        where_keys = list(where_clause.keys())
        where_condition = " AND ".join([f"{key} = ?" for key in where_keys])
        
        sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_condition}"
        
        # 4. 准备参数值
        values = list(data.values()) + list(where_clause.values())
        
        # 5. 执行更新（带事务）
        cursor.execute(sql, values)
        
        # 6. 检查影响行数
        if cursor.rowcount == 0:
            print(f"警告：没有记录被更新，可能条件不匹配")
        
        # 7. 提交事务
        conn.commit()
        
        print(f"更新成功：{cursor.rowcount} 条记录")
        return True
        
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise DatabaseUpdateError(f"数据库错误：{str(e)}")
    except Exception as e:
        if conn:
            conn.rollback()
        raise DatabaseUpdateError(f"更新失败：{str(e)}")
    finally:
        if conn:
            conn.close()


def fix_update_with_retry(
    table_name: str,
    data: Dict[str, Any],
    where_clause: Dict[str, Any],
    db_path: str = "ecommerce.db",
    max_retries: int = 3
) -> bool:
    """
    带重试机制的更新操作（处理并发冲突）
    
    参数:
        table_name: 表名
        data: 要更新的数据字典
        where_clause: 更新条件字典
        db_path: 数据库路径
        max_retries: 最大重试次数
    
    返回:
        bool: 更新是否成功
    """
    for attempt in range(max_retries):
        try:
            return fix_update_operation(table_name, data, where_clause, db_path)
        except DatabaseUpdateError as e:
            if attempt == max_retries - 1:
                print(f"更新失败，已重试 {max_retries} 次：{str(e)}")
                raise
            print(f"第 {attempt + 1} 次重试...")
            import time
            time.sleep(0.5 * (attempt + 1))  # 指数退避
    
    return False


# 测试验证
def test_fix():
    """测试修复代码"""
    import os
    
    # 创建测试数据库
    test_db = "test_ecommerce.db"
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    # 创建测试表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            status TEXT,
            amount REAL,
            updated_at TEXT
        )
    ''')
    
    # 插入测试数据
    cursor.execute('''
        INSERT OR REPLACE INTO orders (id, status, amount, updated_at)
        VALUES (1, 'pending', 100.0, '2024-01-01')
    ''')
    conn.commit()
    conn.close()
    
    # 测试更新操作
    try:
        result = fix_update_operation(
            table_name="orders",
            data={"status": "completed", "updated_at": datetime.now().isoformat()},
            where_clause={"id": 1},
            db_path=test_db
        )
        assert result == True, "更新应该成功"
        
        # 验证数据已更新
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM orders WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        assert row[0] == "completed", "数据应该已更新"
        
        # 清理测试文件
        os.remove(test_db)
        
        print("所有测试通过！")
        return True
        
    except Exception as e:
        print(f"测试失败：{str(e)}")
        if os.path.exists(test_db):
            os.remove(test_db)
        return False


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
