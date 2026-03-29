import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_update_data(data: Dict[str, Any], required_fields: list) -> bool:
    """验证更新数据是否包含必填字段"""
    if not isinstance(data, dict):
        logger.error(f"数据格式错误：期望 dict，实际 {type(data)}")
        return False
    
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        logger.error(f"缺少必填字段：{missing_fields}")
        return False
    
    return True


def safe_update(data: Dict[str, Any], required_fields: list = None) -> Dict[str, Any]:
    """
    安全执行 update 操作，包含完整的错误处理和日志记录
    
    Args:
        data: 待更新的数据字典
        required_fields: 必填字段列表
    
    Returns:
        包含执行结果的字典
    """
    result = {
        'success': False,
        'error': None,
        'timestamp': datetime.now().isoformat(),
        'data': None
    }
    
    try:
        # 1. 参数类型检查
        if data is None:
            raise ValueError("更新数据不能为空")
        
        if not isinstance(data, dict):
            raise TypeError(f"更新数据必须是字典类型，实际类型：{type(data)}")
        
        # 2. 必填字段验证
        if required_fields:
            if not validate_update_data(data, required_fields):
                raise ValueError("数据验证失败")
        
        # 3. 空值检查
        empty_fields = [k for k, v in data.items() if v is None]
        if empty_fields:
            logger.warning(f"检测到空值字段：{empty_fields}")
        
        # 4. 模拟更新操作（实际场景中替换为真实更新逻辑）
        updated_data = {k: v for k, v in data.items() if v is not None}
        
        # 5. 更新成功标记
        result['success'] = True
        result['data'] = updated_data
        logger.info(f"update 执行成功，更新字段数：{len(updated_data)}")
        
    except Exception as e:
        result['error'] = str(e)
        result['exception_type'] = type(e).__name__
        logger.error(f"update 执行失败：{type(e).__name__} - {str(e)}")
        # 重新抛出异常以便调用方感知
        raise
    
    return result


def update_with_retry(data: Dict[str, Any], required_fields: list = None, max_retries: int = 3) -> Dict[str, Any]:
    """
    带重试机制的 update 操作
    
    Args:
        data: 待更新的数据字典
        required_fields: 必填字段列表
        max_retries: 最大重试次数
    
    Returns:
        包含执行结果的字典
    """
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"update 尝试第 {attempt}/{max_retries} 次")
            result = safe_update(data, required_fields)
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"第 {attempt} 次尝试失败：{str(e)}")
            if attempt < max_retries:
                continue
    
    # 所有重试都失败
    logger.error(f"update 所有重试失败，最终错误：{str(last_error)}")
    return {
        'success': False,
        'error': str(last_error),
        'timestamp': datetime.now().isoformat(),
        'data': None,
        'retries_exhausted': True
    }


# 测试验证
def test_fix():
    """测试修复代码"""
    print("开始测试 update 修复代码...")
    
    # 测试 1: 正常更新
    test_data = {'id': 1, 'name': 'test', 'status': 'active'}
    result = safe_update(test_data, required_fields=['id', 'name'])
    assert result['success'] == True, "测试 1 失败：正常更新应成功"
    print("✓ 测试 1 通过：正常更新")
    
    # 测试 2: 缺少必填字段
    try:
        safe_update({'name': 'test'}, required_fields=['id', 'name'])
        assert False, "测试 2 失败：应抛出异常"
    except ValueError:
        print("✓ 测试 2 通过：缺少必填字段正确抛出异常")
    
    # 测试 3: 空数据
    try:
        safe_update(None)
        assert False, "测试 3 失败：应抛出异常"
    except ValueError:
        print("✓ 测试 3 通过：空数据正确抛出异常")
    
    # 测试 4: 类型错误
    try:
        safe_update("not a dict")
        assert False, "测试 4 失败：应抛出异常"
    except TypeError:
        print("✓ 测试 4 通过：类型错误正确抛出异常")
    
    # 测试 5: 带重试机制
    result = update_with_retry({'id': 2, 'name': 'retry_test'}, required_fields=['id'])
    assert result['success'] == True, "测试 5 失败：重试机制应成功"
    print("✓ 测试 5 通过：重试机制")
    
    print("\n所有测试通过！✓")
    return True


if __name__ == '__main__':
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
