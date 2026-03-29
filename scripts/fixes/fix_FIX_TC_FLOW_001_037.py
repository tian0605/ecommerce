import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_update_data(data: Dict[str, Any], required_fields: list = None) -> bool:
    """验证更新数据的有效性"""
    if not isinstance(data, dict):
        logger.error("更新数据必须是字典类型")
        return False
    
    if not data:
        logger.error("更新数据不能为空")
        return False
    
    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"缺少必填字段：{missing_fields}")
            return False
    
    return True


def execute_update(
    data: Dict[str, Any],
    target_id: str,
    max_retries: int = 3,
    required_fields: list = None
) -> Dict[str, Any]:
    """
    执行更新操作，包含验证、重试和错误处理
    
    参数:
        data: 更新数据字典
        target_id: 目标记录ID
        max_retries: 最大重试次数
        required_fields: 必填字段列表
    
    返回:
        包含执行结果的字典
    """
    result = {
        "success": False,
        "target_id": target_id,
        "timestamp": datetime.now().isoformat(),
        "error": None,
        "retries": 0
    }
    
    # 参数验证
    if not validate_update_data(data, required_fields):
        result["error"] = "数据验证失败"
        return result
    
    if not target_id:
        result["error"] = "目标ID不能为空"
        return result
    
    # 执行更新（带重试机制）
    for attempt in range(1, max_retries + 1):
        try:
            result["retries"] = attempt
            logger.info(f"执行更新操作，尝试第 {attempt} 次，目标ID: {target_id}")
            
            # 模拟更新操作（实际使用时替换为真实的API调用）
            update_success = perform_actual_update(data, target_id)
            
            if update_success:
                result["success"] = True
                result["error"] = None
                logger.info(f"更新成功，目标ID: {target_id}")
                break
            else:
                raise Exception("更新操作返回失败状态")
                
        except Exception as e:
            result["error"] = str(e)
            logger.warning(f"更新尝试 {attempt} 失败：{str(e)}")
            
            if attempt < max_retries:
                logger.info(f"准备重试，等待 1 秒...")
                import time
                time.sleep(1)
            else:
                logger.error(f"更新失败，已达到最大重试次数 {max_retries}")
    
    return result


def perform_actual_update(data: Dict[str, Any], target_id: str) -> bool:
    """
    实际执行更新操作的函数
    此处为模拟实现，实际使用时替换为真实的数据库或API调用
    """
    # 模拟更新逻辑
    if not data or not target_id:
        return False
    
    # 这里应该替换为实际的更新逻辑，例如：
    # - 数据库更新：db.collection.update_one({"_id": target_id}, {"$set": data})
    # - API调用：requests.put(url, json=data)
    
    # 模拟成功
    logger.debug(f"模拟更新数据：{json.dumps(data, ensure_ascii=False)}")
    return True


def fix_update_flow(
    update_data: Any,
    record_id: str,
    required_fields: list = None
) -> Dict[str, Any]:
    """
    修复后的更新流程主函数
    
    参数:
        update_data: 更新数据（支持字符串或字典）
        record_id: 记录ID
        required_fields: 必填字段列表
    
    返回:
        执行结果字典
    """
    # 处理字符串类型的输入
    if isinstance(update_data, str):
        try:
            update_data = json.loads(update_data)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败：{str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    # 确保是字典类型
    if not isinstance(update_data, dict):
        return {
            "success": False,
            "error": "更新数据必须是字典或可解析的JSON字符串",
            "timestamp": datetime.now().isoformat()
        }
    
    # 执行更新
    return execute_update(
        data=update_data,
        target_id=record_id,
        max_retries=3,
        required_fields=required_fields
    )


# 测试验证
def test_fix():
    """测试修复后的更新功能"""
    print("开始测试更新修复功能...")
    
    # 测试1：正常字典数据
    result1 = fix_update_flow(
        update_data={"status": "active", "price": 99.99},
        record_id="TC-001"
    )
    assert result1["success"] == True, "测试1失败：正常数据更新应成功"
    print("✓ 测试1通过：正常字典数据更新")
    
    # 测试2：JSON字符串数据
    result2 = fix_update_flow(
        update_data='{"status": "pending", "quantity": 100}',
        record_id="TC-002"
    )
    assert result2["success"] == True, "测试2失败：JSON字符串更新应成功"
    print("✓ 测试2通过：JSON字符串数据更新")
    
    # 测试3：空数据
    result3 = fix_update_flow(
        update_data={},
        record_id="TC-003"
    )
    assert result3["success"] == False, "测试3失败：空数据应失败"
    print("✓ 测试3通过：空数据正确拒绝")
    
    # 测试4：空ID
    result4 = fix_update_flow(
        update_data={"status": "active"},
        record_id=""
    )
    assert result4["success"] == False, "测试4失败：空ID应失败"
    print("✓ 测试4通过：空ID正确拒绝")
    
    # 测试5：必填字段验证
    result5 = fix_update_flow(
        update_data={"price": 99.99},
        record_id="TC-005",
        required_fields=["status", "price"]
    )
    assert result5["success"] == False, "测试5失败：缺少必填字段应失败"
    print("✓ 测试5通过：必填字段验证正确")
    
    print("\n所有测试通过！修复代码验证成功。")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
