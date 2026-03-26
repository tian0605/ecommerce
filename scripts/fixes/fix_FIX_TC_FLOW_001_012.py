import re
from datetime import datetime

def fix_datetime_format(datetime_str):
    """
    修复不完整的日期时间格式
    处理类似 '2026-03-27 00' 这样的不完整时间字符串
    """
    if not datetime_str or not isinstance(datetime_str, str):
        raise ValueError("日期时间字符串不能为空")
    
    # 定义支持的日期时间格式
    supported_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H",
        "%Y-%m-%d",
    ]
    
    # 尝试直接解析
    for fmt in supported_formats:
        try:
            dt = datetime.strptime(datetime_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    
    # 尝试修复不完整的格式（如 '2026-03-27 00'）
    fixed_str = repair_incomplete_datetime(datetime_str)
    if fixed_str:
        return fixed_str
    
    raise ValueError(f"无法解析日期时间格式：{datetime_str}")


def repair_incomplete_datetime(datetime_str):
    """
    修复不完整的日期时间字符串
    例如：'2026-03-27 00' -> '2026-03-27 00:00:00'
    """
    datetime_str = datetime_str.strip()
    
    # 匹配日期 + 小时格式：2026-03-27 00
    pattern_date_hour = r'^(\d{4}-\d{2}-\d{2})\s+(\d{1,2})$'
    match = re.match(pattern_date_hour, datetime_str)
    if match:
        date_part = match.group(1)
        hour_part = match.group(2).zfill(2)
        return f"{date_part} {hour_part}:00:00"
    
    # 匹配只有日期格式：2026-03-27
    pattern_date_only = r'^(\d{4}-\d{2}-\d{2})$'
    match = re.match(pattern_date_only, datetime_str)
    if match:
        return f"{match.group(1)} 00:00:00"
    
    return None


def validate_and_execute_flow(task_id, datetime_str):
    """
    验证并执行流程步骤
    修复日期时间格式后执行任务
    """
    try:
        # 修复日期时间格式
        fixed_datetime = fix_datetime_format(datetime_str)
        
        # 模拟执行流程步骤
        execution_result = {
            "task_id": task_id,
            "original_datetime": datetime_str,
            "fixed_datetime": fixed_datetime,
            "status": "success",
            "message": "日期时间格式修复成功"
        }
        
        return execution_result
        
    except Exception as e:
        return {
            "task_id": task_id,
            "original_datetime": datetime_str,
            "fixed_datetime": None,
            "status": "failed",
            "message": str(e)
        }


# 测试验证
def test_fix():
    """测试日期时间格式修复功能"""
    
    # 测试用例1：不完整的小时格式
    result1 = validate_and_execute_flow("FIX-TC-FLOW-001-012", "2026-03-27 00")
    assert result1["status"] == "success"
    assert result1["fixed_datetime"] == "2026-03-27 00:00:00"
    
    # 测试用例2：完整格式
    result2 = validate_and_execute_flow("FIX-TC-FLOW-001-012", "2026-03-27 10:30:00")
    assert result2["status"] == "success"
    assert result2["fixed_datetime"] == "2026-03-27 10:30:00"
    
    # 测试用例3：只有日期
    result3 = validate_and_execute_flow("FIX-TC-FLOW-001-012", "2026-03-27")
    assert result3["status"] == "success"
    assert result3["fixed_datetime"] == "2026-03-27 00:00:00"
    
    # 测试用例4：日期+小时分钟
    result4 = validate_and_execute_flow("FIX-TC-FLOW-001-012", "2026-03-27 14:30")
    assert result4["status"] == "success"
    assert result4["fixed_datetime"] == "2026-03-27 14:30:00"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    # 运行测试
    test_fix()
    
    # 执行实际修复
    result = validate_and_execute_flow("FIX-TC-FLOW-001-012", "2026-03-27 00")
    print(f"\n修复结果：{result}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
