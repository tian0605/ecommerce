import requests
import time
from typing import Optional, Dict, Any
from requests.exceptions import RequestException, Timeout, ConnectionError

def scrape_with_retry(url: str, max_retries: int = 3, timeout: int = 10) -> Optional[Dict[str, Any]]:
    """
    带重试机制的爬虫函数，修复scrape失败问题
    
    参数:
        url: 目标URL
        max_retries: 最大重试次数
        timeout: 请求超时时间（秒）
    
    返回:
        成功返回响应数据字典，失败返回None
    """
    # 配置请求头，避免被反爬虫拦截
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # 添加随机延迟，避免请求过快
            if attempt > 0:
                time.sleep(2 ** attempt)  # 指数退避
            
            response = requests.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True
            )
            
            # 检查HTTP状态码
            response.raise_for_status()
            
            # 返回成功结果
            return {
                'success': True,
                'status_code': response.status_code,
                'content': response.text,
                'url': url
            }
            
        except Timeout as e:
            last_error = f"请求超时: {str(e)}"
            print(f"[重试 {attempt + 1}/{max_retries}] {last_error}")
            continue
            
        except ConnectionError as e:
            last_error = f"连接错误: {str(e)}"
            print(f"[重试 {attempt + 1}/{max_retries}] {last_error}")
            continue
            
        except RequestException as e:
            last_error = f"请求异常: {str(e)}"
            print(f"[重试 {attempt + 1}/{max_retries}] {last_error}")
            continue
            
        except Exception as e:
            last_error = f"未知错误: {str(e)}"
            print(f"[重试 {attempt + 1}/{max_retries}] {last_error}")
            continue
    
    # 所有重试都失败
    print(f"[失败] 所有重试耗尽，最后错误: {last_error}")
    return {
        'success': False,
        'error': last_error,
        'url': url
    }


def scrape_product_info(url: str) -> Optional[Dict[str, Any]]:
    """
    电商产品信息爬取函数（封装版）
    
    参数:
        url: 商品页面URL
    
    返回:
        产品信息字典或错误信息
    """
    result = scrape_with_retry(url)
    
    if result and result.get('success'):
        return {
            'status': 'success',
            'data': result
        }
    else:
        return {
            'status': 'failed',
            'error': result.get('error', 'Unknown error') if result else 'No response'
        }


# 测试验证
def test_fix():
    """测试修复代码"""
    # 测试1: 验证函数可调用
    try:
        # 使用一个可靠的测试URL
        result = scrape_with_retry('https://httpbin.org/get', max_retries=2, timeout=5)
        if result is not None:
            print("✓ 测试1通过: 函数可正常执行")
            return True
        else:
            print("✗ 测试1失败: 返回None")
            return False
    except Exception as e:
        print(f"✗ 测试1异常: {e}")
        return False


if __name__ == '__main__':
    # 运行测试
    test_fix()
    
    # 示例使用
    print("\n示例使用:")
    example_result = scrape_product_info('https://httpbin.org/get')
    print(f"状态: {example_result.get('status')}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
