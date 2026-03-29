import sqlite3
import logging
import os
from typing import Dict, Any

# 配置日志以便捕获具体错误信息
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_to_database(db_path: str, table_name: str, data: Dict[str, Any]) -> bool:
    """
    修复落库失败问题：增加事务提交、异常捕获及详细日志
    :param db_path: 数据库文件路径
    :param table_name: 表名
    :param data: 待插入的数据字典
    :return: 成功返回 True，失败返回 False
    """
    conn = None
    try:
        # 1. 建立数据库连接
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 2. 自动建表（防止因表不存在导致的落库失败）
        # 将所有字段默认为 TEXT 类型以适应电商多变数据，生产环境建议严格定义
        columns = ', '.join([f"{k} TEXT" for k in data.keys()])
        create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {columns})"
        cursor.execute(create_table_sql)

        # 3. 准备插入语句
        keys = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        insert_sql = f"INSERT INTO {table_name} ({keys}) VALUES ({placeholders})"
        
        # 4. 执行插入
        cursor.execute(insert_sql, tuple(str(v) for v in data.values()))

        # 5. 关键修复：显式提交事务（原代码常漏掉此步）
        conn.commit()
        logging.info(f"数据成功落库到 {table_name}: {data}")
        return True

    except Exception as e:
        # 6. 关键修复：捕获具体异常并回滚，避免静默失败
        if conn:
            conn.rollback()
        logging.error(f"落库失败原因：{str(e)}")
        return False
    finally:
        # 7. 确保连接关闭
        if conn:
            conn.close()

if __name__ == "__main__":
    # 测试验证
    db_file = "test_ecommerce_flow.db"
    table = "task_logs"
    test_data = {"task_id": "FIX-TC-FLOW-001-001", "status": "success", "msg": "verified"}
    
    # 执行修复后的函数
    result = save_to_database(db_file, table, test_data)
    
    # 验证结果
    if result:
        print("测试通过：落库功能已修复并可独立执行")
        # 清理测试文件
        if os.path.exists(db_file):
            os.remove(db_file)
    else:
        raise AssertionError("修复后落库仍然失败")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
