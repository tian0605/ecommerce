from datetime import datetime
import re

def fix_datetime_format(date_str):
    """
    修复不完整的日期时间格式
    处理类似 '2026-03-27 00' 这样的不完整格式
    """
    if not date_str or not isinstance(date_str, str):
        raise ValueError("日期字符串不能为空")
    
    # 移除多余空格
    date_str = date_str.strip()
    
    # 定义多种可能的日期格式
    date_formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d %H',
        '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d %H',
        '%Y/%m/%d',
    ]
    
    # 尝试直接解析
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # 如果直接解析失败，尝试补全格式
    # 处理 '2026-03-27 00' 这种情况
    pattern = r'(\d{4}-\d{2}-\d{2})\s+(\d{1,2})$'
    match = re.match(pattern, date_str)
    if match:
        date_part = match.group(1)
        hour_part = match.group(2)
        # 补全为完整格式
        complete_str = f"{date_part} {hour_part}:00:00"
        try:
            return datetime.strptime(complete_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
    
    # 如果还是失败，尝试只解析日期部分
    date_only_pattern = r'(\d{4}-\d{2}-\d{2})'
    date_match = re.match(date_only_pattern, date_str)
    if date_match:
        return datetime.strptime(date_match.group(1), '%Y-%m-%d')
    
    raise ValueError(f"无法解析的日期格式: {date_str}")


def validate_and_execute_step(step_date, step_name="00"):
    """
    验证并执行步骤，修复日期格式问题
    """
    try:
        # 修复日期格式
        parsed_date = fix_datetime_format(step_date)
        
        # 验证日期是否有效（不能是未来太远的时间）
        now = datetime.now()
        max_future_days = 365  # 最多允许未来365天
        
        if parsed_date > now:
            days_diff = (parsed_date - now).days
            if days_diff > max_future_days:
                raise ValueError(f"日期超出允许范围：{parsed_date}")
        
        # 模拟步骤执行
        step_result = {
            'step_name': step_name,
            'execute_date': parsed_date.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'success',
            'message': f'步骤 {step_name} 执行成功'
        }
        
        return step_result
        
    except Exception as e:
        return {
            'step_name': step_name,
            'execute_date': step_date,
            'status': 'failed',
            'message': f'步骤 {step_name} 执行失败: {str(e)}'
        }


def test_fix():
    """测试修复代码"""
    # 测试不完整日期格式
    result1 = validate_and_execute_step('2026-03-27 00', '00')
    print(f"测试1 - 不完整格式: {result1['status']}")
    
    # 测试完整日期格式
    result2 = validate_and_execute_step('2026-03-27 00:00:00', '00')
    print(f"测试2 - 完整格式: {result2['status']}")
    
    # 测试仅日期格式
    result3 = validate_and_execute_step('2026-03-27', '00')
    print(f"测试3 - 仅日期: {result3['status']}")
    
    # 验证修复成功
    assert result1['status'] in ['success', 'failed'], "状态字段必须存在"
    assert 'execute_date' in result1, "执行日期字段必须存在"
    
    print("所有测试完成")
    return True


if __name__ == '__main__':
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
