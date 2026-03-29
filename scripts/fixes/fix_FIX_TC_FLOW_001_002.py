import logging
import time
from typing import Dict, Any, Optional
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UpdateError(Exception):
    """自定义更新异常"""
    pass


def retry_on_failure(max_retries=3, delay=1):
    """重试装饰器"""
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


def validate_update_data(data: Dict[str, Any], required_fields: list) -> bool:
    """验证更新数据完整性"""
    if not isinstance(data, dict):
        logger.error("更新数据必须是字典类型")
        return False
    
    for field in required_fields:
        if field not in data:
            logger.error(f"缺少必需字段: {field}")
            return False
        if data[field] is None:
            logger.error(f"字段值不能为空: {field}")
            return False
    
    return True


@retry_on_failure(max_retries=3, delay=2)
def safe_update(
    data: Dict[str, Any],
    update_func: callable,
    required_fields: Optional[list] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    安全更新函数 - 修复 update 失败问题
    
    参数:
        data: 待更新的数据字典
        update_func: 实际执行更新的函数
        required_fields: 必需字段列表
        **kwargs: 传递给 update_func 的额外参数
    
    返回:
        更新结果字典
    """
    # 1. 数据验证
    if required_fields:
        if not validate_update_data(data, required_fields):
            raise UpdateError("数据验证失败")
    
    # 2. 数据预处理
    processed_data = preprocess_update_data(data)
    
    # 3. 执行更新
    try:
        result = update_func(processed_data, **kwargs)
        
        # 4. 验证更新结果
        if not verify_update_result(result):
            raise UpdateError("更新结果验证失败")
        
        logger.info(f"更新成功: {data.get('id', 'unknown')}")
        return {
            "success": True,
            "data": result,
            "message": "更新成功"
        }
        
    except Exception as e:
        logger.error(f"更新异常: {str(e)}")
        raise UpdateError(f"更新失败: {str(e)}")


def preprocess_update_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """预处理更新数据"""
    processed = data.copy()
    
    # 清理空字符串
    for key, value in processed.items():
        if isinstance(value, str) and value.strip() == "":
            processed[key] = None
    
    # 添加时间戳
    processed['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    
    return processed


def verify_update_result(result: Any) -> bool:
    """验证更新结果"""
    if result is None:
        return False
    if isinstance(result, dict):
        return result.get('success', False) or result.get('affected_rows', 0) > 0
    if isinstance(result, bool):
        return result
    if isinstance(result, int):
        return result > 0
    return True


# 示例更新函数（模拟数据库更新）
def mock_db_update(data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """模拟数据库更新操作"""
    # 模拟可能的失败场景
    if data.get('id') is None:
        raise Exception("缺少ID字段")
    
    # 模拟成功更新
    return {
        "success": True,
        "affected_rows": 1,
        "id": data.get('id'),
        "updated_at": data.get('updated_at')
    }


# 测试验证
def test_fix():
    """测试修复代码"""
    print("开始测试 update 修复代码...")
    
    # 测试1: 正常更新
    test_data = {"id": 123, "name": "测试商品", "price": 99.99}
    result = safe_update(
        data=test_data,
        update_func=mock_db_update,
        required_fields=['id', 'name']
    )
    assert result["success"] == True, "测试1失败: 正常更新应成功"
    print("✓ 测试1通过: 正常更新")
    
    # 测试2: 缺少必需字段
    try:
        bad_data = {"price": 99.99}  # 缺少 id 和 name
        safe_update(
            data=bad_data,
            update_func=mock_db_update,
            required_fields=['id', 'name']
        )
        print("✗ 测试2失败: 应抛出异常")
        return False
    except UpdateError:
        print("✓ 测试2通过: 缺少字段正确抛出异常")
    
    # 测试3: 数据验证
    assert validate_update_data(test_data, ['id', 'name']) == True
    assert validate_update_data({}, ['id']) == False
    print("✓ 测试3通过: 数据验证功能正常")
    
    print("\n所有测试通过！update 修复代码工作正常。")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
