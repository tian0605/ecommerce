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


class TCFlowAnalyzer:
    """TC-FLOW流程错误分析器"""
    
    def __init__(self, flow_id: str = "TC-FLOW-001"):
        self.flow_id = flow_id
        self.error_log = []
        
    def analyze_failure(self, log_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        分析流程失败原因
        
        Args:
            log_data: 失败日志数据，如果为None则生成模拟诊断
            
        Returns:
            诊断结果字典
        """
        result = {
            "flow_id": self.flow_id,
            "status": "analyzed",
            "timestamp": datetime.now().isoformat(),
            "issues": [],
            "fixes": []
        }
        
        if log_data is None:
            # 无日志时执行通用检查
            result["issues"].append("未提供具体错误日志，执行通用诊断")
            result["fixes"].append("请提供完整错误日志以便精准定位")
            self._run_common_checks(result)
        else:
            self._parse_error_log(log_data, result)
            
        return result
    
    def _run_common_checks(self, result: Dict) -> None:
        """执行常见问题检查"""
        common_issues = [
            ("参数格式错误", "确保输入参数为正确的JSON格式"),
            ("API连接超时", "检查网络连接和API端点可用性"),
            ("权限验证失败", "验证API密钥和访问令牌"),
            ("数据格式不匹配", "检查请求数据与接口规范是否一致"),
            ("资源不存在", "确认操作的商品/订单ID有效")
        ]
        
        for issue, fix in common_issues:
            result["issues"].append(f"可能原因：{issue}")
            result["fixes"].append(f"建议修复：{fix}")
    
    def _parse_error_log(self, log_data: Dict, result: Dict) -> None:
        """解析具体错误日志"""
        error_msg = log_data.get("error", "")
        stack_trace = log_data.get("traceback", "")
        
        if "timeout" in error_msg.lower():
            result["issues"].append("检测到超时错误")
            result["fixes"].append("增加请求超时时间或重试机制")
        elif "permission" in error_msg.lower() or "auth" in error_msg.lower():
            result["issues"].append("检测到权限验证错误")
            result["fixes"].append("更新API密钥或检查权限配置")
        elif "not found" in error_msg.lower() or "404" in error_msg:
            result["issues"].append("检测到资源不存在错误")
            result["fixes"].append("验证资源ID是否正确")
        else:
            result["issues"].append(f"未知错误：{error_msg}")
            result["fixes"].append("需要进一步分析错误堆栈")


def fix_tc_flow_001(log_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    TC-FLOW-001流程修复主函数
    
    Args:
        log_data: 可选的错误日志数据
        
    Returns:
        修复建议字典
    """
    analyzer = TCFlowAnalyzer(flow_id="TC-FLOW-001")
    diagnosis = analyzer.analyze_failure(log_data)
    
    logger.info(f"流程诊断完成：{diagnosis['flow_id']}")
    logger.info(f"发现问题数：{len(diagnosis['issues'])}")
    
    return diagnosis


def test_fix():
    """测试验证函数"""
    # 测试1：无日志情况
    result1 = fix_tc_flow_001()
    assert result1["flow_id"] == "TC-FLOW-001"
    assert result1["status"] == "analyzed"
    assert len(result1["issues"]) > 0
    
    # 测试2：有日志情况
    mock_log = {
        "error": "Connection timeout after 30s",
        "traceback": "line 45 in api_call"
    }
    result2 = fix_tc_flow_001(mock_log)
    assert "超时" in str(result2["issues"]) or "timeout" in str(result2["issues"]).lower()
    
    # 测试3：权限错误
    mock_log_auth = {
        "error": "Authentication failed: invalid token",
        "traceback": "line 22 in auth_check"
    }
    result3 = fix_tc_flow_001(mock_log_auth)
    assert "权限" in str(result3["issues"]) or "auth" in str(result3["issues"]).lower()
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    # 执行测试
    test_fix()
    
    # 输出诊断结果示例
    print("\n=== TC-FLOW-001 诊断报告 ===")
    report = fix_tc_flow_001()
    print(json.dumps(report, ensure_ascii=False, indent=2))
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
