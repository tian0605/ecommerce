import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime
import json

class UpdateFlowError(Exception):
    """更新流程异常"""
    pass

def validate_update_data(data: Dict[str, Any], required_fields: list) -> bool:
    """验证更新数据是否包含必填字段"""
    if not isinstance(data, dict):
        return False
    for field in required_fields:
        if field not in data:
            return False
    return True

def fix_update_flow(
    table_name: str,
    data: Dict[str, Any],
    condition: Dict[str, Any],
    db_path: str = ":memory:",
    required_fields: Optional[list] = None
) -> Dict[str, Any]:
    """
    修复电商运营自动化中的 update 失败问题
    
    参数:
        table_name: 表名
        data: 要更新的数据字典
        condition: 更新条件字典
        db_path: 数据库路径
        required_fields: 必填字段列表
    
    返回:
        包含成功状态和受影响行数的字典
    """
    result = {
        "success": False,
        "rows_affected": 0,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # 1. 参数验证
        if not table_name or not isinstance(table_name, str):
            raise UpdateFlowError("表名不能为空")
        
        if not isinstance(data, dict) or len(data) == 0:
            raise UpdateFlowError("更新数据不能为空")
        
        if not isinstance(condition, dict) or len(condition) == 0:
            raise UpdateFlowError("更新条件不能为空")
        
        # 2. 必填字段验证
        if required_fields:
            if not validate_update_data(data, required_fields):
                raise UpdateFlowError(f"缺少必填字段，需要: {required_fields}")
        
        # 3. 防止 SQL 注入 - 验证表名
        if not table_name.replace("_", "").replace("-", "").isalnum():
            raise UpdateFlowError("表名包含非法字符")
        
        # 4. 建立数据库连接
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # 5. 构建安全的 UPDATE 语句
            set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
            where_clause = " AND ".join([f"{key} = ?" for key in condition.keys()])
            
            sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
            
            # 6. 执行更新
            values = list(data.values()) + list(condition.values())
            cursor.execute(sql, values)
            
            # 7. 提交事务
            conn.commit()
            
            # 8. 获取受影响行数
            result["rows_affected"] = cursor.rowcount
            result["success"] = True
            
        except sqlite3.Error as db_error:
            conn.rollback()
            raise UpdateFlowError(f"数据库错误: {str(db_error)}")
        finally:
            conn.close()
            
    except UpdateFlowError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = f"未知错误: {str(e)}"
    
    return result

def fix_update_flow_json(
    table_name: str,
    data_json: str,
    condition_json: str,
    db_path: str = ":memory:",
    required_fields: Optional[list] = None
) -> Dict[str, Any]:
    """
    修复版本 - 支持 JSON 字符串输入
    """
    try:
        data = json.loads(data_json) if isinstance(data_json, str) else data_json
        condition = json.loads(condition_json) if isinstance(condition_json, str) else condition_json
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "rows_affected": 0,
            "error": f"JSON 解析错误: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
    
    return fix_update_flow(table_name, data, condition, db_path, required_fields)

# 测试验证
def test_fix():
    """测试修复代码"""
    import tempfile
    import os
    
    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    try:
        # 初始化测试表
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                status TEXT,
                amount REAL,
                updated_at TEXT
            )
        """)
        conn.execute("INSERT INTO orders VALUES (1, 'pending', 100.0, '')")
        conn.commit()
        conn.close()
        
        # 测试更新
        result = fix_update_flow(
            table_name="orders",
            data={"status": "completed", "updated_at": datetime.now().isoformat()},
            condition={"id": 1},
            db_path=db_path,
            required_fields=["status"]
        )
        
        assert result["success"] == True, f"更新应成功: {result}"
        assert result["rows_affected"] == 1, f"应影响 1 行: {result}"
        assert result["error"] is None, f"不应有错误: {result}"
        
        # 测试 JSON 输入版本
        result_json = fix_update_flow_json(
            table_name="orders",
            data_json='{"status": "shipped", "amount": 150.0}',
            condition_json='{"id": 1}',
            db_path=db_path
        )
        
        assert result_json["success"] == True, f"JSON 版本更新应成功: {result_json}"
        
        print("所有测试通过!")
        return True
        
    finally:
        # 清理临时文件
        if os.path.exists(db_path):
            os.unlink(db_path)

if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
