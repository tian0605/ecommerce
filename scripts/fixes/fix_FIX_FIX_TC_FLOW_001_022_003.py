import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UpdateStepError(Exception):
    """更新步骤异常"""
    pass

def validate_update_data(data: Dict[str, Any]) -> bool:
    """验证更新数据的有效性"""
    if not isinstance(data, dict):
        return False
    if not data:
        return False
    return True

def execute_update(data: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    """
    执行更新操作，包含重试机制和异常处理
    
    Args:
        data: 更新数据字典
        max_retries: 最大重试次数
    
    Returns:
        更新结果字典
    """
    # 参数验证
    if not validate_update_data(data):
        raise UpdateStepError("更新数据无效或为空")
    
    result = {
        "success": False,
        "message": "",
        "timestamp": datetime.now().isoformat(),
        "data_updated": None
    }
    
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"执行更新操作，尝试次数：{attempt}/{max_retries}")
            
            # 模拟更新操作（实际场景中替换为真实业务逻辑）
            updated_data = perform_update_operation(data)
            
            result["success"] = True
            result["message"] = "更新成功"
            result["data_updated"] = updated_data
            logger.info("更新操作执行成功")
            break
            
        except Exception as e:
            last_error = str(e)
            logger.warning(f"更新操作失败，尝试 {attempt}/{max_retries}: {e}")
            
            if attempt == max_retries:
                result["success"] = False
                result["message"] = f"更新失败：{last_error}"
                logger.error(f"更新操作最终失败：{last_error}")
            else:
                # 重试前等待（实际可添加延时）
                continue
    
    return result

def perform_update_operation(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行实际的更新业务逻辑
    
    Args:
        data: 待更新的数据
    
    Returns:
        更新后的数据
    """
    # 这里根据实际业务需求实现更新逻辑
    # 示例：处理商品更新、订单更新等
    
    if "id" not in data and "item_id" not in data:
        raise UpdateStepError("缺少必要的标识字段(id 或 item_id)")
    
    # 模拟更新处理
    updated = data.copy()
    updated["updated_at"] = datetime.now().isoformat()
    updated["status"] = "updated"
    
    return updated

def fix_update_step(input_data: Any) -> Dict[str, Any]:
    """
    修复 update 步骤的主函数
    
    Args:
        input_data: 输入数据（可以是字典或 JSON 字符串）
    
    Returns:
        执行结果字典
    """
    # 处理输入数据格式
    if isinstance(input_data, str):
        try:
            data = json.loads(input_data)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "message": f"JSON 解析失败：{e}",
                "timestamp": datetime.now().isoformat()
            }
    elif isinstance(input_data, dict):
        data = input_data
    else:
        return {
            "success": False,
            "message": "输入数据格式不支持",
            "timestamp": datetime.now().isoformat()
        }
    
    # 执行更新操作
    result = execute_update(data)
    return result

# 测试验证
def test_fix():
    """测试修复代码"""
    # 测试用例 1: 正常字典输入
    test_data_1 = {"id": "12345", "name": "测试商品", "price": 99.99}
    result_1 = fix_update_step(test_data_1)
    assert result_1["success"] == True, "测试用例 1 失败"
    
    # 测试用例 2: JSON 字符串输入
    test_data_2 = json.dumps({"item_id": "67890", "status": "active"})
    result_2 = fix_update_step(test_data_2)
    assert result_2["success"] == True, "测试用例 2 失败"
    
    # 测试用例 3: 缺少必要字段
    test_data_3 = {"name": "无 ID 商品"}
    result_3 = fix_update_step(test_data_3)
    assert result_3["success"] == False, "测试用例 3 失败"
    
    # 测试用例 4: 无效 JSON 字符串
    test_data_4 = "invalid json {"
    result_4 = fix_update_step(test_data_4)
    assert result_4["success"] == False, "测试用例 4 失败"
    
    print("所有测试用例通过！")
    return True

if __name__ == "__main__":
    # 运行测试
    test_fix()
    
    # 示例：实际调用
    sample_data = {
        "id": "PROD-001",
        "name": "电商商品",
        "price": 199.00,
        "stock": 100
    }
    result = fix_update_step(sample_data)
    print(f"\n更新结果：{json.dumps(result, indent=2, ensure_ascii=False)}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
