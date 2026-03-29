import json
import os
import time
from typing import Any, Dict, Optional
from datetime import datetime

class StoreOperationError(Exception):
    """存储操作异常"""
    pass

def fix_store_operation(data: Any, store_path: str = None, store_type: str = "json", 
                        max_retries: int = 3, timeout: int = 5) -> Dict[str, Any]:
    """
    修复 store 存储操作失败问题
    
    参数:
        data: 要存储的数据
        store_path: 存储路径（文件或数据库连接字符串）
        store_type: 存储类型 (json/file/memory)
        max_retries: 最大重试次数
        timeout: 每次重试间隔秒数
    
    返回:
        包含存储结果的字典
    """
    result = {
        "success": False,
        "error": None,
        "timestamp": datetime.now().isoformat(),
        "data_size": 0
    }
    
    # 1. 数据验证
    if data is None:
        result["error"] = "存储数据不能为空"
        return result
    
    # 2. 计算数据大小
    try:
        if isinstance(data, (dict, list)):
            result["data_size"] = len(json.dumps(data))
        elif isinstance(data, str):
            result["data_size"] = len(data)
        else:
            result["data_size"] = len(str(data))
    except Exception:
        result["data_size"] = 0
    
    # 3. 执行存储操作（带重试机制）
    for attempt in range(1, max_retries + 1):
        try:
            if store_type == "json":
                _store_json(data, store_path)
            elif store_type == "file":
                _store_file(data, store_path)
            elif store_type == "memory":
                _store_memory(data)
            else:
                raise StoreOperationError(f"不支持的存储类型：{store_type}")
            
            result["success"] = True
            result["attempt"] = attempt
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["attempt"] = attempt
            
            if attempt < max_retries:
                time.sleep(timeout)
            else:
                break
    
    return result


def _store_json(data: Any, store_path: str = None) -> None:
    """存储为 JSON 格式"""
    if store_path is None:
        store_path = f"./store_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # 确保目录存在
    dir_path = os.path.dirname(store_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    
    with open(store_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _store_file(data: Any, store_path: str = None) -> None:
    """存储为文件"""
    if store_path is None:
        store_path = f"./store_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    dir_path = os.path.dirname(store_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    
    with open(store_path, 'w', encoding='utf-8') as f:
        f.write(str(data))


def _store_memory(data: Any) -> None:
    """内存存储（模拟）"""
    # 内存存储通常不会失败，这里做数据序列化验证
    json.dumps(data)


def validate_store_result(result: Dict[str, Any]) -> bool:
    """验证存储结果是否成功"""
    return result.get("success", False) is True


# 测试验证
def test_fix():
    """测试修复代码"""
    test_data = {"order_id": "ORD001", "status": "completed", "amount": 100.00}
    
    # 测试 JSON 存储
    result = fix_store_operation(test_data, store_type="json")
    assert validate_store_result(result), f"存储失败：{result['error']}"
    
    # 测试空数据
    empty_result = fix_store_operation(None, store_type="json")
    assert not validate_store_result(empty_result), "空数据应该失败"
    assert "不能为空" in empty_result["error"]
    
    # 测试内存存储
    memory_result = fix_store_operation(test_data, store_type="memory")
    assert validate_store_result(memory_result), "内存存储应该成功"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
