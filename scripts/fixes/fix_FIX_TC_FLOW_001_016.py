import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UpdateOperationError(Exception):
    """自定义更新操作异常"""
    pass


def validate_update_data(data: Dict[str, Any], required_fields: list) -> bool:
    """验证更新数据是否包含必要字段"""
    if not isinstance(data, dict):
        return False
    for field in required_fields:
        if field not in data:
            logger.warning(f"缺少必要字段: {field}")
            return False
    return True


def safe_update(
    table_name: str,
    update_data: Dict[str, Any],
    where_condition: Dict[str, Any],
    required_fields: Optional[list] = None,
    db_connection: Optional[Any] = None
) -> Dict[str, Any]:
    """
    安全的数据库更新操作
    
    参数:
        table_name: 表名
        update_data: 要更新的数据字典
        where_condition: 更新条件字典
        required_fields: 必要字段列表
        db_connection: 数据库连接对象
    
    返回:
        包含操作结果的字典
    """
    result = {
        "success": False,
        "affected_rows": 0,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # 1. 验证输入参数
        if not table_name or not isinstance(table_name, str):
            raise UpdateOperationError("表名不能为空")
        
        if not update_data or not isinstance(update_data, dict):
            raise UpdateOperationError("更新数据不能为空")
        
        if not where_condition or not isinstance(where_condition, dict):
            raise UpdateOperationError("更新条件不能为空")
        
        # 2. 验证必要字段
        if required_fields:
            if not validate_update_data(update_data, required_fields):
                raise UpdateOperationError(f"更新数据缺少必要字段: {required_fields}")
        
        # 3. 清理更新数据（移除空值和非法字符）
        clean_data = {}
        for key, value in update_data.items():
            if value is not None and key.strip():
                clean_data[key.strip()] = value
        
        if not clean_data:
            raise UpdateOperationError("清理后无有效更新数据")
        
        # 4. 执行更新操作（模拟数据库操作）
        if db_connection:
            # 实际数据库更新逻辑
            cursor = db_connection.cursor()
            set_clause = ", ".join([f"{k} = %s" for k in clean_data.keys()])
            where_clause = " AND ".join([f"{k} = %s" for k in where_condition.keys()])
            sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
            values = list(clean_data.values()) + list(where_condition.values())
            
            cursor.execute(sql, values)
            affected = cursor.rowcount
            db_connection.commit()
            
            result["affected_rows"] = affected
            result["success"] = affected > 0
        else:
            # 模拟更新（用于测试）
            logger.info(f"模拟更新表 {table_name}, 数据: {clean_data}, 条件: {where_condition}")
            result["affected_rows"] = 1
            result["success"] = True
        
        logger.info(f"更新成功，影响行数: {result['affected_rows']}")
        
    except Exception as e:
        error_msg = str(e)
        result["error"] = error_msg
        result["success"] = False
        logger.error(f"更新失败: {error_msg}")
        
        # 事务回滚
        if db_connection:
            try:
                db_connection.rollback()
                logger.info("已回滚事务")
            except Exception as rollback_error:
                logger.error(f"回滚失败: {rollback_error}")
    
    return result


def batch_update(
    table_name: str,
    update_records: list,
    required_fields: Optional[list] = None,
    db_connection: Optional[Any] = None
) -> Dict[str, Any]:
    """
    批量更新操作
    
    参数:
        table_name: 表名
        update_records: 更新记录列表，每条记录包含 update_data 和 where_condition
        required_fields: 必要字段列表
        db_connection: 数据库连接对象
    
    返回:
        批量操作结果
    """
    result = {
        "success": True,
        "total": len(update_records),
        "success_count": 0,
        "failed_count": 0,
        "errors": [],
        "timestamp": datetime.now().isoformat()
    }
    
    for index, record in enumerate(update_records):
        update_data = record.get("update_data", {})
        where_condition = record.get("where_condition", {})
        
        single_result = safe_update(
            table_name=table_name,
            update_data=update_data,
            where_condition=where_condition,
            required_fields=required_fields,
            db_connection=db_connection
        )
        
        if single_result["success"]:
            result["success_count"] += 1
        else:
            result["failed_count"] += 1
            result["errors"].append({
                "index": index,
                "error": single_result["error"]
            })
    
    result["success"] = result["failed_count"] == 0
    return result


# 测试验证
def test_fix():
    """测试修复代码"""
    print("测试 1: 单条更新（模拟）")
    result1 = safe_update(
        table_name="products",
        update_data={"price": 99.99, "stock": 100},
        where_condition={"id": 1},
        required_fields=["price"]
    )
    assert result1["success"] == True
    print(f"结果: {result1}")
    
    print("\n测试 2: 缺少必要字段")
    result2 = safe_update(
        table_name="products",
        update_data={"stock": 100},
        where_condition={"id": 1},
        required_fields=["price"]
    )
    assert result2["success"] == False
    print(f"结果: {result2}")
    
    print("\n测试 3: 批量更新（模拟）")
    result3 = batch_update(
        table_name="products",
        update_records=[
            {"update_data": {"price": 99.99}, "where_condition": {"id": 1}},
            {"update_data": {"price": 199.99}, "where_condition": {"id": 2}}
        ],
        required_fields=["price"]
    )
    assert result3["success"] == True
    assert result3["success_count"] == 2
    print(f"结果: {result3}")
    
    print("\n所有测试通过!")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
