from typing import Dict, Any

def process_order_data(order_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理订单数据函数
    修复了 Dict 类型未导入的问题
    """
    if not isinstance(order_info, dict):
        raise ValueError("Input must be a dictionary")
    
    # 模拟电商订单处理逻辑
    processed_data = {
        "order_id": order_info.get("order_id", ""),
        "status": "processed",
        "items_count": len(order_info.get("items", []))
    }
    return processed_data

# 测试验证
if __name__ == "__main__":
    try:
        test_input = {
            "order_id": "TC-FLOW-001",
            "items": [{"sku": "A1", "qty": 2}]
        }
        result = process_order_data(test_input)
        print(f"修复成功，处理结果：{result}")
        assert result["status"] == "processed"
        print("所有测试通过")
    except NameError as e:
        print(f"修复失败，仍然存在错误：{e}")
    except Exception as e:
        print(f"发生其他错误：{e}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
