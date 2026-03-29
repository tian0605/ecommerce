import requests
from typing import Dict, Union

def call_miaoshou_collector(product_id: Union[str, int], target_platform: str = "Shopee") -> Dict:
    """
    调用miaoshou-collector采集指定商品并认领到对应平台采集箱
    :param product_id: 待采集的商品ID
    :param target_platform: 认领目标平台，默认Shopee
    :return: 采集+认领结果
    """
    # 1. 调用miaoshou-collector采集接口
    collect_url = "http://miaoshou-collector/api/v1/collect"
    collect_params = {
        "product_id": str(product_id),
        "source": "official"
    }
    try:
        collect_resp = requests.post(collect_url, json=collect_params, timeout=30)
        collect_resp.raise_for_status()
        collect_result = collect_resp.json()
    except Exception as e:
        raise RuntimeError(f"调用采集接口失败：{str(e)}")
    
    if not collect_result.get("success"):
        raise RuntimeError(f"商品采集失败：{collect_result.get('msg', '未知错误')}")
    
    # 2. 认领到Shopee采集箱
    claim_url = "http://miaoshou-collector/api/v1/claim_to_platform_box"
    claim_params = {
        "collect_record_id": collect_result["data"]["collect_record_id"],
        "platform": target_platform
    }
    try:
        claim_resp = requests.post(claim_url, json=claim_params, timeout=30)
        claim_resp.raise_for_status()
        claim_result = claim_resp.json()
    except Exception as e:
        raise RuntimeError(f"调用认领接口失败：{str(e)}")
    
    if not claim_result.get("success"):
        raise RuntimeError(f"认领Shopee采集箱失败：{claim_result.get('msg', '未知错误')}")
    
    return {
        "code": 0,
        "msg": "采集并认领成功",
        "data": {
            "product_id": str(product_id),
            "platform": target_platform,
            "collect_record_id": collect_result["data"]["collect_record_id"]
        }
    }

# 测试验证
def test_collect_task():
    try:
        # 执行目标任务：采集1031400982378并认领到Shopee采集箱
        result = call_miaoshou_collector(1031400982378, "Shopee")
        print(f"任务执行成功：{result}")
        return True
    except Exception as e:
        print(f"任务执行失败：{str(e)}")
        return False

if __name__ == "__main__":
    test_collect_task()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
