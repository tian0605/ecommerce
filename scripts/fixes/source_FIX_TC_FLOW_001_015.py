import json
from datetime import datetime
from typing import Dict, Any, Optional

def fix_update_data(data: Any, required_fields: list = None) -> Dict[str, Any]:
    """
    修复电商运营数据更新操作
    处理常见的 update 失败问题：数据格式、必填字段、空值等
    """
    if required_fields is None:
        required_fields = ['id']
    
    # 1. 处理字符串类型的 JSON 数据
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败：{str(e)}")
    
    # 2. 确保数据是字典类型
    if not isinstance(data, dict):
        raise TypeError(f"数据必须是字典类型，当前类型：{type(data)}")
    
    # 3. 验证必填字段
    for field in required_fields:
        if field not in data or data[field] is None:
            raise ValueError(f"缺少必填字段：{field}")
    
    # 4. 清理空值和无效数据
    cleaned_data = {}
    for key, value in data.items():
        if value is not None:
            # 处理特殊类型
            if isinstance(value, datetime):
                cleaned_data[key] = value.isoformat()
            elif isinstance(value, (list, dict)):
                cleaned_data[key] = value
            else:
                cleaned_data[key] = value
    
    # 5. 添加更新时间戳
    cleaned_data['updated_at'] = datetime.now().isoformat()
    
    return cleaned_data


def safe_update(data_source: Dict, update_data: Any, 
                required_fields: list = None) -> Dict[str, Any]:
    """
    安全执行更新操作，包含完整的错误处理
    """
    try:
        # 修复更新数据
        fixed_data = fix_update_data(update_data, required_fields)
        
        # 获取记录 ID
        record_id = fixed_data.get('id')
        
        # 验证数据源中是否存在该记录
        if record_id not in data_source:
            raise KeyError(f"记录不存在：id={record_id}")
        
        # 执行更新（保留原有数据，只更新提供的字段）
        original_data = data_source[record_id].copy()
        original_data.update(fixed_data)
        
        # 标记更新成功
        original_data['update_status'] = 'success'
        
        return {
            'success': True,
            'data': original_data,
            'message': '更新成功'
        }
        
    except Exception as e:
        return {
            'success': False,
            'data': None,
            'message': f'更新失败：{str(e)}',
            'error_type': type(e).__name__
        }


# 测试验证
def test_fix():
    """测试修复代码功能"""
    # 测试数据源
    data_source = {
        '001': {'id': '001', 'name': '商品 A', 'price': 100},
        '002': {'id': '002', 'name': '商品 B', 'price': 200}
    }
    
    # 测试 1: 正常更新
    update_data = {'id': '001', 'price': 150, 'stock': 50}
    result1 = safe_update(data_source, update_data)
    assert result1['success'] == True, "测试 1 失败"
    
    # 测试 2: 字符串 JSON 更新
    update_data_str = '{"id": "002", "price": 250}'
    result2 = safe_update(data_source, update_data_str)
    assert result2['success'] == True, "测试 2 失败"
    
    # 测试 3: 缺少必填字段
    update_data_invalid = {'price': 300}
    result3 = safe_update(data_source, update_data_invalid)
    assert result3['success'] == False, "测试 3 失败"
    
    # 测试 4: 记录不存在
    update_data_notexist = {'id': '999', 'price': 100}
    result4 = safe_update(data_source, update_data_notexist)
    assert result4['success'] == False, "测试 4 失败"
    
    return True


if __name__ == '__main__':
    # 运行测试
    test_result = test_fix()
    print(f"所有测试通过：{test_result}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
