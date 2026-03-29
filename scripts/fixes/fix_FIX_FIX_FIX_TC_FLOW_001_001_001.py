from typing import Optional

def process_order_data(order_id: int, coupon_code: Optional[str] = None) -> dict:
    """
    处理订单数据，修复 Optional 未定义错误
    :param order_id: 订单 ID
    :param coupon_code: 可选的优惠券代码
    :return: 处理后的订单数据字典
    """
    return {
        "order_id": order_id,
        "coupon_code": coupon_code if coupon_code else "NONE"
    }

if __name__ == "__main__":
    # 测试验证修复是否成功
    try:
        result = process_order_data(20231001)
        assert isinstance(result, dict)
        assert result["order_id"] == 20231001
        print("修复成功：Optional 已正确导入并使用")
    except NameError as e:
        print(f"修复失败：{e}")
    except Exception as e:
        print(f"发生其他错误：{e}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
