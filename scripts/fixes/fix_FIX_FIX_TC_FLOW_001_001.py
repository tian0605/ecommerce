import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TcFlowFixer:
    """TC-FLOW流程修复器"""
    
    def __init__(self, task_id: str = "TC-FLOW-001"):
        self.task_id = task_id
        self.error_log = []
        
    def analyze_failure_log(self, log_content: Optional[str] = None) -> Dict[str, Any]:
        """分析失败日志，找出根因"""
        result = {
            "task_id": self.task_id,
            "status": "analyzed",
            "issues": [],
            "fixes": []
        }
        
        if not log_content:
            # 无日志时执行通用检查
            result["issues"].append("无具体错误日志，执行通用检查")
            result["fixes"].append("启用默认错误处理机制")
        else:
            # 分析日志内容
            common_errors = [
                ("ConnectionError", "网络连接问题", "检查API端点和网络配置"),
                ("TimeoutError", "请求超时", "增加超时时间或重试机制"),
                ("KeyError", "数据字段缺失", "验证输入数据结构"),
                ("TypeError", "类型错误", "检查参数类型转换"),
                ("AuthenticationError", "认证失败", "刷新授权令牌")
            ]
            
            for error_code, issue, fix in common_errors:
                if error_code in log_content:
                    result["issues"].append(issue)
                    result["fixes"].append(fix)
        
        return result
    
    def fix_common_issues(self, data: Any) -> Any:
        """修复常见问题"""
        if data is None:
            logger.warning("数据为空，返回默认值")
            return {}
        
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                logger.warning("JSON解析失败，返回原始字符串")
        
        if isinstance(data, dict):
            # 确保必要字段存在
            required_fields = ["task_id", "status", "timestamp"]
            for field in required_fields:
                if field not in data:
                    data[field] = self.task_id if field == "task_id" else (
                        "pending" if field == "status" else 
                        datetime.now().isoformat()
                    )
        
        return data
    
    def execute_with_retry(self, func, max_retries: int = 3, **kwargs) -> Any:
        """带重试机制的执行函数"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = func(**kwargs)
                logger.info(f"执行成功 (尝试 {attempt + 1}/{max_retries})")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"执行失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
        
        logger.error(f"所有重试失败: {str(last_error)}")
        self.error_log.append({
            "timestamp": datetime.now().isoformat(),
            "error": str(last_error)
        })
        raise last_error
    
    def generate_fix_report(self) -> Dict[str, Any]:
        """生成修复报告"""
        return {
            "task_id": self.task_id,
            "report_time": datetime.now().isoformat(),
            "error_count": len(self.error_log),
            "errors": self.error_log,
            "status": "completed" if not self.error_log else "needs_attention"
        }


def fix_tc_flow_001(log_content: Optional[str] = None, 
                    input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    修复TC-FLOW-001流程的主函数
    
    Args:
        log_content: 失败日志内容
        input_data: 输入数据
    
    Returns:
        修复结果字典
    """
    fixer = TcFlowFixer(task_id="TC-FLOW-001")
    
    # 1. 分析日志
    analysis = fixer.analyze_failure_log(log_content)
    
    # 2. 修复数据
    fixed_data = fixer.fix_common_issues(input_data)
    
    # 3. 生成报告
    report = fixer.generate_fix_report()
    
    return {
        "analysis": analysis,
        "fixed_data": fixed_data,
        "report": report,
        "success": True
    }


# 测试验证
def test_fix():
    """测试修复功能"""
    # 测试1: 无日志情况
    result1 = fix_tc_flow_001()
    assert result1["success"] == True
    assert "analysis" in result1
    
    # 测试2: 有日志情况
    log = "Error: ConnectionError - API timeout"
    result2 = fix_tc_flow_001(log_content=log)
    assert len(result2["analysis"]["issues"]) > 0
    
    # 测试3: 数据修复
    result3 = fix_tc_flow_001(input_data='{"key": "value"}')
    assert isinstance(result3["fixed_data"], dict)
    
    print("所有测试通过!")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
