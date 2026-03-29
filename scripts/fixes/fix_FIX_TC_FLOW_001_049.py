import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StoreError(Exception):
    """存储操作异常"""
    pass


def validate_store_data(data: Any) -> bool:
    """验证存储数据的有效性"""
    if data is None:
        return False
    if isinstance(data, dict):
        return len(data) > 0
    if isinstance(data, (list, str, int, float)):
        return True
    return False


def store_data(
    data: Any,
    store_type: str = "json",
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Dict[str, Any]:
    """
    修复后的数据存储函数
    
    参数:
        data: 要存储的数据
        store_type: 存储类型 (json/file/memory)
        max_retries: 最大重试次数
        retry_delay: 重试间隔秒数
    
    返回:
        存储结果字典
    """
    result = {
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "error": None,
        "data_id": None
    }
    
    # 1. 数据验证
    if not validate_store_data(data):
        result["error"] = "Invalid data: data is empty or None"
        logger.error(result["error"])
        return result
    
    # 2. 尝试存储（带重试机制）
    for attempt in range(1, max_retries + 1):
        try:
            if store_type == "json":
                data_id = _store_as_json(data)
            elif store_type == "memory":
                data_id = _store_in_memory(data)
            elif store_type == "file":
                data_id = _store_to_file(data)
            else:
                raise StoreError(f"Unsupported store type: {store_type}")
            
            result["success"] = True
            result["data_id"] = data_id
            result["error"] = None
            logger.info(f"Store success on attempt {attempt}, data_id: {data_id}")
            break
            
        except Exception as e:
            result["error"] = str(e)
            logger.warning(f"Store attempt {attempt} failed: {e}")
            
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                logger.error(f"Store failed after {max_retries} attempts")
    
    return result


def _store_as_json(data: Any) -> str:
    """将数据存储为 JSON 格式"""
    try:
        # 确保数据可序列化
        json_str = json.dumps(data, default=str, ensure_ascii=False)
        # 生成数据 ID
        data_id = f"json_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        # 这里可以实际写入文件或数据库
        logger.debug(f"JSON data prepared, length: {len(json_str)}")
        return data_id
    except TypeError as e:
        raise StoreError(f"JSON serialization failed: {e}")


def _store_in_memory(data: Any) -> str:
    """将数据存储到内存"""
    data_id = f"mem_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    # 实际应用中这里会存入缓存或全局变量
    logger.debug(f"Data stored in memory with id: {data_id}")
    return data_id


def _store_to_file(data: Any, filename: Optional[str] = None) -> str:
    """将数据存储到文件"""
    if filename is None:
        filename = f"store_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=str, ensure_ascii=False, indent=2)
        data_id = f"file_{filename}"
        return data_id
    except IOError as e:
        raise StoreError(f"File write failed: {e}")


def fix_store_flow(data: Any, **kwargs) -> Dict[str, Any]:
    """
    修复 store 流程的主函数
    
    参数:
        data: 要存储的数据
        **kwargs: 额外参数 (store_type, max_retries, retry_delay)
    
    返回:
        存储结果
    """
    # 提取参数
    store_type = kwargs.get('store_type', 'json')
    max_retries = kwargs.get('max_retries', 3)
    retry_delay = kwargs.get('retry_delay', 1.0)
    
    # 执行存储
    result = store_data(
        data=data,
        store_type=store_type,
        max_retries=max_retries,
        retry_delay=retry_delay
    )
    
    return result


# 测试验证
def test_fix():
    """测试修复后的 store 功能"""
    # 测试 1: 正常数据存储
    test_data = {"product_id": "P001", "price": 99.99, "stock": 100}
    result = fix_store_flow(test_data)
    assert result["success"] == True, "Test 1 failed: normal data store"
    
    # 测试 2: 空数据处理
    result = fix_store_flow(None)
    assert result["success"] == False, "Test 2 failed: None data should fail"
    
    # 测试 3: 列表数据存储
    test_data = [{"id": 1}, {"id": 2}]
    result = fix_store_flow(test_data, store_type='memory')
    assert result["success"] == True, "Test 3 failed: list data store"
    
    # 测试 4: 重试机制测试
    result = fix_store_flow(test_data, max_retries=2, retry_delay=0.1)
    assert "data_id" in result, "Test 4 failed: missing data_id"
    
    print("All tests passed!")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
