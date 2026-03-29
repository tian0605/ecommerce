import logging
from datetime import datetime
from typing import Callable, Any

# 配置日志以便捕获详细错误信息
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def validate_step_id(step_id: str) -> bool:
    """
    验证步骤 ID 格式是否符合 YYYY-MM-DD HH 规范
    """
    try:
        datetime.strptime(step_id, "%Y-%m-%d %H")
        return True
    except ValueError:
        return False

def execute_step_safely(step_id: str, task_func: Callable, *args, **kwargs) -> Any:
    """
    健壮的步骤执行包装器，防止静默失败并确保错误可追溯
    """
    # 1. 校验步骤 ID 格式
    if not validate_step_id(step_id):
        error_msg = f"Invalid step ID format: {step_id}, expected YYYY-MM-DD HH"
        logging.error(error_msg)
        raise ValueError(error_msg)

    try:
        logging.info(f"Starting execution for step: {step_id}")
        # 2. 执行任务逻辑
        result = task_func(*args, **kwargs)
        logging.info(f"Step {step_id} completed successfully")
        return result
    except Exception as e:
        # 3. 捕获异常并记录详细堆栈，避免静默失败
        logging.error(f"Step {step_id} failed with error: {str(e)}", exc_info=True)
        # 4. 重新抛出异常以便上层流程感知失败
        raise

# 模拟任务函数
def mock_business_task():
    """模拟具体的电商业务逻辑"""
    # 此处模拟正常逻辑，若需测试错误可手动抛出异常
    return {"status": "success", "data": "order_processed"}

# 测试验证入口
if __name__ == "__main__":
    try:
        # 使用修复后的函数执行失败步骤
        step_id = "2026-03-27 07"
        result = execute_step_safely(step_id, mock_business_task)
        print(f"验证通过：{result}")
    except Exception as e:
        print(f"验证捕获到异常：{e}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
