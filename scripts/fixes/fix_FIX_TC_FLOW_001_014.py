import json
import logging
import time
from typing import Any, Dict, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StoreError(Exception):
    """存储操作异常"""
    pass


def validate_store_data(data: Dict) -> bool:
    """验证存储数据的有效性"""
    if not isinstance(data, dict):
        return False
    if not data:
        logger.warning("存储数据为空")
        return False
    return True


def serialize_data(data: Any) -> str:
    """安全序列化数据"""
    try:
        # 处理 datetime 对象
        def default_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        return json.dumps(data, default=default_serializer, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.error(f"数据序列化失败: {e}")
        raise StoreError(f"序列化错误: {e}")


def store_with_retry(
    data: Dict,
    store_func: callable,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> bool:
    """带重试机制的存储操作"""
    if not validate_store_data(data):
        return False
    
    serialized_data = serialize_data(data)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"执行存储操作，尝试 {attempt + 1}/{max_retries}")
            store_func(serialized_data)
            logger.info("存储操作成功")
            return True
        except Exception as e:
            logger.warning(f"存储尝试 {attempt + 1} 失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                logger.error(f"存储操作最终失败: {e}")
                raise StoreError(f"存储失败，已重试 {max_retries} 次: {e}")
    
    return False


def fix_store_operation(data: Optional[Dict] = None) -> Dict:
    """
    修复 store 操作的主函数
    处理常见的存储失败问题
    """
    result = {
        "success": False,
        "message": "",
        "data": None
    }
    
    try:
        # 1. 验证输入数据
        if data is None:
            data = {}
            logger.info("使用空数据执行存储")
        
        if not isinstance(data, dict):
            try:
                if isinstance(data, str):
                    data = json.loads(data)
                else:
                    data = dict(data)
            except Exception as e:
                result["message"] = f"数据转换失败: {e}"
                return result
        
        # 2. 添加必要的时间戳
        if "timestamp" not in data:
            data["timestamp"] = datetime.now().isoformat()
        
        # 3. 添加操作标识
        if "operation_id" not in data:
            data["operation_id"] = f"STORE_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 4. 执行存储（模拟存储函数）
        def mock_store_func(serialized_data: str):
            """模拟存储函数，实际使用时替换为真实存储逻辑"""
            # 这里可以替换为实际的数据库/缓存存储操作
            # 例如：redis.set(key, value) 或 db.insert(data)
            if not serialized_data:
                raise ValueError("存储数据为空")
            # 模拟成功
            return True
        
        # 5. 执行带重试的存储
        success = store_with_retry(data, mock_store_func)
        
        if success:
            result["success"] = True
            result["message"] = "存储操作成功完成"
            result["data"] = data
        else:
            result["message"] = "存储操作失败"
            
    except StoreError as e:
        result["message"] = str(e)
        logger.error(f"StoreError: {e}")
    except Exception as e:
        result["message"] = f"未知错误: {e}"
        logger.exception(f"Unexpected error: {e}")
    
    return result


# 测试验证
def test_fix_store():
    """测试修复后的存储功能"""
    # 测试用例 1: 正常数据
    test_data_1 = {"product_id": "P001", "quantity": 100, "price": 99.99}
    result_1 = fix_store_operation(test_data_1)
    assert result_1["success"] == True, f"测试 1 失败: {result_1}"
    
    # 测试用例 2: 空数据
    result_2 = fix_store_operation(None)
    assert result_2["success"] == True, f"测试 2 失败: {result_2}"
    
    # 测试用例 3: 字符串数据
    test_data_3 = '{"order_id": "O001", "status": "pending"}'
    result_3 = fix_store_operation(test_data_3)
    assert result_3["success"] == True, f"测试 3 失败: {result_3}"
    
    # 测试用例 4: 带时间戳的数据
    test_data_4 = {
        "item_id": "I001",
        "timestamp": datetime.now().isoformat()
    }
    result_4 = fix_store_operation(test_data_4)
    assert result_4["success"] == True, f"测试 4 失败: {result_4}"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    # 运行测试
    test_fix_store()
    
    # 示例使用
    sample_data = {
        "store_name": "旗舰店",
        "product_count": 1500,
        "daily_sales": 25000.00
    }
    
    result = fix_store_operation(sample_data)
    print(f"\n存储结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
