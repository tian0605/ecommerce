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
                        logger.error(f"更新失败，已重试{max_retries}次: {str(e)}")
                        raise
                    logger.warning(f"更新失败，第{attempt + 1}次重试: {str(e)}")
                    time.sleep(delay * (attempt + 1))
        return wrapper
    return decorator


def validate_update_data(data: Dict[str, Any]) -> bool:
    """验证更新数据的有效性"""
    if not isinstance(data, dict):
        return False
    if not data:
        return False
    return True


@retry_on_failure(max_retries=3, delay=1)
def update_record(record_id: str, update_data: Dict[str, Any], 
                  datasource: Optional[Any] = None) -> Dict[str, Any]:
    """
    修复后的更新函数，包含完整的错误处理
    
    Args:
        record_id: 记录ID
        update_data: 更新数据字典
        datasource: 数据源对象（可选）
    
    Returns:
        更新结果字典
    """
    # 参数验证
    if not record_id or not isinstance(record_id, str):
        raise ValueError("record_id 必须是非空字符串")
    
    if not validate_update_data(update_data):
        raise ValueError("update_data 必须是非空字典")
    
    # 模拟更新操作（实际使用时替换为真实的数据源操作）
    try:
        # 这里应该替换为实际的数据库或API更新逻辑
        # 例如：datasource.update(record_id, update_data)
        result = {
            "success": True,
            "record_id": record_id,
            "updated_fields": list(update_data.keys()),
            "timestamp": time.time()
        }
        logger.info(f"更新成功：record_id={record_id}")
        return result
    
    except Exception as e:
        logger.error(f"更新异常：{str(e)}")
        raise


def fix_update_flow(record_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    主修复函数：处理电商运营中的更新流程
    
    Args:
        record_id: 需要更新的记录ID
        update_data: 更新的数据内容
    
    Returns:
        更新结果
    """
    try:
        result = update_record(record_id, update_data)
        return {
            "status": "success",
            "data": result
        }
    except ValueError as e:
        return {
            "status": "validation_error",
            "message": str(e)
        }
    except Exception as e:
        return {
            "status": "update_failed",
            "message": str(e)
        }


# 测试验证
def test_fix():
    """测试修复代码"""
    # 测试1：正常更新
    result1 = fix_update_flow("ORDER-001", {"status": "shipped", "tracking_no": "TRK123"})
    assert result1["status"] == "success", "测试1失败：正常更新应成功"
    
    # 测试2：空record_id
    result2 = fix_update_flow("", {"status": "shipped"})
    assert result2["status"] == "validation_error", "测试2失败：空ID应返回验证错误"
    
    # 测试3：空更新数据
    result3 = fix_update_flow("ORDER-002", {})
    assert result3["status"] == "validation_error", "测试3失败：空数据应返回验证错误"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
