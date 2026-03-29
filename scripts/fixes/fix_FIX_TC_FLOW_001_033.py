import re
from datetime import datetime
from typing import Optional, Union

def fix_datetime_format(date_str: Union[str, datetime], default_format: str = "%Y-%m-%d %H") -> Optional[datetime]:
    """
    修复日期时间格式解析错误
    支持多种常见日期格式的自动识别和标准化
    """
    if isinstance(date_str, datetime):
        return date_str
    
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    
    # 定义多种可能的日期格式
    date_formats = [
        "%Y-%m-%d %H",           # 2026-03-27 05
        "%Y-%m-%d %H:%M",        # 2026-03-27 05:30
        "%Y-%m-%d %H:%M:%S",     # 2026-03-27 05:30:00
        "%Y-%m-%d",              # 2026-03-27
        "%Y/%m/%d %H",           # 2026/03/27 05
        "%Y/%m/%d %H:%M",        # 2026/03/27 05:30
        "%Y%m%d%H",              # 2026032705
        "%Y-%m-%dT%H",           # 2026-03-27T05
        "%Y-%m-%dT%H:%M:%S",     # 2026-03-27T05:30:00
    ]
    
    # 尝试多种格式解析
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # 尝试智能解析：处理不完整的小时字段
    match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(\d{1,2})', date_str)
    if match:
        date_part, hour_part = match.groups()
        try:
            # 补全分钟和秒
            complete_str = f"{date_part} {int(hour_part):02d}:00:00"
            return datetime.strptime(complete_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    
    # 如果所有解析都失败，记录警告并返回None
    print(f"警告：无法解析日期格式 '{date_str}'")
    return None


def validate_and_fix_flow_step(step_date: str, step_name: str = "FLOW_STEP") -> dict:
    """
    验证并修复流程步骤的日期时间
    返回包含修复结果的状态字典
    """
    result = {
        "step_name": step_name,
        "original_date": step_date,
        "fixed_date": None,
        "status": "pending",
        "error_message": None
    }
    
    try:
        fixed_datetime = fix_datetime_format(step_date)
        
        if fixed_datetime is None:
            result["status"] = "failed"
            result["error_message"] = "日期格式无法解析"
        else:
            result["fixed_date"] = fixed_datetime.strftime("%Y-%m-%d %H:%M:%S")
            result["status"] = "success"
            
    except Exception as e:
        result["status"] = "failed"
        result["error_message"] = str(e)
    
    return result


def test_fix():
    """测试验证修复函数"""
    test_cases = [
        ("2026-03-27 05", True),
        ("2026-03-27 05:30", True),
        ("2026-03-27", True),
        ("2026/03/27 05", True),
        ("", False),
        (None, False),
    ]
    
    all_passed = True
    for date_str, should_succeed in test_cases:
        result = validate_and_fix_flow_step(date_str if date_str else "", "TEST_STEP")
        if should_succeed:
            if result["status"] != "success":
                print(f"测试失败：{date_str} 应该成功但得到 {result['status']}")
                all_passed = False
        else:
            if result["status"] == "success":
                print(f"测试失败：{date_str} 应该失败但得到 {result['status']}")
                all_passed = False
    
    # 特别测试问题案例
    problem_case = validate_and_fix_flow_step("2026-03-27 05", "FIX-TC-FLOW-001-033")
    assert problem_case["status"] == "success", "问题案例修复失败"
    assert problem_case["fixed_date"] is not None, "修复后的日期为空"
    
    return all_passed


if __name__ == "__main__":
    # 执行测试
    print("开始执行日期格式修复测试...")
    test_result = test_fix()
    print(f"测试结果：{'通过' if test_result else '失败'}")
    
    # 演示修复问题案例
    print("\n修复问题案例 FIX-TC-FLOW-001-033:")
    fix_result = validate_and_fix_flow_step("2026-03-27 05", "FIX-TC-FLOW-001-033")
    print(f"状态：{fix_result['status']}")
    print(f"原始日期：{fix_result['original_date']}")
    print(f"修复后日期：{fix_result['fixed_date']}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
