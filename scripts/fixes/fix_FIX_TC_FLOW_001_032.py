import re
from datetime import datetime

def fix_datetime_format(datetime_str):
    """
    修复不完整的日期时间格式
    处理类似 '2026-03-27 05' 这样的不完整时间字符串
    """
    if not datetime_str or not isinstance(datetime_str, str):
        raise ValueError("无效的日期时间字符串")
    
    datetime_str = datetime_str.strip()
    
    # 模式1: 完整格式 YYYY-MM-DD HH:MM:SS
    if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', datetime_str):
        return datetime_str
    
    # 模式2: 缺少秒数 YYYY-MM-DD HH:MM
    if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', datetime_str):
        return datetime_str + ':00'
    
    # 模式3: 只有小时 YYYY-MM-DD HH
    if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}$', datetime_str):
        return datetime_str + ':00:00'
    
    # 模式4: 只有日期 YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', datetime_str):
        return datetime_str + ' 00:00:00'
    
    # 模式5: 带T的ISO格式
    if 'T' in datetime_str:
        datetime_str = datetime_str.replace('T', ' ')
        return fix_datetime_format(datetime_str)
    
    raise ValueError(f"无法解析的日期时间格式: {datetime_str}")


def parse_datetime_safe(datetime_str):
    """
    安全解析日期时间字符串，自动修复格式问题
    """
    try:
        fixed_str = fix_datetime_format(datetime_str)
        return datetime.strptime(fixed_str, '%Y-%m-%d %H:%M:%S')
    except Exception as e:
        raise ValueError(f"日期时间解析失败: {datetime_str}, 错误: {str(e)}")


def validate_task_flow(task_date, task_hour):
    """
    验证任务流程的日期时间
    用于电商运营自动化任务执行
    """
    # 构建完整的日期时间字符串
    if isinstance(task_hour, int):
        task_hour = f"{task_hour:02d}"
    
    datetime_str = f"{task_date} {task_hour}"
    
    try:
        parsed_dt = parse_datetime_safe(datetime_str)
        return {
            'success': True,
            'datetime': parsed_dt,
            'formatted': parsed_dt.strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'original_input': f"{task_date} {task_hour}"
        }


# 测试验证
def test_fix():
    """测试日期时间格式修复功能"""
    test_cases = [
        ('2026-03-27 05', '2026-03-27 05:00:00'),
        ('2026-03-27 05:30', '2026-03-27 05:30:00'),
        ('2026-03-27 05:30:45', '2026-03-27 05:30:45'),
        ('2026-03-27', '2026-03-27 00:00:00'),
    ]
    
    for input_str, expected in test_cases:
        result = fix_datetime_format(input_str)
        assert result == expected, f"失败: {input_str} -> {result}, 期望: {expected}"
    
    # 测试任务流程验证
    result = validate_task_flow('2026-03-27', 5)
    assert result['success'] == True, "任务流程验证失败"
    
    return True


if __name__ == '__main__':
    # 执行测试
    if test_fix():
        print("所有测试通过!")
        
        # 演示修复示例
        print("\n修复示例:")
        sample = '2026-03-27 05'
        fixed = fix_datetime_format(sample)
        print(f"原始: {sample}")
        print(f"修复后: {fixed}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
