import json
import logging
import time
from typing import Dict, List, Any, Optional
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """重试装饰器，用于处理临时性失败"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"函数 {func.__name__} 执行失败，已重试 {max_retries} 次: {str(e)}")
                        raise
                    logger.warning(f"函数 {func.__name__} 执行失败，第 {attempt + 1} 次重试: {str(e)}")
                    time.sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator


class CollectError(Exception):
    """收集数据时的自定义异常"""
    pass


def validate_data(data: Any, required_fields: List[str] = None) -> bool:
    """验证收集的数据是否有效"""
    if data is None:
        return False
    if isinstance(data, dict):
        if required_fields:
            return all(field in data for field in required_fields)
        return len(data) > 0
    if isinstance(data, list):
        return len(data) > 0
    return True


@retry_on_failure(max_retries=3, delay=1.0)
def collect_data(
    source: str,
    params: Optional[Dict[str, Any]] = None,
    required_fields: Optional[List[str]] = None,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    收集数据的核心函数，包含完善的错误处理
    
    参数:
        source: 数据源标识
        params: 收集参数
        required_fields: 必需字段列表
        timeout: 超时时间（秒）
    
    返回:
        收集到的数据字典
    """
    logger.info(f"开始执行 collect 步骤，数据源: {source}")
    
    # 参数验证
    if params is None:
        params = {}
    
    if not isinstance(params, dict):
        try:
            if isinstance(params, str):
                params = json.loads(params)
            else:
                params = dict(params)
        except (json.JSONDecodeError, TypeError) as e:
            raise CollectError(f"参数解析失败: {str(e)}")
    
    # 模拟数据收集过程（实际使用时替换为真实的数据收集逻辑）
    try:
        # 这里应该替换为实际的数据收集逻辑
        # 例如：API 调用、数据库查询、文件读取等
        collected_data = _execute_collect(source, params, timeout)
        
        # 数据验证
        if not validate_data(collected_data, required_fields):
            raise CollectError(
                f"收集的数据无效或为空，数据源: {source}, "
                f"必需字段: {required_fields}"
            )
        
        logger.info(f"collect 步骤执行成功，收集到 {len(collected_data) if isinstance(collected_data, (dict, list)) else 1} 条数据")
        
        return {
            "status": "success",
            "source": source,
            "data": collected_data,
            "timestamp": time.time()
        }
        
    except CollectError:
        raise
    except Exception as e:
        logger.error(f"collect 步骤执行异常: {str(e)}")
        raise CollectError(f"collect 失败: {str(e)}")


def _execute_collect(source: str, params: Dict[str, Any], timeout: int) -> Any:
    """
    执行实际的数据收集逻辑
    根据实际业务场景实现不同的收集策略
    """
    # 示例实现，实际使用时需要根据业务需求修改
    collect_strategies = {
        "api": _collect_from_api,
        "database": _collect_from_database,
        "file": _collect_from_file,
        "default": _collect_default
    }
    
    strategy = params.get("strategy", "default")
    collector = collect_strategies.get(strategy, collect_strategies["default"])
    
    return collector(source, params, timeout)


def _collect_from_api(source: str, params: Dict[str, Any], timeout: int) -> Any:
    """从 API 收集数据"""
    import requests
    
    url = params.get("url", source)
    headers = params.get("headers", {})
    method = params.get("method", "GET")
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            timeout=timeout,
            params=params.get("query_params")
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise CollectError(f"API 请求失败: {str(e)}")


def _collect_from_database(source: str, params: Dict[str, Any], timeout: int) -> Any:
    """从数据库收集数据"""
    # 这里需要根据实际数据库类型实现
    # 示例返回空列表表示需要配置数据库连接
    logger.warning("数据库收集未配置，返回空数据")
    return []


def _collect_from_file(source: str, params: Dict[str, Any], timeout: int) -> Any:
    """从文件收集数据"""
    import os
    
    file_path = params.get("file_path", source)
    
    if not os.path.exists(file_path):
        raise CollectError(f"文件不存在: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.endswith('.json'):
                return json.load(f)
            else:
                return f.read()
    except Exception as e:
        raise CollectError(f"文件读取失败: {str(e)}")


def _collect_default(source: str, params: Dict[str, Any], timeout: int) -> Any:
    """默认收集策略"""
    logger.info(f"使用默认收集策略，数据源: {source}")
    # 返回示例数据，实际使用时需要替换
    return {
        "source": source,
        "items": []
    }


def fix_collect_flow(
    source: str,
    params: Optional[Dict[str, Any]] = None,
    required_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    修复 collect 步骤的主函数
    封装了完整的错误处理和重试逻辑
    """
    try:
        result = collect_data(
            source=source,
            params=params,
            required_fields=required_fields,
            timeout=30
        )
        return result
    except CollectError as e:
        logger.error(f"collect 步骤修复失败: {str(e)}")
        return {
            "status": "failed",
            "source": source,
            "error": str(e),
            "timestamp": time.time()
        }


# 测试验证
def test_fix():
    """测试修复后的 collect 函数"""
    # 测试 1: 正常收集
    result1 = fix_collect_flow(
        source="test_source",
        params={"strategy": "default"}
    )
    assert result1["status"] == "success", "测试 1 失败"
    
    # 测试 2: 带必需字段验证
    result2 = fix_collect_flow(
        source="test_source",
        params={"strategy": "default"},
        required_fields=["source"]
    )
    assert result2["status"] == "success", "测试 2 失败"
    
    # 测试 3: 字符串参数自动解析
    result3 = fix_collect_flow(
        source="test_source",
        params='{"strategy": "default"}'
    )
    assert result3["status"] == "success", "测试 3 失败"
    
    logger.info("所有测试通过")
    return True


if __name__ == "__main__":
    # 运行测试
    test_fix()
    
    # 示例使用
    print("\n=== Collect 修复示例 ===")
    result = fix_collect_flow(
        source="product_list",
        params={"strategy": "default"},
        required_fields=["source"]
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
