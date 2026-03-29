import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UpdateOperationError(Exception):
    """更新操作异常"""
    pass


def validate_update_params(data: Dict[str, Any], required_fields: list = None) -> bool:
    """
    验证更新参数是否有效
    """
    if not isinstance(data, dict):
        logger.error(f"更新数据必须是字典类型，当前类型：{type(data)}")
        return False
    
    if not data:
        logger.error("更新数据不能为空")
        return False
    
    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"缺少必要字段：{missing_fields}")
            return False
    
    return True


def check_data_exists(data_id: Any, data_source: Any) -> bool:
    """
    检查数据是否存在
    """
    if data_source is None:
        logger.warning("数据源为空，跳过存在性检查")
        return True
    
    try:
        if hasattr(data_source, 'get'):
            return data_source.get(data_id) is not None
        elif isinstance(data_source, (list, tuple)):
            return any(item.get('id') == data_id for item in data_source if isinstance(item, dict))
        else:
            logger.warning("无法执行存在性检查")
            return True
    except Exception as e:
        logger.warning(f"存在性检查失败：{e}")
        return True


def safe_update(data: Dict[str, Any], 
                data_id: Any = None,
                data_source: Any = None,
                required_fields: list = None,
                max_retries: int = 3) -> Dict[str, Any]:
    """
    安全的更新操作函数
    
    参数:
        data: 要更新的数据字典
        data_id: 数据ID（主键）
        data_source: 数据源（用于存在性检查）
        required_fields: 必填字段列表
        max_retries: 最大重试次数
    
    返回:
        包含更新结果的字典
    """
    result = {
        'success': False,
        'message': '',
        'data': None,
        'timestamp': datetime.now().isoformat()
    }
    
    # 1. 验证参数类型
    if not validate_update_params(data, required_fields):
        result['message'] = '参数验证失败'
        return result
    
    # 2. 检查必要的主键字段
    if data_id is None and 'id' not in data and 'ID' not in data:
        logger.warning("未提供数据ID，尝试从数据中提取")
        data_id = data.get('id') or data.get('ID')
    
    if data_id is None:
        result['message'] = '缺少数据ID，无法执行更新'
        logger.error(result['message'])
        return result
    
    # 3. 检查数据是否存在
    if not check_data_exists(data_id, data_source):
        result['message'] = f'数据不存在，ID: {data_id}'
        logger.error(result['message'])
        return result
    
    # 4. 执行更新操作（带重试机制）
    retry_count = 0
    while retry_count < max_retries:
        try:
            # 模拟更新操作（实际使用时替换为真实的更新逻辑）
            updated_data = execute_update(data, data_id)
            
            result['success'] = True
            result['message'] = '更新成功'
            result['data'] = updated_data
            logger.info(f"更新成功，ID: {data_id}")
            break
            
        except Exception as e:
            retry_count += 1
            logger.warning(f"更新失败，重试 {retry_count}/{max_retries}: {e}")
            
            if retry_count >= max_retries:
                result['message'] = f'更新失败，已达最大重试次数：{e}'
                logger.error(result['message'])
    
    return result


def execute_update(data: Dict[str, Any], data_id: Any) -> Dict[str, Any]:
    """
    执行实际的更新操作
    
    注意：这是一个示例实现，实际使用时需要根据具体业务逻辑修改
    """
    if not isinstance(data, dict):
        raise UpdateOperationError("数据必须是字典类型")
    
    # 模拟更新操作
    updated_data = data.copy()
    updated_data['id'] = data_id
    updated_data['updated_at'] = datetime.now().isoformat()
    updated_data['status'] = 'updated'
    
    # 这里可以添加实际的数据库更新逻辑
    # 例如：db.collection.update_one({'id': data_id}, {'$set': data})
    
    return updated_data


def fix_update_flow(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    修复 update 流程的主函数
    
    参数:
        task_data: 任务数据，包含更新所需的所有信息
    
    返回:
        更新结果
    """
    # 提取更新参数
    data = task_data.get('data', {})
    data_id = task_data.get('id') or task_data.get('data_id')
    data_source = task_data.get('data_source')
    required_fields = task_data.get('required_fields', ['id'])
    
    # 执行安全更新
    result = safe_update(
        data=data,
        data_id=data_id,
        data_source=data_source,
        required_fields=required_fields
    )
    
    return result


# 测试验证
def test_fix():
    """测试修复代码"""
    print("开始测试 update 修复代码...")
    
    # 测试1：正常更新
    test_data_1 = {
        'data': {'name': 'test_product', 'price': 99.99},
        'id': 'PROD-001',
        'required_fields': ['name']
    }
    result_1 = fix_update_flow(test_data_1)
    assert result_1['success'] == True, f"测试1失败：{result_1['message']}"
    print("✓ 测试1通过：正常更新")
    
    # 测试2：缺少ID
    test_data_2 = {
        'data': {'name': 'test_product'},
        'required_fields': ['name']
    }
    result_2 = fix_update_flow(test_data_2)
    assert result_2['success'] == False, "测试2应该失败"
    print("✓ 测试2通过：缺少ID检测")
    
    # 测试3：空数据
    test_data_3 = {
        'data': {},
        'id': 'PROD-002'
    }
    result_3 = fix_update_flow(test_data_3)
    assert result_3['success'] == False, "测试3应该失败"
    print("✓ 测试3通过：空数据检测")
    
    # 测试4：参数类型错误
    test_data_4 = {
        'data': 'invalid_string',
        'id': 'PROD-003'
    }
    result_4 = fix_update_flow(test_data_4)
    assert result_4['success'] == False, "测试4应该失败"
    print("✓ 测试4通过：参数类型检测")
    
    print("\n所有测试通过！✓")
    return True


if __name__ == '__main__':
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
