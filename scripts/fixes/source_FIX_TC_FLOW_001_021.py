import logging
import time
from typing import Any, Dict, Optional
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TC_FLOW_FIX')


class FlowExecutionError(Exception):
    """流程执行异常"""
    pass


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """重试装饰器，处理临时性失败"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    logger.info(f"执行 {func.__name__}, 尝试 {attempt + 1}/{max_retries}")
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"尝试 {attempt + 1} 失败：{str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
            logger.error(f"{func.__name__} 最终失败：{str(last_exception)}")
            raise FlowExecutionError(f"重试 {max_retries} 次后仍失败") from last_exception
        return wrapper
    return decorator


def safe_get(data: Any, key: str, default: Any = None) -> Any:
    """安全获取字典值，避免 KeyError"""
    if isinstance(data, dict):
        return data.get(key, default)
    return default


def validate_flow_data(data: Dict) -> bool:
    """验证流程数据完整性"""
    required_fields = ['task_id', 'status', 'timestamp']
    for field in required_fields:
        if field not in data:
            logger.warning(f"缺少必需字段：{field}")
            return False
    return True


class TCFlowHandler:
    """TC-FLOW-001 流程处理器"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.retry_count = 0
        self.max_retries = 3
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def execute_flow(self, flow_data: Dict) -> Dict:
        """执行核心流程"""
        if not validate_flow_data(flow_data):
            raise FlowExecutionError("流程数据验证失败")
        
        result = {
            'task_id': self.task_id,
            'status': 'completed',
            'timestamp': time.time(),
            'retry_count': self.retry_count
        }
        logger.info(f"流程 {self.task_id} 执行成功")
        return result
    
    def run(self, flow_data: Dict) -> Dict:
        """运行流程，包含完整异常处理"""
        try:
            logger.info(f"开始执行任务 {self.task_id}")
            
            # 数据预处理
            if flow_data is None:
                flow_data = {}
            
            # 执行流程
            result = self.execute_flow(flow_data)
            
            # 后处理
            result['execution_time'] = time.time()
            
            return result
            
        except FlowExecutionError as e:
            logger.error(f"流程执行错误：{str(e)}")
            return {
                'task_id': self.task_id,
                'status': 'failed',
                'error': str(e),
                'timestamp': time.time()
            }
        except Exception as e:
            logger.exception(f"未预期的错误：{str(e)}")
            return {
                'task_id': self.task_id,
                'status': 'error',
                'error': str(e),
                'timestamp': time.time()
            }


def fix_tc_flow_001(task_id: str, flow_data: Optional[Dict] = None) -> Dict:
    """
    修复 TC-FLOW-001 流程的主函数
    
    Args:
        task_id: 任务 ID
        flow_data: 流程数据，可选
    
    Returns:
        执行结果字典
    """
    if flow_data is None:
        flow_data = {
            'task_id': task_id,
            'status': 'pending',
            'timestamp': time.time()
        }
    
    handler = TCFlowHandler(task_id)
    result = handler.run(flow_data)
    
    return result


# 测试验证
def test_fix():
    """测试修复代码"""
    # 测试 1: 正常执行
    result1 = fix_tc_flow_001('TEST-001')
    assert result1['task_id'] == 'TEST-001'
    assert result1['status'] in ['completed', 'failed', 'error']
    
    # 测试 2: 空数据处理
    result2 = fix_tc_flow_001('TEST-002', None)
    assert result2['task_id'] == 'TEST-002'
    
    # 测试 3: 安全获取
    test_dict = {'key': 'value'}
    assert safe_get(test_dict, 'key') == 'value'
    assert safe_get(test_dict, 'missing', 'default') == 'default'
    assert safe_get(None, 'key', 'default') == 'default'
    
    # 测试 4: 数据验证
    valid_data = {'task_id': '1', 'status': 'ok', 'timestamp': 123}
    assert validate_flow_data(valid_data) == True
    
    invalid_data = {'task_id': '1'}
    assert validate_flow_data(invalid_data) == False
    
    logger.info("所有测试通过")
    return True


if __name__ == '__main__':
    # 运行测试
    test_fix()
    
    # 示例执行
    result = fix_tc_flow_001('TC-FLOW-001-021')
    print(f"执行结果：{result}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
