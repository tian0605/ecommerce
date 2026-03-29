from datetime import datetime
import re

def fix_datetime_format(date_str):
    """
    修复日期时间格式问题
    处理不完整的日期时间字符串，如"2026-03-27 08"
    """
    if not date_str or not isinstance(date_str, str):
        raise ValueError("无效的日期时间字符串")
    
    # 清理字符串
    date_str = date_str.strip()
    
    # 尝试多种日期格式解析
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H",
        "%Y/%m/%d",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt
        except ValueError:
            continue
    
    # 如果都失败，尝试智能补全格式
    # 处理"2026-03-27 08"这种情况
    match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(\d{1,2})$', date_str)
    if match:
        date_part = match.group(1)
        hour_part = match.group(2)
        complete_str = f"{date_part} {hour_part}:00:00"
        try:
            dt = datetime.strptime(complete_str, "%Y-%m-%d %H:%M:%S")
            return dt
        except ValueError:
            pass
    
    raise ValueError(f"无法解析日期时间字符串：{date_str}")


def validate_flow_step(step_date, step_name="步骤"):
    """
    验证流程步骤的日期时间
    """
    try:
        dt = fix_datetime_format(step_date)
        print(f"{step_name}时间解析成功：{dt}")
        return True
    except Exception as e:
        print(f"{step_name}时间解析失败：{e}")
        return False


def test_fix():
    """测试修复代码"""
    test_cases = [
        ("2026-03-27 08", True),
        ("2026-03-27 08:30", True),
        ("2026-03-27 08:30:00", True),
        ("2026-03-27", True),
        ("invalid-date", False),
    ]
    
    all_passed = True
    for date_str, should_pass in test_cases:
        result = validate_flow_step(date_str, f"测试[{date_str}]")
        if result != should_pass:
            all_passed = False
            print(f"测试失败：{date_str}")
    
    return all_passed


if __name__ == "__main__":
    # 运行测试
    success = test_fix()
    print(f"\n所有测试{'通过' if success else '失败'}")
    
    # 修复原始问题
    print("\n修复原始问题：")
    original_date = "2026-03-27 08"
    try:
        fixed_dt = fix_datetime_format(original_date)
        print(f"原始日期：{original_date}")
        print(f"修复后：{fixed_dt}")
        print("修复成功！")
    except Exception as e:
        print(f"修复失败：{e}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
