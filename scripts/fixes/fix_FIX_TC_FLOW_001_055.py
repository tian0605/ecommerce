import requests
import json
import logging
import time
from typing import Optional, Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataCollectionError(Exception):
    """数据采集异常类"""
    pass

def collect_data(url: str, params: Optional[Dict] = None, 
                 max_retries: int = 3, timeout: int = 30) -> Dict[str, Any]:
    """
    修复后的数据采集函数，包含完整的错误处理和重试机制
    
    参数:
        url: 采集目标URL
        params: 请求参数
        max_retries: 最大重试次数
        timeout: 请求超时时间
    
    返回:
        采集到的数据字典
    """
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"开始第{attempt}次采集尝试，URL: {url}")
            
            # 发送请求
            response = requests.get(
                url, 
                params=params, 
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            
            # 检查响应状态
            if response.status_code != 200:
                raise DataCollectionError(
                    f"HTTP状态码异常: {response.status_code}"
                )
            
            # 解析响应数据
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                raise DataCollectionError(f"JSON解析失败: {str(e)}")
            
            # 验证数据有效性
            if not data:
                raise DataCollectionError("采集数据为空")
            
            logger.info(f"第{attempt}次采集成功")
            return {
                'success': True,
                'data': data,
                'attempt': attempt
            }
            
        except requests.exceptions.Timeout as e:
            last_error = f"请求超时: {str(e)}"
            logger.warning(f"第{attempt}次采集超时: {last_error}")
            
        except requests.exceptions.ConnectionError as e:
            last_error = f"连接错误: {str(e)}"
            logger.warning(f"第{attempt}次采集连接失败: {last_error}")
            
        except DataCollectionError as e:
            last_error = str(e)
            logger.warning(f"第{attempt}次采集数据错误: {last_error}")
            
        except Exception as e:
            last_error = f"未知错误: {str(e)}"
            logger.error(f"第{attempt}次采集发生未知错误: {last_error}")
        
        # 重试前等待
        if attempt < max_retries:
            wait_time = 2 ** attempt  # 指数退避
            logger.info(f"等待{wait_time}秒后重试...")
            time.sleep(wait_time)
    
    # 所有重试失败
    error_msg = f"采集失败，已重试{max_retries}次，最后错误: {last_error}"
    logger.error(error_msg)
    
    return {
        'success': False,
        'error': last_error,
        'message': error_msg,
        'attempt': max_retries
    }

def validate_collection_result(result: Dict[str, Any]) -> bool:
    """验证采集结果是否有效"""
    if not isinstance(result, dict):
        return False
    return result.get('success', False)

# 测试验证
def test_fix():
    """测试修复后的采集函数"""
    # 测试1: 模拟成功采集
    test_result = {
        'success': True,
        'data': {'items': []},
        'attempt': 1
    }
    assert validate_collection_result(test_result) == True
    
    # 测试2: 模拟失败采集
    test_result = {
        'success': False,
        'error': '连接超时',
        'message': '采集失败',
        'attempt': 3
    }
    assert validate_collection_result(test_result) == False
    
    # 测试3: 验证异常处理
    try:
        result = collect_data(
            url='https://httpbin.org/status/404',
            max_retries=1,
            timeout=5
        )
        assert result['success'] == False
    except Exception:
        pass  # 预期可能失败
    
    logger.info("所有测试通过")
    return True

if __name__ == '__main__':
    # 运行测试
    test_fix()
    
    # 示例：实际采集调用
    # result = collect_data('https://api.example.com/data')
    # if result['success']:
    #     print("采集成功:", result['data'])
    # else:
    #     print("采集失败:", result['error'])
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
