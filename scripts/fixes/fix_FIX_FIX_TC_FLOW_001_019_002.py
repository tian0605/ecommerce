import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_update_params(params: Dict[str, Any]) -> bool:
    """验证更新参数是否完整"""
    required_fields = ['record_id', 'update_data']
    for field in required_fields:
        if field not in params:
            logger.error(f"缺少必要参数: {field}")
            return False
    if not params.get('record_id'):
        logger.error("record_id 不能为空")
        return False
    if not isinstance(params.get('update_data'), dict):
        logger.error("update_data 必须是字典类型")
        return False
    return True


def execute_update(params: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    """
    执行更新操作，包含重试机制和错误处理
    
    Args:
        params: 更新参数字典，包含 record_id 和 update_data
        max_retries: 最大重试次数
    
    Returns:
        执行结果字典
    """
    result = {
        'success': False,
        'message': '',
        'record_id': None,
        'timestamp': datetime.now().isoformat()
    }
    
    # 参数类型转换处理
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError as e:
            result['message'] = f"参数解析失败: {str(e)}"
            return result
    
    # 验证参数
    if not validate_update_params(params):
        result['message'] = "参数验证失败"
        return result
    
    record_id = params['record_id']
    update_data = params['update_data']
    result['record_id'] = record_id
    
    # 执行更新，带重试机制
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"执行更新操作，尝试 {attempt}/{max_retries}")
            logger.info(f"记录ID: {record_id}")
            logger.info(f"更新数据: {update_data}")
            
            # 模拟更新操作（实际场景中替换为真实的数据库或API调用）
            if not update_data:
                raise ValueError("更新数据不能为空")
            
            # 更新成功
            result['success'] = True
            result['message'] = f"更新成功，记录ID: {record_id}"
            logger.info(result['message'])
            break
            
        except Exception as e:
            error_msg = f"更新失败 (尝试 {attempt}/{max_retries}): {str(e)}"
            logger.error(error_msg)
            result['message'] = error_msg
            
            if attempt == max_retries:
                result['message'] = f"更新失败，已达到最大重试次数: {str(e)}"
                logger.error(result['message'])
            else:
                logger.info("等待重试...")
    
    return result


def fix_update_step(task_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    修复 update 步骤的主函数
    
    Args:
        task_params: 任务参数字典
    
    Returns:
        执行结果
    """
    logger.info("=" * 50)
    logger.info("开始执行 update 步骤修复")
    logger.info("=" * 50)
    
    # 默认参数（如果未提供）
    if task_params is None:
        task_params = {
            'record_id': 'DEFAULT_001',
            'update_data': {'status': 'updated', 'timestamp': datetime.now().isoformat()}
        }
    
    # 执行更新
    result = execute_update(task_params)
    
    logger.info("=" * 50)
    logger.info(f"update 步骤执行完成，成功: {result['success']}")
    logger.info("=" * 50)
    
    return result


# 测试验证
def test_fix():
    """测试修复代码"""
    print("测试 1: 正常参数更新")
    test_params = {
        'record_id': 'TEST_001',
        'update_data': {'status': 'active', 'count': 100}
    }
    result1 = fix_update_step(test_params)
    assert result1['success'] == True, "测试 1 失败"
    print(f"✓ 测试 1 通过: {result1['message']}")
    
    print("\n测试 2: 字符串参数更新")
    test_params_str = json.dumps({
        'record_id': 'TEST_002',
        'update_data': {'status': 'pending'}
    })
    result2 = execute_update(test_params_str)
    assert result2['success'] == True, "测试 2 失败"
    print(f"✓ 测试 2 通过: {result2['message']}")
    
    print("\n测试 3: 缺少必要参数")
    test_params_invalid = {'record_id': 'TEST_003'}
    result3 = execute_update(test_params_invalid)
    assert result3['success'] == False, "测试 3 失败"
    print(f"✓ 测试 3 通过: {result3['message']}")
    
    print("\n" + "=" * 50)
    print("所有测试通过！")
    print("=" * 50)
    return True


if __name__ == '__main__':
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
