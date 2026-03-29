import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_update_data(data: Dict[str, Any], required_fields: list) -> bool:
    """验证更新数据是否包含必需字段"""
    if not isinstance(data, dict):
        logger.error("数据格式错误：必须是字典类型")
        return False
    
    for field in required_fields:
        if field not in data:
            logger.error(f"缺少必需字段：{field}")
            return False
    
    return True


def execute_update(
    table_name: str,
    update_data: Dict[str, Any],
    condition: Dict[str, Any],
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    执行安全的 update 操作，包含验证和重试机制
    
    参数:
        table_name: 表名
        update_data: 要更新的数据
        condition: 更新条件
        max_retries: 最大重试次数
    
    返回:
        包含执行结果的字典
    """
    # 定义必需字段
    required_fields = ['id']  # 根据实际业务调整
    
    result = {
        'success': False,
        'message': '',
        'timestamp': datetime.now().isoformat(),
        'table': table_name,
        'retries': 0
    }
    
    # 参数验证
    if not table_name or not isinstance(table_name, str):
        result['message'] = '表名无效'
        return result
    
    if not isinstance(update_data, dict):
        result['message'] = '更新数据必须是字典格式'
        return result
    
    if not isinstance(condition, dict):
        result['message'] = '更新条件必须是字典格式'
        return result
    
    # 验证必需字段
    if not validate_update_data(update_data, required_fields):
        result['message'] = '数据验证失败'
        return result
    
    # 执行更新（带重试）
    for attempt in range(max_retries):
        try:
            result['retries'] = attempt + 1
            
            # 模拟数据库更新操作
            # 实际使用时替换为真实的数据库操作
            success = _perform_database_update(table_name, update_data, condition)
            
            if success:
                result['success'] = True
                result['message'] = '更新成功'
                logger.info(f"Update successful: {table_name}, attempt {attempt + 1}")
                break
            else:
                logger.warning(f"Update failed, attempt {attempt + 1}/{max_retries}")
                
        except Exception as e:
            logger.error(f"Update error: {str(e)}, attempt {attempt + 1}/{max_retries}")
            result['message'] = f'更新异常：{str(e)}'
            
            if attempt == max_retries - 1:
                result['message'] = f'更新失败，已重试{max_retries}次'
    
    return result


def _perform_database_update(
    table_name: str,
    update_data: Dict[str, Any],
    condition: Dict[str, Any]
) -> bool:
    """
    执行实际的数据库更新操作
    此处为模拟实现，实际使用时替换为真实数据库操作
    """
    # 模拟更新逻辑
    if not update_data or not condition:
        return False
    
    # 检查是否有可更新的字段
    if len(update_data) == 0:
        return False
    
    # 模拟成功
    return True


def fix_update_flow(
    table_name: str,
    data: Any,
    condition: Any
) -> Dict[str, Any]:
    """
    修复 update 流程的主函数
    处理各种可能的输入格式问题
    """
    # 处理字符串格式的输入
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'message': f'数据解析失败：{str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    if isinstance(condition, str):
        try:
            condition = json.loads(condition)
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'message': f'条件解析失败：{str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    # 确保是字典类型
    if not isinstance(data, dict):
        data = {'data': data}
    
    if not isinstance(condition, dict):
        condition = {'id': condition}
    
    # 执行更新
    return execute_update(table_name, data, condition)


# 测试验证
def test_fix():
    """测试修复后的 update 功能"""
    print("测试 1: 正常更新")
    result1 = fix_update_flow(
        'orders',
        {'id': 1, 'status': 'completed'},
        {'id': 1}
    )
    assert result1['success'] == True
    print(f"结果：{result1['message']}")
    
    print("\n测试 2: 字符串格式输入")
    result2 = fix_update_flow(
        'orders',
        '{"id": 2, "status": "pending"}',
        '{"id": 2}'
    )
    assert result2['success'] == True
    print(f"结果：{result2['message']}")
    
    print("\n测试 3: 缺少必需字段")
    result3 = fix_update_flow(
        'orders',
        {'status': 'pending'},  # 缺少 id
        {'id': 3}
    )
    assert result3['success'] == False
    print(f"结果：{result3['message']}")
    
    print("\n所有测试通过！")
    return True


if __name__ == '__main__':
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
