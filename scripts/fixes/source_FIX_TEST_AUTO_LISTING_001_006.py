import requests
from typing import List, Dict


def write_optimized_content_to_miaoshou_shopee(
    optimized_list: List[Dict],
    collect_box_ids: List[str],
    miaoshou_auth: str,
    updater_endpoint: str = "https://api.miaoshouerp.com/skill/miaoshou-updater/shopee/collect-box/write"
) -> Dict:
    """
    将优化后的商品内容回写到妙手ERP的Shopee采集箱
    Args:
        optimized_list: 优化后的商品内容列表，每个元素为包含sku、标题、描述等字段的字典
        collect_box_ids: 待更新的Shopee采集箱ID列表，和优化内容一一对应
        miaoshou_auth: 妙手ERP接口授权token
        updater_endpoint: miaoshou-updater技能的接口地址，可根据实际部署情况修改
    Returns:
        回写结果，包含成功/失败状态和详情
    """
    # 基础参数校验
    if not optimized_list or not collect_box_ids or not miaoshou_auth:
        return {"code": 400, "msg": "优化内容、采集箱ID、授权token为必填参数，不能为空", "data": None}
    if len(optimized_list) != len(collect_box_ids):
        return {"code": 400, "msg": "优化内容数量与待更新的采集箱ID数量不匹配", "data": None}

    # 构造请求参数
    request_data = {
        "collect_box_ids": collect_box_ids,
        "optimized_contents": optimized_list
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {miaoshou_auth}"
    }

    try:
        # 调用miaoshou-updater技能执行回写
        resp = requests.post(updater_endpoint, json=request_data, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"code": 500, "msg": f"调用miaoshou-updater技能失败: {str(e)}", "data": None}


# 测试验证
def test_write_back():
    # 测试参数校验逻辑
    test_optimized = [{"sku": "SP001", "title": "优化后的商品标题", "desc": "优化后的商品描述"}]
    test_ids = ["COLLECT123456"]
    test_auth = "test_auth_token_123"

    # 空参数测试
    res1 = write_optimized_content_to_miaoshou_shopee([], test_ids, test_auth)
    assert res1["code"] == 400

    # 数量不匹配测试
    res2 = write_optimized_content_to_miaoshou_shopee(test_optimized, ["COLLECT123", "COLLECT456"], test_auth)
    assert res2["code"] == 400
    return True


if __name__ == "__main__":
    test_pass = test_write
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
