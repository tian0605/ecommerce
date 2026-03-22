# remote_weight_caller.py
# 远程服务器调用本地服务的模块
# 通过 SSH 隧道访问本地 HTTP 服务

import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# 本地服务地址（通过隧道映射）
LOCAL_SERVICE_URL = "http://127.0.0.1:9090"

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
            logger.info(f"成功获取重量: weight={data.get('weight_g')}g, "
                       f"size={data.get('length_cm')}x{data.get('width_cm')}x{data.get('height_cm')}cm")
            return {
                'success': True,
                'weight_g': data.get('weight_g'),
                'length_cm': data.get('length_cm'),
                'width_cm': data.get('width_cm'),
                'height_cm': data.get('height_cm'),
                'error': None
            }
        else:
            logger.warning(f"本地服务未能提取数据: {data.get('error')}")
            return {
                'success': False,
                'weight_g': None,
                'length_cm': None,
                'width_cm': None,
                'height_cm': None,
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
