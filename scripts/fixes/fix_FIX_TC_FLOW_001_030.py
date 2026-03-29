import logging
import time
from typing import Dict, Any, Optional
from functools import wraps

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def retry_on_failure(max_retries=3, delay=1):
    """重试装饰器，处理临时性失败"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"第{attempt + 1}次尝试失败: {str(e)}")
                    time.sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator


def validate_update_data(data: Dict[str, Any], required_fields: list) -> bool:
    """验证更新数据是否包含必要字段"""
    if not isinstance(data, dict):
        logger.error("更新数据必须是字典类型")
        return False
    
    for field in required_fields:
        if field not in data:
            logger.error(f"缺少必要字段: {field}")
            return False
    
    if not data:
        logger.error("更新数据不能为空")
        return False
    
    return True


def validate_where_condition(where: Dict[str, Any]) -> bool:
    """验证查询条件是否有效"""
    if not isinstance(where, dict):
        logger.error("查询条件必须是字典类型")
        return False
    
    if not where:
        logger.error("查询条件不能为空，否则可能更新全部数据")
        return False
    
    return True


@retry_on_failure(max_retries=3, delay=1)
def safe_update(
    table: str,
    data: Dict[str, Any],
    where: Dict[str, Any],
    required_fields: Optional[list] = None,
    connection: Optional[Any] = None
) -> Dict[str, Any]:
    """
    安全的数据库更新操作
    
    参数:
        table: 表名
        data: 要更新的数据字典
        where: 查询条件字典
        required_fields: 必填字段列表
        connection: 数据库连接对象
    
    返回:
        包含成功状态和受影响行数的字典
    """
    result = {
        "success": False,
        "affected_rows": 0,
        "error": None
    }
    
    # 参数验证
    if not table or not isinstance(table, str):
        result["error"] = "表名无效"
        logger.error(result["error"])
        return result
    
    if not validate_update_data(data, required_fields or []):
        result["error"] = "更新数据验证失败"
        return result
    
    if not validate_where_condition(where):
        result["error"] = "查询条件验证失败"
        return result
    
    try:
        # 模拟数据库更新操作（实际使用时替换为真实数据库操作）
        if connection is None:
            # 如果没有提供连接，使用模拟模式
            logger.info(f"模拟更新表 {table}, 条件: {where}, 数据: {data}")
            result["success"] = True
            result["affected_rows"] = 1
        else:
            # 使用真实数据库连接
            cursor = connection.cursor()
            
            # 构建更新语句
            set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
            where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
            sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
            
            values = list(data.values()) + list(where.values())
            cursor.execute(sql, values)
            
            affected = cursor.rowcount
            connection.commit()
            
            result["success"] = affected > 0
            result["affected_rows"] = affected
            
            cursor.close()
        
        logger.info(f"更新成功，影响行数: {result['affected_rows']}")
        
    except Exception as e:
        error_msg = f"更新失败: {str(e)}"
        result["error"] = error_msg
        logger.error(error_msg)
        
        # 如果有连接，尝试回滚
        if connection is not None:
            try:
                connection.rollback()
            except:
                pass
        
        raise  # 重新抛出异常以触发重试
    
    return result


def update_with_transaction(
    table: str,
    data: Dict[str, Any],
    where: Dict[str, Any],
    connection: Any,
    required_fields: Optional[list] = None
) -> Dict[str, Any]:
    """
    带事务管理的更新操作
    
    参数:
        table: 表名
        data: 要更新的数据
        where: 查询条件
        connection: 数据库连接
        required_fields: 必填字段
    
    返回:
        操作结果字典
    """
    result = {"success": False, "affected_rows": 0, "error": None}
    
    try:
        # 开始事务
        connection.autocommit = False
        
        result = safe_update(
            table=table,
            data=data,
            where=where,
            required_fields=required_fields,
            connection=connection
        )
        
        if result["success"]:
            connection.commit()
        else:
            connection.rollback()
            
    except Exception as e:
        connection.rollback()
        result["error"] = f"事务执行失败: {str(e)}"
        logger.error(result["error"])
    
    finally:
        connection.autocommit = True
    
    return result


# 测试验证
def test_fix():
    """测试修复代码"""
    print("测试 1: 验证更新数据...")
    assert validate_update_data({"name": "test"}, []) == True
    assert validate_update_data("invalid", []) == False
    assert validate_update_data({}, ["name"]) == False
    
    print("测试 2: 验证查询条件...")
    assert validate_where_condition({"id": 1}) == True
    assert validate_where_condition({}) == False
    assert validate_where_condition("invalid") == False
    
    print("测试 3: 安全更新（模拟模式）...")
    result = safe_update(
        table="users",
        data={"name": "new_name"},
        where={"id": 1}
    )
    assert result["success"] == True
    assert result["affected_rows"] == 1
    
    print("测试 4: 带必填字段验证...")
    result = safe_update(
        table="orders",
        data={"status": "completed"},
        where={"order_id": 1001},
        required_fields=["status"]
    )
    assert result["success"] == True
    
    print("测试 5: 缺少必填字段...")
    result = safe_update(
        table="orders",
        data={"other": "value"},
        where={"order_id": 1001},
        required_fields=["status"]
    )
    assert result["success"] == False
    assert result["error"] == "更新数据验证失败"
    
    print("\n所有测试通过！")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
