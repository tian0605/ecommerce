from datetime import datetime
import re

def fix_datetime_format(datetime_str):
    """
    修复日期时间格式解析错误
    处理不完整的日期时间字符串，如"2026-03-27 03"
    """
    if not datetime_str or not isinstance(datetime_str, str):
        return datetime_str
    
    # 清理字符串
    datetime_str = datetime_str.strip()
    
    # 定义多种可能的日期时间格式
    date_formats = [
        '%Y-%m-%d %H',      # 2026-03-27 03
        '%Y-%m-%d %H:%M',   # 2026-03-27 03:00
        '%Y-%m-%d %H:%M:%S', # 2026-03-27 03:00:00
        '%Y-%m-%d',         # 2026-03-27
        '%Y/%m/%d %H',      # 2026/03/27 03
        '%Y/%m/%d %H:%M',   # 2026/03/27 03:00
        '%Y/%m/%d %H:%M:%S', # 2026/03/27 03:00:00
        '%Y/%m/%d',         # 2026/03/27
        '%Y%m%d%H',         # 2026032703
        '%Y%m%d%H%M',       # 202603270300
        '%Y%m%d%H%M%S',     # 20260327030000
    ]
    
    # 尝试多种格式解析
    for fmt in date_formats:
        try:
            dt = datetime.strptime(datetime_str, fmt)
            # 返回标准格式
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    
    # 如果所有格式都失败，尝试智能补全
    fixed_str = smart_complete_datetime(datetime_str)
    if fixed_str:
        return fixed_str
    
    # 无法修复则返回原值
    return datetime_str


def smart_complete_datetime(datetime_str):
    """
    智能补全不完整的日期时间字符串
    """
    # 匹配日期部分
    date_pattern = r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})'
    date_match = re.search(date_pattern, datetime_str)
    
    if date_match:
        year, month, day = date_match.groups()
        # 提取小时部分（如果有）
        hour_pattern = r'(\d{1,2})(?::\d{1,2})?(?::\d{1,2})?$'
        hour_match = re.search(hour_pattern, datetime_str)
        
        if hour_match:
            hour = hour_match.group(1).zfill(2)
            return f"{year}-{month.zfill(2)}-{day.zfill(2)} {hour}:00:00"
        else:
            return f"{year}-{month.zfill(2)}-{day.zfill(2)} 00:00:00"
    
    return None


def validate_datetime(datetime_str):
    """
    验证日期时间字符串是否有效
    """
    try:
        fixed = fix_datetime_format(datetime_str)
        datetime.strptime(fixed, '%Y-%m-%d %H:%M:%S')
        return True, fixed
    except Exception as e:
        return False, str(e)


# 测试验证
def test_fix():
    """测试日期时间修复功能"""
    test_cases = [
        ('2026-03-27 03', '2026-03-27 03:00:00'),
        ('2026-03-27 03:30', '2026-03-27 03:30:00'),
        ('2026-03-27 03:30:45', '2026-03-27 03:30:45'),
        ('2026-03-27', '2026-03-27 00:00:00'),
        ('2026/03/27 03', '2026-03-27 03:00:00'),
    ]
    
    all_passed = True
    for input_str, expected in test_cases:
        result = fix_datetime_format(input_str)
        if result != expected:
            print(f"FAIL: {input_str} -> {result} (expected: {expected})")
            all_passed = False
        else:
            print(f"PASS: {input_str} -> {result}")
    
    return all_passed


if __name__ == '__main__':
    # 运行测试
    success = test_fix()
    print(f"\n所有测试{'通过' if success else '失败'}")
    
    # 示例：修复任务中的日期时间
    problematic_datetime = "2026-03-27 03"
    fixed_datetime = fix_datetime_format(problematic_datetime)
    print(f"\n修复示例: {problematic_datetime} -> {fixed_datetime}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
