import json
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UpdateStepError(Exception):
    """更新步骤异常"""
    pass


def validate_update_params(params: Dict[str, Any]) -> bool:
    """验证更新参数是否完整"""
    required_fields = ['id', 'data']
    for field in required_fields:
        if field not in params:
            logger.error(f"缺少必要参数: {field}")
            return False
    if not params.get('id'):
        logger.error("ID 不能为空")
        return False
    if not isinstance(params.get('data'), dict):
        logger.error("data 必须是字典类型")
        return False
    return True


def execute_update(params: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    """
    执行更新操作，包含重试机制
    
    Args:
        params: 更新参数，包含 id 和 data
        max_retries: 最大重试次数
    
    Returns:
        更新结果字典
    """
    # 参数验证
    if not validate_update_params(params):
        raise UpdateStepError("参数验证失败")
    
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            # 模拟更新操作（实际使用时替换为真实逻辑）
            result = _perform_update(params)
            
            if result.get('success'):
                logger.info(f"更新成功，ID: {params['id']}")
                return {
                    'success': True,
                    'message': '更新成功',
                    'data': result.get('data'),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                raise UpdateStepError(result.get('message', '更新失败'))
                
        except Exception as e:
            last_error = e
            retry_count += 1
            logger.warning(f"更新失败，重试 {retry_count}/{max_retries}: {str(e)}")
            
            if retry_count < max_retries:
                time.sleep(1 * retry_count)  # 递增延迟
    
    # 所有重试失败
    error_msg = f"更新失败，已重试{max_retries}次: {str(last_error)}"
    logger.error(error_msg)
    raise UpdateStepError(error_msg)


def _perform_update(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    实际执行更新操作
    
    注意：这是模拟实现，实际使用时需要替换为真实的数据库或API调用
    """
    update_id = params['id']
    update_data = params['data']
    
    # 模拟业务逻辑验证
    if not isinstance(update_id, (str, int)):
        return {'success': False, 'message': 'ID 类型错误'}
    
    if len(update_data) == 0:
        return {'success': False, 'message': '更新数据不能为空'}
    
    # 模拟成功更新
    return {
        'success': True,
        'data': {
            'id': update_id,
            'updated_fields': list(update_data.keys()),
            'update_time': datetime.now().isoformat()
        }
    }


def fix_update_step(task_params: Any) -> Dict[str, Any]:
    """
    修复 update 步骤的主函数
    
    Args:
        task_params: 任务参数，可以是字典或 JSON 字符串
    
    Returns:
        执行结果
    """
    try:
        # 处理字符串类型的参数
        if isinstance(task_params, str):
            params = json.loads(task_params)
        elif isinstance(task_params, dict):
            params = task_params
        else:
            raise UpdateStepError(f"不支持的参数类型: {type(task_params)}")
        
        # 执行更新
        result = execute_update(params)
        
        return {
            'status': 'success',
            'task_id': 'FIX-FIX-TC-FLOW-001-018-002',
            'result': result
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {str(e)}")
        return {
            'status': 'error',
            'task_id': 'FIX-FIX-TC-FLOW-001-018-002',
            'error': f'参数格式错误：{str(e)}'
        }
    except UpdateStepError as e:
        logger.error(f"更新步骤错误: {str(e)}")
        return {
            'status': 'error',
            'task_id': 'FIX-FIX-TC-FLOW-001-018-002',
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"未知错误: {str(e)}")
        return {
            'status': 'error',
            'task_id': 'FIX-FIX-TC-FLOW-001-018-002',
            'error': f'未知错误：{str(e)}'
        }


# 测试验证
def test_fix():
    """测试修复代码"""
    # 测试用例1：正常更新
    test_params = {
        'id': '12345',
        'data': {
            'status': 'active',
            'price': 99.99
        }
    }
    result = fix_update_step(test_params)
    assert result['status'] == 'success', f"测试1失败：{result}"
    
    # 测试用例2：JSON 字符串参数
    json_params = json.dumps({
        'id': '67890',
        'data': {'name': 'test_product'}
    })
    result = fix_update_step(json_params)
    assert result['status'] == 'success', f"测试2失败：{result}"
    
    # 测试用例3：缺少必要参数
    invalid_params = {'data': {'name': 'test'}}
    result = fix_update_step(invalid_params)
    assert result['status'] == 'error', f"测试3失败：{result}"
    
    print("所有测试通过！")
    return True


if __name__ == '__main__':
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
