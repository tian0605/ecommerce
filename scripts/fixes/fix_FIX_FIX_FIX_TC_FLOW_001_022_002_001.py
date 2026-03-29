from typing import Dict, Any

def process_ecommerce_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理电商数据函数
    修复了 name 'Dict' is not defined 错误，确保类型注解正确导入
    """
    # 模拟数据处理逻辑
    if not isinstance(data, dict):
        raise ValueError("Input must be a dictionary")
    return data

if __name__ == "__main__":
    # 测试验证
    try:
        sample_input = {"product_id": "TC-001", "status": "active"}
        result = process_ecommerce_data(sample_input)
        print(f"修复成功，函数执行无误：{result}")
    except NameError as e:
        print(f"修复失败：{e}")
    except Exception as e:
        print(f"其他错误：{e}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
