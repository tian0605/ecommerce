from datetime import datetime
import re

def fix_datetime_format(datetime_str):
    """
    修复日期时间格式解析错误
    处理不完整的日期时间字符串，如 '2026-03-27 07'
    """
    if not datetime_str or not isinstance(datetime_str, str):
        raise ValueError("无效的日期时间字符串")
    
    # 清理字符串
    datetime_str = datetime_str.strip()
    
    # 定义多种可能的日期时间格式
    formats = [
        '%Y-%m-%d %H:%M:%S',  # 完整格式
        '%Y-%m-%d %H:%M',     # 缺少秒
        '%Y-%m-%d %H',        # 缺少分钟和秒（问题格式）
        '%Y-%m-%d',           # 只有日期
        '%Y/%m/%d %H:%M:%S',  # 斜杠分隔
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d %H',
    ]
    
    # 尝试自动补全不完整的格式
    if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}$', datetime_str):
        # 格式如 '2026-03-27 07'，补全为 '2026-03-27 07:00:00'
        datetime_str = datetime_str + ':00:00'
    elif re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', datetime_str):
        # 格式如 '2026-03-27 07:30'，补全为 '2026-03-27 07:30:00'
        datetime_str = datetime_str + ':00'
    
    # 尝试解析
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"无法解析的日期时间格式：{datetime_str}")


def validate_task_flow(task_date):
    """
    验证任务流程日期，修复日期解析问题
    """
    try:
        parsed_date = fix_datetime_format(task_date)
        return {
            'status': 'success',
            'parsed_date': parsed_date.isoformat(),
            'message': '日期格式修复成功'
        }
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'message': '日期格式修复失败'
        }


# 测试验证
def test_fix():
    """测试日期时间格式修复功能"""
    test_cases = [
        ('2026-03-27 07', True),      # 问题格式
        ('2026-03-27 07:30', True),   # 缺少秒
        ('2026-03-27 07:30:00', True), # 完整格式
        ('2026-03-27', True),         # 只有日期
    ]
    
    all_passed = True
    for test_input, should_pass in test_cases:
        result = validate_task_flow(test_input)
        if should_pass and result['status'] != 'success':
            print(f"测试失败：{test_input} -> {result}")
            all_passed = False
        else:
            print(f"测试通过：{test_input} -> {result['status']}")
    
    return all_passed


if __name__ == '__main__':
    # 执行测试
    test_result = test_fix()
    print(f"\n所有测试{'通过' if test_result else '失败'}")
    
    # 修复具体问题
    problem_date = '2026-03-27 07'
    fix_result = validate_task_flow(problem_date)
    print(f"\n问题日期 '{problem_date}' 修复结果：{fix_result}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
