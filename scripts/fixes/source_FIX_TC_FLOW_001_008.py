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
    """验证更新参数是否完整有效"""
    if not isinstance(params, dict):
        logger.error("参数必须是字典类型")
        return False
    
    required_fields = ['id', 'data']
    for field in required_fields:
        if field not in params:
            logger.error(f"缺少必要字段：{field}")
            return False
    
    if not params.get('id'):
        logger.error("id 不能为空")
        return False
    
    return True


def execute_update(params: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    """
    执行更新操作，包含重试机制和错误处理
    
    Args:
        params: 更新参数，包含 id 和 data
        max_retries: 最大重试次数
    
    Returns:
        包含成功状态和消息的字典
    """
    # 参数验证
    if not validate_update_params(params):
        return {
            'success': False,
            'message': '参数验证失败',
            'timestamp': datetime.now().isoformat()
        }
    
    # 参数标准化处理
    try:
        if isinstance(params.get('data'), str):
            params['data'] = json.loads(params['data'])
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败：{e}")
        return {
            'success': False,
            'message': f'数据格式错误：{str(e)}',
            'timestamp': datetime.now().isoformat()
        }
    
    # 执行更新操作（带重试）
    retry_count = 0
    while retry_count < max_retries:
        try:
            # 模拟更新操作（实际使用时替换为真实业务逻辑）
            result = _perform_update(params)
            
            if result:
                logger.info(f"更新成功：id={params['id']}")
                return {
                    'success': True,
                    'message': '更新成功',
                    'data': params['data'],
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logger.warning(f"更新返回空结果：id={params['id']}")
                retry_count += 1
                continue
                
        except Exception as e:
            logger.error(f"更新失败（尝试 {retry_count + 1}/{max_retries}）: {str(e)}")
            retry_count += 1
            if retry_count >= max_retries:
                return {
                    'success': False,
                    'message': f'更新失败：{str(e)}',
                    'timestamp': datetime.now().isoformat()
                }
    
    return {
        'success': False,
        'message': '达到最大重试次数',
        'timestamp': datetime.now().isoformat()
    }


def _perform_update(params: Dict[str, Any]) -> bool:
    """
    实际执行更新操作的内部函数
    实际使用时替换为真实的数据库或API调用
    """
    # 模拟更新逻辑
    if not params.get('id') or not params.get('data'):
        return False
    
    # 这里应该替换为实际的更新逻辑
    # 例如：数据库更新、API调用等
    logger.debug(f"执行更新：id={params['id']}, data={params['data']}")
    
    return True


def fix_update_flow(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    修复后的更新流程主函数
    
    Args:
        params: 更新参数
    
    Returns:
        更新结果字典
    """
    logger.info(f"开始执行更新流程，参数：{params}")
    result = execute_update(params)
    logger.info(f"更新流程完成，结果：{result['success']}")
    return result


# 测试验证
def test_fix():
    """测试修复后的更新功能"""
    # 测试用例1：正常更新
    test_params_1 = {
        'id': 'TC-001',
        'data': {'status': 'active', 'price': 99.99}
    }
    result_1 = fix_update_flow(test_params_1)
    assert result_1['success'] == True, "测试用例1失败"
    
    # 测试用例2：字符串数据
    test_params_2 = {
        'id': 'TC-002',
        'data': '{"status": "pending"}'
    }
    result_2 = fix_update_flow(test_params_2)
    assert result_2['success'] == True, "测试用例2失败"
    
    # 测试用例3：缺少必要字段
    test_params_3 = {
        'data': {'status': 'active'}
    }
    result_3 = fix_update_flow(test_params_3)
    assert result_3['success'] == False, "测试用例3失败"
    
    # 测试用例4：空id
    test_params_4 = {
        'id': '',
        'data': {'status': 'active'}
    }
    result_4 = fix_update_flow(test_params_4)
    assert result_4['success'] == False, "测试用例4失败"
    
    print("所有测试用例通过！")
    return True


if __name__ == '__main__':
    # 运行测试
    test_fix()
    
    # 示例使用
    example_params = {
        'id': 'ORDER-20240101-001',
        'data': {
            'status': 'shipped',
            'tracking_number': 'SF123456789'
        }
    }
    result = fix_update_flow(example_params)
    print(f"\n示例执行结果：{json.dumps(result, indent=2, ensure_ascii=False)}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
