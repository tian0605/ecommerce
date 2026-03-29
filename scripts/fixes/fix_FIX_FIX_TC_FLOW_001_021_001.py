import logging
import time
from typing import Any, Dict, Optional
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FlowExecutionError(Exception):
    """流程执行异常"""
    pass


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"执行失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
            raise FlowExecutionError(f"流程执行失败，已重试{max_retries}次") from last_exception
        return wrapper
    return decorator


def validate_flow_params(params: Optional[Dict]) -> Dict:
    """验证流程参数"""
    if params is None:
        raise FlowExecutionError("流程参数不能为空")
    if not isinstance(params, dict):
        raise FlowExecutionError(f"流程参数类型错误，期望 dict，实际 {type(params)}")
    return params


@retry_on_failure(max_retries=3, delay=1.0)
def execute_tc_flow(flow_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行 TC 流程的核心函数
    
    Args:
        flow_id: 流程标识
        params: 流程参数
    
    Returns:
        执行结果
    """
    # 参数验证
    params = validate_flow_params(params)
    
    logger.info(f"开始执行流程 {flow_id}")
    
    try:
        # 模拟流程执行步骤
        result = {
            "flow_id": flow_id,
            "status": "success",
            "executed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "params_received": params
        }
        
        # 关键业务逻辑占位 - 实际使用时替换为真实逻辑
        if "critical_step" in params:
            if not params["critical_step"]:
                raise FlowExecutionError("关键步骤配置缺失")
        
        logger.info(f"流程 {flow_id} 执行成功")
        return result
        
    except FlowExecutionError:
        raise
    except Exception as e:
        logger.error(f"流程 {flow_id} 执行异常：{str(e)}")
        raise FlowExecutionError(f"流程执行失败：{str(e)}") from e


def fix_tc_flow_execution(flow_id: str = "TC-FLOW-001", 
                          params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    修复后的流程执行入口函数
    
    Args:
        flow_id: 流程标识，默认 TC-FLOW-001
        params: 流程参数
    
    Returns:
        执行结果字典
    """
    # 默认参数处理
    if params is None:
        params = {"critical_step": True}
    
    try:
        result = execute_tc_flow(flow_id, params)
        return {
            "success": True,
            "data": result,
            "error": None
        }
    except FlowExecutionError as e:
        logger.error(f"流程修复失败：{str(e)}")
        return {
            "success": False,
            "data": None,
            "error": str(e)
        }


# 测试验证
def test_fix():
    """测试修复代码"""
    # 测试 1: 正常执行
    result1 = fix_tc_flow_execution("TC-FLOW-001", {"critical_step": True})
    assert result1["success"] == True, "测试 1 失败：正常执行应成功"
    
    # 测试 2: 参数为空时的默认处理
    result2 = fix_tc_flow_execution("TC-FLOW-001", None)
    assert result2["success"] == True, "测试 2 失败：空参数应使用默认值"
    
    # 测试 3: 关键步骤缺失应失败
    result3 = fix_tc_flow_execution("TC-FLOW-001", {"critical_step": False})
    assert result3["success"] == False, "测试 3 失败：关键步骤缺失应失败"
    
    # 测试 4: 参数类型错误应失败
    result4 = fix_tc_flow_execution("TC-FLOW-001", "invalid")  # type: ignore
    assert result4["success"] == False, "测试 4 失败：参数类型错误应失败"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
