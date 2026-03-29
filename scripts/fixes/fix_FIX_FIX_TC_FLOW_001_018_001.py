import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FlowExecutionError(Exception):
    """流程执行异常"""
    def __init__(self, flow_id: str, message: str, error_code: str = "UNKNOWN"):
        self.flow_id = flow_id
        self.message = message
        self.error_code = error_code
        super().__init__(f"[{flow_id}] {message} (Code: {error_code})")


class FlowStatus:
    """流程状态管理"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    
    def __init__(self, flow_id: str):
        self.flow_id = flow_id
        self.status = self.PENDING
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self.retry_count: int = 0
        self.max_retries: int = 3
    
    def start(self):
        self.status = self.RUNNING
        self.start_time = datetime.now()
        logger.info(f"[{self.flow_id}] 流程开始执行")
    
    def success(self):
        self.status = self.SUCCESS
        self.end_time = datetime.now()
        logger.info(f"[{self.flow_id}] 流程执行成功")
    
    def fail(self, error_message: str):
        self.status = self.FAILED
        self.end_time = datetime.now()
        self.error_message = error_message
        logger.error(f"[{self.flow_id}] 流程执行失败：{error_message}")
    
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries
    
    def retry(self):
        self.retry_count += 1
        self.status = self.RETRYING
        logger.warning(f"[{self.flow_id}] 第{self.retry_count}次重试")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count
        }


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(f"执行失败，{delay}秒后重试 ({attempt + 1}/{max_retries}): {str(e)}")
                        time.sleep(delay)
                    else:
                        logger.error(f"执行失败，已达最大重试次数：{str(e)}")
            raise last_error
        return wrapper
    return decorator


class TcFlowExecutor:
    """TC 流程执行器"""
    
    def __init__(self, flow_id: str = "TC-FLOW-001"):
        self.flow_id = flow_id
        self.status = FlowStatus(flow_id)
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def execute_step(self, step_name: str, step_func, *args, **kwargs) -> Any:
        """执行单个步骤，带重试机制"""
        logger.info(f"[{self.flow_id}] 执行步骤：{step_name}")
        try:
            result = step_func(*args, **kwargs)
            logger.info(f"[{self.flow_id}] 步骤 {step_name} 执行成功")
            return result
        except Exception as e:
            logger.error(f"[{self.flow_id}] 步骤 {step_name} 执行失败：{str(e)}")
            raise
    
    def execute(self, task_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行完整流程"""
        self.status.start()
        
        try:
            # 步骤 1: 参数验证
            validated_params = self.execute_step(
                "参数验证",
                self._validate_params,
                task_params
            )
            
            # 步骤 2: 数据准备
            prepared_data = self.execute_step(
                "数据准备",
                self._prepare_data,
                validated_params
            )
            
            # 步骤 3: 核心业务逻辑
            business_result = self.execute_step(
                "核心业务",
                self._execute_business_logic,
                prepared_data
            )
            
            # 步骤 4: 结果处理
            final_result = self.execute_step(
                "结果处理",
                self._process_result,
                business_result
            )
            
            self.status.success()
            return {
                "success": True,
                "flow_id": self.flow_id,
                "result": final_result,
                "status": self.status.to_dict()
            }
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self.status.fail(error_msg)
            return {
                "success": False,
                "flow_id": self.flow_id,
                "error": error_msg,
                "status": self.status.to_dict()
            }
    
    def _validate_params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """验证输入参数"""
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise FlowExecutionError(
                self.flow_id,
                "参数格式错误，应为字典类型",
                "INVALID_PARAMS"
            )
        return params
    
    def _prepare_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """准备业务数据"""
        # 模拟数据准备逻辑
        prepared = {
            "timestamp": datetime.now().isoformat(),
            "params": params,
            "context": {}
        }
        return prepared
    
    def _execute_business_logic(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """执行核心业务逻辑"""
        # 模拟业务逻辑
        result = {
            "processed": True,
            "data": data
        }
        return result
    
    def _process_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """处理最终结果"""
        result["completed_at"] = datetime.now().isoformat()
        return result


def fix_tc_flow_001(task_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    修复 TC-FLOW-001 流程执行问题
    
    主要修复点：
    1. 完善异常捕获和错误信息记录
    2. 添加流程状态管理
    3. 实现重试机制
    4. 增强日志记录
    """
    executor = TcFlowExecutor(flow_id="TC-FLOW-001")
    result = executor.execute(task_params)
    return result


# 测试验证
def test_fix():
    """测试修复后的流程"""
    print("=" * 50)
    print("测试 1: 正常执行流程")
    result1 = fix_tc_flow_001({"test_key": "test_value"})
    assert result1["success"] == True
    assert result1["flow_id"] == "TC-FLOW-001"
    print(f"✓ 测试 1 通过：{result1['status']['status']}")
    
    print("\n" + "=" * 50)
    print("测试 2: 空参数执行")
    result2 = fix_tc_flow_001(None)
    assert result2["success"] == True
    print(f"✓ 测试 2 通过：{result2['status']['status']}")
    
    print("\n" + "=" * 50)
    print("测试 3: 状态信息完整性")
    status = result1["status"]
    assert "flow_id" in status
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
