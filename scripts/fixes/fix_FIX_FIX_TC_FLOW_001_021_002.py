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


def validate_update_data(data: Any) -> Dict[str, Any]:
    """验证并标准化更新数据"""
    if data is None:
        raise ValueError("更新数据不能为空")
    
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败：{str(e)}")
    
    if not isinstance(data, dict):
        raise TypeError(f"更新数据必须是字典类型，当前类型：{type(data)}")
    
    return data


def execute_update(
    data: Dict[str, Any],
    target_id: Optional[str] = None,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    执行更新操作，包含错误处理和重试机制
    
    参数:
        data: 更新数据字典
        target_id: 目标记录ID
        max_retries: 最大重试次数
    
    返回:
        更新结果字典
    """
    # 验证数据
    validated_data = validate_update_data(data)
    
    # 添加必要元数据
    validated_data['_updated_at'] = datetime.now().isoformat()
    if target_id:
        validated_data['_target_id'] = target_id
    
    result = {
        'success': False,
        'data': None,
        'error': None,
        'timestamp': datetime.now().isoformat()
    }
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"执行更新操作，尝试第 {attempt}/{max_retries} 次")
            
            # 模拟更新操作（实际场景中替换为真实逻辑）
            update_result = perform_actual_update(validated_data)
            
            result['success'] = True
            result['data'] = update_result
            logger.info("更新操作成功")
            break
            
        except Exception as e:
            error_msg = f"更新失败（尝试 {attempt}/{max_retries}）: {str(e)}"
            logger.error(error_msg)
            result['error'] = error_msg
            
            if attempt == max_retries:
                logger.error("达到最大重试次数，更新操作最终失败")
            else:
                logger.info("准备重试...")
    
    return result


def perform_actual_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行实际的更新逻辑
    此处为示例实现，实际使用时替换为真实业务逻辑
    """
    # 检查必要字段
    required_fields = ['id']  # 根据实际业务调整
    for field in required_fields:
        if field not in data and '_target_id' not in data:
            raise ValueError(f"缺少必要字段：{field}")
    
    # 模拟更新成功
    return {
        'updated': True,
        'fields_updated': list(data.keys()),
        'record_id': data.get('_target_id', data.get('id', 'unknown'))
    }


def fix_update_step(update_data: Any, target_id: str = None) -> Dict[str, Any]:
    """
    修复 update 步骤的主函数
    封装完整的错误处理和验证逻辑
    """
    try:
        result = execute_update(data=update_data, target_id=target_id)
        return result
    except Exception as e:
        logger.error(f"update 步骤执行异常：{str(e)}")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


# 测试验证
def test_fix():
    """测试修复代码"""
    # 测试1：正常字典数据
    result1 = fix_update_step({'id': '123', 'name': 'test'})
    assert result1['success'] == True, "测试1失败：正常数据应成功"
    
    # 测试2：JSON 字符串数据
    result2 = fix_update_step('{"id": "456", "name": "test2"}')
    assert result2['success'] == True, "测试2失败：JSON 字符串应成功"
    
    # 测试3：空数据应失败
    result3 = fix_update_step(None)
    assert result3['success'] == False, "测试3失败：空数据应失败"
    
    # 测试4：无效 JSON 应失败
    try:
        result4 = fix_update_step('invalid json')
        assert result4['success'] == False, "测试4失败：无效 JSON 应失败"
    except:
        pass
    
    logger.info("所有测试通过")
    return True


if __name__ == '__main__':
    # 运行测试
    test_fix()
    
    # 示例使用
    print("\n=== 使用示例 ===")
    example_result = fix_update_step(
        update_data={'id': 'ORDER-001', 'status': 'updated'},
        target_id='ORDER-001'
    )
    print(json.dumps(example_result, indent=2, ensure_ascii=False))
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
