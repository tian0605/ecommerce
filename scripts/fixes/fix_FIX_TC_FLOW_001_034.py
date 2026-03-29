import re
from datetime import datetime

def fix_datetime_format(datetime_str):
    """
    修复不完整的日期时间格式
    处理类似 '2026-03-27 05' 这样的不完整时间字符串
    """
    if not datetime_str or not isinstance(datetime_str, str):
        raise ValueError("输入必须是有效的字符串")
    
    # 清理空白字符
    datetime_str = datetime_str.strip()
    
    # 定义多种时间格式模式
    patterns = [
        # 完整格式
        (r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', '%Y-%m-%d %H:%M:%S'),
        # 缺少秒
        (r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', '%Y-%m-%d %H:%M'),
        # 只有小时（问题所在）
        (r'^\d{4}-\d{2}-\d{2} \d{2}$', '%Y-%m-%d %H'),
        # 只有日期
        (r'^\d{4}-\d{2}-\d{2}$', '%Y-%m-%d'),
    ]
    
    for pattern, fmt in patterns:
        if re.match(pattern, datetime_str):
            # 如果格式不完整，补充默认值
            if fmt == '%Y-%m-%d %H':
                datetime_str = datetime_str + ':00:00'
                fmt = '%Y-%m-%d %H:%M:%S'
            elif fmt == '%Y-%m-%d %H:%M':
                datetime_str = datetime_str + ':00'
                fmt = '%Y-%m-%d %H:%M:%S'
            elif fmt == '%Y-%m-%d':
                datetime_str = datetime_str + ' 00:00:00'
                fmt = '%Y-%m-%d %H:%M:%S'
            
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError as e:
                raise ValueError(f"时间格式解析失败：{datetime_str}, 错误：{e}")
    
    raise ValueError(f"无法识别的时间格式：{datetime_str}")


def validate_flow_step(step_date, step_hour):
    """
    验证流程步骤的时间信息
    修复类似 2026-03-27 05 这样的步骤执行失败问题
    """
    try:
        # 组合日期和时间
        if step_hour and len(str(step_hour)) == 2:
            step_hour = f"{step_hour}:00:00"
        elif step_hour and len(str(step_hour)) == 5:
            step_hour = f"{step_hour}:00"
        
        datetime_str = f"{step_date} {step_hour}" if step_hour else step_date
        parsed_time = fix_datetime_format(datetime_str)
        
        return {
            'status': 'success',
            'parsed_time': parsed_time.isoformat(),
            'original_input': datetime_str
        }
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'original_input': f"{step_date} {step_hour}" if step_hour else step_date
        }


def fix_tc_flow_001_034(step_date='2026-03-27', step_hour='05'):
    """
    修复 FIX-TC-FLOW-001-034 任务的时间格式问题
    专门处理 2026-03-27 05 这类不完整的日期时间格式
    """
    result = validate_flow_step(step_date, step_hour)
    
    if result['status'] == 'success':
        print(f"✓ 时间格式修复成功：{result['parsed_time']}")
    else:
        print(f"✗ 时间格式修复失败：{result['error']}")
    
    return result


# 测试验证
def test_fix():
    """测试修复函数"""
    # 测试原始问题场景
    result1 = fix_tc_flow_001_034('2026-03-27', '05')
    assert result1['status'] == 'success', "测试1失败：小时格式修复"
    
    # 测试完整时间格式
    result2 = fix_tc_flow_001_034('2026-03-27', '05:30:00')
    assert result2['status'] == 'success', "测试2失败：完整时间格式"
    
    # 测试只有日期
    result3 = fix_tc_flow_001_034('2026-03-27', None)
    assert result3['status'] == 'success', "测试3失败：只有日期"
    
    print("所有测试通过！")
    return True


if __name__ == '__main__':
    # 执行修复
    fix_tc_flow_001_034()
    # 运行测试
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
