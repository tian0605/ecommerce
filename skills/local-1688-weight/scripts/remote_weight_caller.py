# remote_weight_caller.py
# 远程服务器调用本地服务的模块
# 通过 SSH 隧道访问本地 HTTP 服务

import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# 本地服务地址（通过隧道映射）
# 注意：8080端口是用户调整后的隧道端口
LOCAL_SERVICE_URL = "http://127.0.0.1:8080"

def fetch_weight_from_local(product_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
    """
    通过隧道调用本地服务获取1688商品重量和尺寸
    
    Args:
        product_id: 1688商品ID或URL
        timeout: 超时时间（秒）
    
    Returns:
        {
            'success': True/False,
            'weight_g': 1500,  # 克
            'length_cm': 30,
            'width_cm': 20,
            'height_cm': 15,
            'error': None 或错误信息
        }
        如果失败返回 None
    """
    try:
        logger.info(f"通过本地服务获取商品重量: {product_id}")
        
        response = requests.post(
            f"{LOCAL_SERVICE_URL}/fetch-weight",
            json={'product_id': product_id},
            timeout=timeout
        )
        
        if response.status_code != 200:
            logger.error(f"本地服务响应错误: HTTP {response.status_code}")
            return None
        
        data = response.json()
        
        if data.get('success'):
            # 解析新的嵌套结构
            weight_info = data.get('weight_info', {})
            spec_list = data.get('spec_list', [])
            
            # 默认值
            default_weight = weight_info.get('weight_g')
            applies_to_all = weight_info.get('applies_to_all', True)
            
            # 构建SKU列表
            sku_list = []
            for spec in spec_list:
                sku_name = spec.get('name', '')
                
                # 如果applies_to_all为true，所有SKU使用相同的重量
                if applies_to_all and default_weight:
                    weight_g = default_weight
                else:
                    weight_g = spec.get('weight_g') or default_weight
                
                # 优先使用spec中的尺寸，否则尝试从名称解析
                length_cm = spec.get('length_cm')
                width_cm = spec.get('width_cm')
                height_cm = spec.get('height_cm')
                
                # 如果spec没有尺寸但名称包含尺寸信息，尝试解析
                if not all([length_cm, width_cm, height_cm]) and 'cm' in sku_name:
                    import re
                    size_match = re.search(r'(\d+)\*(\d+)\*(\d+)', sku_name)
                    if size_match:
                        length_cm = length_cm or int(size_match.group(1))
                        width_cm = width_cm or int(size_match.group(2))
                        height_cm = height_cm or int(size_match.group(3))
                
                sku_list.append({
                    'sku_name': sku_name,
                    'weight_g': weight_g,
                    'length_cm': length_cm,
                    'width_cm': width_cm,
                    'height_cm': height_cm
                })
            
            # 如果spec_list为空但有weight_info，创建默认SKU
            if not sku_list and default_weight:
                sku_list.append({
                    'sku_name': '默认',
                    'weight_g': default_weight,
                    'length_cm': None,
                    'width_cm': None,
                    'height_cm': None
                })
            
            logger.info(f"成功获取重量: weight={default_weight}g, {len(sku_list)} 个SKU")
            for sku in sku_list[:3]:  # 只打印前3个
                logger.info(f"   - {sku.get('sku_name')}: {sku.get('weight_g')}g, "
                           f"{sku.get('length_cm') or 'N/A'}x{sku.get('width_cm') or 'N/A'}x{sku.get('height_cm') or 'N/A'}cm")
            
            return {
                'success': True,
                'sku_count': len(sku_list),
                'sku_list': sku_list,
                'error': None
            }
        else:
            logger.warning(f"本地服务未能提取数据: {data.get('error')}")
            return {
                'success': False,
                'sku_count': 0,
                'sku_list': [],
                'error': data.get('error')
            }
            
    except requests.exceptions.ConnectionError:
        logger.error("无法连接到本地服务，请检查隧道是否建立")
        return None
    except requests.exceptions.Timeout:
        logger.error(f"本地服务响应超时 ({timeout}s)")
        return None
    except Exception as e:
        logger.error(f"调用本地服务异常: {e}")
        return None

def check_local_service_health() -> bool:
    """检查本地服务是否可用"""
    try:
        response = requests.get(f"{LOCAL_SERVICE_URL}/health", timeout=5)
        if response.status_code == 200:
            logger.info("本地服务健康检查通过")
            return True
    except Exception as e:
        logger.warning(f"本地服务不可用: {e}")
    return False

if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    # 检查服务
    if check_local_service_health():
        # 测试获取
        result = fetch_weight_from_local("1027205078815")
        print(f"结果: {result}")
    else:
        print("本地服务不可用，请检查隧道")
