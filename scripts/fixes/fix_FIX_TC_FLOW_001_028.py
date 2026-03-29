import json
import time
from typing import Any, Dict, Optional
from datetime import datetime

class StoreError(Exception):
    """存储操作异常"""
    pass

def validate_store_data(data: Dict[str, Any]) -> bool:
    """验证存储数据的有效性"""
    if not isinstance(data, dict):
        return False
    if not data:
        return False
    return True

def fix_store_operation(data: Dict[str, Any], 
                        store_type: str = 'json',
                        max_retries: int = 3,
                        timeout: int = 5) -> Dict[str, Any]:
    """
    修复并执行存储操作
    
    参数:
        data: 待存储的数据
        store_type: 存储类型 (json/file/memory)
        max_retries: 最大重试次数
        timeout: 每次操作超时时间
    
    返回:
        存储结果字典
    """
    result = {
        'success': False,
        'message': '',
        'data': None,
        'timestamp': datetime.now().isoformat()
    }
    
    # 1. 验证输入数据
    if not validate_store_data(data):
        result['message'] = '无效的数据格式，需要非空字典'
        return result
    
    # 2. 数据预处理 - 确保可序列化
    try:
        processed_data = preprocess_store_data(data)
    except Exception as e:
        result['message'] = f'数据预处理失败：{str(e)}'
        return result
    
    # 3. 执行存储操作（带重试机制）
    for attempt in range(max_retries):
        try:
            stored_data = execute_store(processed_data, store_type)
            result['success'] = True
            result['message'] = f'存储成功（尝试次数：{attempt + 1}）'
            result['data'] = stored_data
            break
        except Exception as e:
            if attempt == max_retries - 1:
                result['message'] = f'存储失败（最大重试次数）：{str(e)}'
            else:
                time.sleep(timeout * (attempt + 1) * 0.1)  # 指数退避
                continue
    
    return result

def preprocess_store_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """预处理存储数据，确保可序列化"""
    processed = {}
    for key, value in data.items():
        # 转换键为字符串
        str_key = str(key) if not isinstance(key, str) else key
        
        # 处理特殊数据类型
        if isinstance(value, datetime):
            processed[str_key] = value.isoformat()
        elif isinstance(value, (set, tuple)):
            processed[str_key] = list(value)
        elif isinstance(value, bytes):
            processed[str_key] = value.decode('utf-8', errors='ignore')
        elif isinstance(value, dict):
            processed[str_key] = preprocess_store_data(value)
        elif isinstance(value, list):
            processed[str_key] = [
                preprocess_store_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            try:
                json.dumps(value)  # 测试是否可序列化
                processed[str_key] = value
            except (TypeError, ValueError):
                processed[str_key] = str(value)
    
    return processed

def execute_store(data: Dict[str, Any], store_type: str) -> Dict[str, Any]:
    """执行实际存储操作"""
    if store_type == 'json':
        # JSON 存储验证
        json_str = json.dumps(data, ensure_ascii=False, default=str)
        return {'type': 'json', 'size': len(json_str), 'data': data}
    elif store_type == 'memory':
        # 内存存储
        return {'type': 'memory', 'data': data}
    elif store_type == 'file':
        # 文件存储模拟
        return {'type': 'file', 'data': data}
    else:
        raise StoreError(f'不支持的存储类型：{store_type}')

def test_fix_store():
    """测试存储修复功能"""
    # 测试用例1：正常数据
    test_data1 = {
        'product_id': 'P001',
        'price': 99.99,
        'stock': 100,
        'created_at': datetime.now()
    }
    result1 = fix_store_operation(test_data1)
    assert result1['success'] == True, f"测试1失败：{result1['message']}"
    
    # 测试用例2：包含特殊类型的数据
    test_data2 = {
        'tags': {'a', 'b', 'c'},
        'metadata': (1, 2, 3),
        'nested': {'key': 'value'}
    }
    result2 = fix_store_operation(test_data2)
    assert result2['success'] == True, f"测试2失败：{result2['message']}"
    
    # 测试用例3：无效数据
    test_data3 = {}
    result3 = fix_store_operation(test_data3)
    assert result3['success'] == False, "测试3应该失败"
    
    # 测试用例4：非字典数据
    result4 = fix_store_operation("invalid")  # type: ignore
    assert result4['success'] == False, "测试4应该失败"
    
    return True

# 主执行入口
if __name__ == '__main__':
    print("开始测试 store 修复功能...")
    test_result = test_fix_store()
    print(f"测试结果：{'通过' if test_result else '失败'}")
    
    # 示例使用
    sample_data = {
        'order_id': 'ORD20240101001',
        'amount': 299.00,
        'status': 'pending',
        'items': [
            {'sku': 'SKU001', 'qty': 2},
            {'sku': 'SKU002', 'qty': 1}
        ]
    }
    
    store_result = fix_store_operation(sample_data)
    print(f"\n存储结果：{json.dumps(store_result, ensure_ascii=False, indent=2)}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
