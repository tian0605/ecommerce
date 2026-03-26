import re
from datetime import datetime

def fix_datetime_format(datetime_str):
    """
    修复不完整的日期时间格式
    处理类似 '2026-03-27 00' 这样的不完整时间字符串
    """
    if not datetime_str or not isinstance(datetime_str, str):
        raise ValueError("无效的日期时间字符串")
    
    # 移除多余空格
    datetime_str = datetime_str.strip()
    
    # 匹配日期部分
    date_pattern = r'^(\d{4}-\d{2}-\d{2})'
    date_match = re.match(date_pattern, datetime_str)
    
    if not date_match:
        raise ValueError(f"无法解析日期部分：{datetime_str}")
    
    date_part = date_match.group(1)
    time_part = datetime_str[len(date_part):].strip()
    
    # 处理时间部分
    if not time_part:
        # 没有时间部分，默认添加 00:00:00
        time_part = "00:00:00"
    elif re.match(r'^\d{2}$', time_part):
        # 只有小时，补充分钟和秒
        time_part = f"{time_part}:00:00"
    elif re.match(r'^\d{2}:\d{2}$', time_part):
        # 有时和分，补充秒
        time_part = f"{time_part}:00"
    elif re.match(r'^\d{2}:\d{2}:\d{2}$', time_part):
        # 完整的时间格式，无需处理
        pass
    else:
        raise ValueError(f"无法解析时间部分：{time_part}")
    
    # 组合完整的日期时间字符串
    full_datetime = f"{date_part} {time_part}"
    
    # 验证格式是否正确
    try:
        datetime.strptime(full_datetime, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise ValueError(f"日期时间格式验证失败：{full_datetime}, 错误：{e}")
    
    return full_datetime


def process_task_datetime(task_info):
    """
    处理任务中的日期时间字段
    """
    if not isinstance(task_info, dict):
        raise ValueError("任务信息必须是字典格式")
    
    # 常见的日期时间字段名
    datetime_fields = ['datetime', 'time', 'date', 'timestamp', 'exec_time', 'create_time']
    
    for field in datetime_fields:
        if field in task_info and task_info[field]:
            try:
                task_info[field] = fix_datetime_format(str(task_info[field]))
            except ValueError as e:
                print(f"警告：字段 {field} 处理失败：{e}")
                continue
    
    return task_info


# 测试验证
def test_fix():
    """测试日期时间格式修复功能"""
    test_cases = [
        ("2026-03-27 00", "2026-03-27 00:00:00"),
        ("2026-03-27 00:30", "2026-03-27 00:30:00"),
        ("2026-03-27 00:30:45", "2026-03-27 00:30:45"),
        ("2026-03-27", "2026-03-27 00:00:00"),
    ]
    
    for input_str, expected in test_cases:
        result = fix_datetime_format(input_str)
        assert result == expected, f"测试失败：{input_str} -> {result}, 期望：{expected}"
    
    # 测试任务信息处理
    task_info = {
        "task_id": "FIX-TC-FLOW-001-011",
        "datetime": "2026-03-27 00",
        "status": "failed"
    }
    processed = process_task_datetime(task_info)
    assert processed["datetime"] == "2026-03-27 00:00:00"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
