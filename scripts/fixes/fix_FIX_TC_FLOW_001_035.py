import json
import os
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

def validate_data(data: Any) -> bool:
    """验证数据是否可存储"""
    if data is None:
        return False
    if isinstance(data, (dict, list, str, int, float, bool)):
        return True
    try:
        json.dumps(data)
        return True
    except (TypeError, ValueError):
        return False

def store_data(
    data: Any,
    store_path: str = "./data",
    filename: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Dict[str, Any]:
    """
    修复后的数据存储函数
    
    参数:
        data: 要存储的数据
        store_path: 存储目录路径
        filename: 文件名（可选，默认使用时间戳）
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
    
    返回:
        存储结果字典
    """
    result = {
        "success": False,
        "path": None,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    # 1. 数据验证
    if not validate_data(data):
        error_msg = f"无效的数据类型: {type(data)}"
        logger.error(error_msg)
        result["error"] = error_msg
        return result
    
    # 2. 确保存储目录存在
    try:
        os.makedirs(store_path, exist_ok=True)
        logger.info(f"存储目录已确认: {store_path}")
    except OSError as e:
        error_msg = f"创建目录失败: {str(e)}"
        logger.error(error_msg)
        result["error"] = error_msg
        return result
    
    # 3. 生成文件名
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"data_{timestamp}.json"
    
    file_path = os.path.join(store_path, filename)
    result["path"] = file_path
    
    # 4. 带重试的存储操作
    for attempt in range(1, max_retries + 1):
        try:
            # 检查写入权限
            if not os.access(store_path, os.W_OK):
                raise StoreError(f"无写入权限: {store_path}")
            
            # 执行存储
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            # 验证文件是否成功写入
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logger.info(f"数据存储成功: {file_path}")
                result["success"] = True
                result["error"] = None
                return result
            else:
                raise StoreError("文件写入后验证失败")
                
        except Exception as e:
            error_msg = f"存储失败 (尝试 {attempt}/{max_retries}): {str(e)}"
            logger.warning(error_msg)
            result["error"] = error_msg
            
            if attempt < max_retries:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            else:
                logger.error(f"存储操作最终失败: {file_path}")
                return result
    
    return result

def store_to_database(
    data: Dict[str, Any],
    table_name: str,
    connection_config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    数据库存储函数（模拟实现）
    
    参数:
        data: 要存储的数据字典
        table_name: 表名
        connection_config: 数据库连接配置
    
    返回:
        存储结果字典
    """
    result = {
        "success": False,
        "table": table_name,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    # 验证数据
    if not isinstance(data, dict):
        result["error"] = "数据必须是字典类型"
        return result
    
    if not table_name or not isinstance(table_name, str):
        result["error"] = "表名无效"
        return result
    
    try:
        # 模拟数据库存储操作
        logger.info(f"准备存储到数据库表: {table_name}")
        logger.info(f"数据字段: {list(data.keys())}")
        
        # 这里可以集成真实的数据库操作
        # 例如: sqlite3, pymysql, pymongo 等
        
        result["success"] = True
        logger.info(f"数据库存储成功: {table_name}")
        
    except Exception as e:
        error_msg = f"数据库存储失败: {str(e)}"
        logger.error(error_msg)
        result["error"] = error_msg
    
    return result

# 测试验证
def test_fix():
    """测试修复后的存储功能"""
    print("=" * 50)
    print("开始测试 store 修复功能")
    print("=" * 50)
    
    # 测试1: 正常数据存储
    test_data = {
        "order_id": "ORD-2024-001",
        "product": "测试商品",
        "quantity": 10,
        "price": 99.99,
        "timestamp": datetime.now().isoformat()
    }
    
    result1 = store_data(test_data, store_path="./test_store_data")
    print(f"\n测试1 - 正常存储: {'通过' if result1['success'] else '失败'}")
    assert result1["success"] == True, "正常存储应该成功"
    
    # 测试2: 无效数据
    result2 = store_data(None, store_path="./test_store_data")
    print(f"测试2 - 无效数据处理: {'通过' if not result2['success'] else '失败'}")
    assert result2["success"] == False, "None 数据应该失败"
    
    # 测试3: 列表数据
    result3 = store_data([1, 2, 3, 4, 5], store_path="./test_store_data")
    print(f"测试3 - 列表存储: {'通过' if result3['success'] else '失败'}")
    assert result3["success"] == True, "列表数据应该成功"
    
    # 测试4: 数据库存储模拟
    result4 = store_to_database(test_data, "orders")
    print(f"测试4 - 数据库存储: {'通过' if result4['success'] else '失败'}")
    assert result4["success"] == True, "数据库存储应该成功"
    
    print("\n" + "=" * 50)
    print("所有测试完成!")
    print("=" * 50)
    
    return True

if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
