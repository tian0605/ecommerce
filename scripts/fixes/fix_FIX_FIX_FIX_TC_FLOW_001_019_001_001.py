from typing import Optional

def process_ecommerce_data(item_id: str, coupon_code: Optional[str] = None) -> dict:
    """
    处理电商数据，修复 Optional 未定义错误
    :param item_id: 商品ID
    :param coupon_code: 优惠券代码，可选
    :return: 处理结果字典
    """
    result = {
        "item_id": item_id,
        "coupon_code": coupon_code,
        "status": "success"
    }
    return result

if __name__ == "__main__":
    # 测试验证
    try:
        # 测试不带优惠券的情况
        res1 = process_ecommerce_data("ITEM_001")
        print(f"测试 1 成功：{res1}")
        
        # 测试带优惠券的情况
        res2 = process_ecommerce_data("ITEM_002", "SAVE10")
        print(f"测试 2 成功：{res2}")
        
        print("所有测试通过，Optional 导入修复成功。")
    except NameError as e:
        print(f"修复失败，仍然存在错误：{e}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
