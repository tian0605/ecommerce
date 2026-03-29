import logging
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def optimize(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    修复后的优化函数，增加数据验证和异常处理
    用于电商运营自动化流程中的策略优化步骤
    """
    result = {
        "success": False,
        "message": "",
        "optimized_data": None
    }

    try:
        # 1. 检查输入数据是否为空
        if not data:
            logger.warning("输入数据为空，跳过优化计算")
            result["success"] = True  # 视为成功但无操作，避免阻断后续流程
            result["message"] = "输入数据为空，跳过优化"
            return result

        # 2. 检查必需字段并设置默认值 (防止 KeyError)
        # 假设优化逻辑依赖 'cost' (成本) 和 'revenue' (营收)
        cost = float(data.get('cost', 0) or 0)
        revenue = float(data.get('revenue', 0) or 0)

        # 3. 安全计算指标 (防止除零错误)
        if cost > 0:
            roi = revenue / cost
        else:
            roi = 0.0

        # 4. 执行优化逻辑 (示例：根据 ROI 调整建议预算)
        if roi > 1.5:
            suggested_budget = revenue * 0.6  # 高 ROI 增加预算
        elif roi > 1.0:
            suggested_budget = revenue * 0.5  # 正常 ROI 保持
        else:
            suggested_budget = revenue * 0.2  # 低 ROI 缩减预算

        result["success"] = True
        result["message"] = "优化执行成功"
        result["optimized_data"] = {
            "roi": round(roi, 4),
            "suggested_budget": round(suggested_budget, 2),
            "original_cost": cost,
            "original_revenue": revenue
        }

    except Exception as e:
        logger.error(f"优化步骤执行失败：{str(e)}")
        result["success"] = False
        result["message"] = f"优化异常：{str(e)}"
        # 确保即使失败也返回结构化数据，便于上游处理
        result["optimized_data"] = {}

    return result

def test_fix():
    """测试验证修复后的代码"""
    print("开始测试优化函数...")
    
    # 测试用例 1: 正常数据
    res1 = optimize({"cost": 100, "revenue": 200})
    assert res1["success"] is True, "正常数据测试失败"
    assert res1["optimized_data"]["roi"] == 2.0, "ROI 计算错误"
    print("测试用例 1 通过：正常数据")

    # 测试用例 2: 空数据
    res2 = optimize(None)
    assert res2["success"] is True, "空数据测试失败"
    print("测试用例 2 通过：空数据")

    # 测试用例 3: 除零风险 (cost=0)
    res3 = optimize({"cost": 0, "revenue": 100})
    assert res3["success"] is True, "除零测试失败"
    assert res3["optimized_data"]["roi"] == 0.0, "除零处理错误"
    print("测试用例 3 通过：除零风险")

    # 测试用例 4: 缺失字段
    res4 = optimize({"cost": 100}) # 缺少 revenue
    assert res4["success"] is True, "缺失字段测试失败"
    print("测试用例 4 通过：缺失字段")

    print("所有测试通过，修复有效。")
    return True

if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
