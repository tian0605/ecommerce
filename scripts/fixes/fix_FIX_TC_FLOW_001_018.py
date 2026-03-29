import re
from datetime import datetime
from typing import Optional, Dict, Any

def parse_flow_step_identifier(step_id: str) -> Dict[str, Any]:
    """
    解析流程步骤标识符，处理日期时间格式
    支持格式：2026-03-27 01, 2026-03-27-01, 2026032701 等
    """
    if not step_id or not isinstance(step_id, str):
        raise ValueError(f"无效的步骤标识符：{step_id}")
    
    result = {
        'original': step_id,
        'date': None,
        'hour': None,
        'datetime_obj': None,
        'is_valid': False
    }
    
    # 尝试多种日期格式解析
    patterns = [
        (r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2})', '%Y-%m-%d %H'),
        (r'(\d{4})-(\d{2})-(\d{2})-(\d{2})', '%Y-%m-%d-%H'),
        (r'(\d{4})(\d{2})(\d{2})(\d{2})', '%Y%m%d%H'),
        (r'(\d{4})/(\d{2})/(\d{2})\s+(\d{2})', '%Y/%m/%d %H'),
    ]
    
    for pattern, date_format in patterns:
        match = re.match(pattern, step_id.strip())
        if match:
            try:
                # 重构为标准格式
                if date_format == '%Y-%m-%d %H':
                    date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)} {match.group(4)}:00:00"
                    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                elif date_format == '%Y-%m-%d-%H':
                    date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)} {match.group(4)}:00:00"
                    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                elif date_format == '%Y%m%d%H':
                    date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)} {match.group(4)}:00:00"
                    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                elif date_format == '%Y/%m/%d %H':
                    date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)} {match.group(4)}:00:00"
                    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                else:
                    continue
                
                result['date'] = dt.strftime('%Y-%m-%d')
                result['hour'] = dt.strftime('%H')
                result['datetime_obj'] = dt
                result['is_valid'] = True
                break
            except ValueError as e:
                continue
    
    return result


def validate_flow_step(step_id: str, allow_future: bool = True) -> Dict[str, Any]:
    """
    验证流程步骤是否有效，检查日期时间合理性
    """
    parsed = parse_flow_step_identifier(step_id)
    
    validation_result = {
        'step_id': step_id,
        'is_valid': False,
        'error': None,
        'parsed': parsed
    }
    
    if not parsed['is_valid']:
        validation_result['error'] = f"无法解析步骤标识符格式：{step_id}"
        return validation_result
    
    # 检查是否为未来时间（根据配置决定是否允许）
    if not allow_future:
        if parsed['datetime_obj'] > datetime.now():
            validation_result['error'] = f"步骤时间为未来时间：{parsed['datetime_obj']}"
            return validation_result
    
    # 检查日期合理性
    if parsed['datetime_obj'].year < 2000 or parsed['datetime_obj'].year > 2100:
        validation_result['error'] = f"年份超出合理范围：{parsed['datetime_obj'].year}"
        return validation_result
    
    validation_result['is_valid'] = True
    return validation_result


def fix_flow_step_execution(step_id: str) -> Dict[str, Any]:
    """
    修复流程步骤执行问题，主入口函数
    """
    result = {
        'success': False,
        'step_id': step_id,
        'message': '',
        'parsed_info': None
    }
    
    try:
        # 验证步骤标识符
        validation = validate_flow_step(step_id, allow_future=True)
        
        if not validation['is_valid']:
            result['message'] = f"验证失败：{validation['error']}"
            return result
        
        result['parsed_info'] = validation['parsed']
        result['success'] = True
        result['message'] = f"步骤标识符解析成功：{validation['parsed']['date']} {validation['parsed']['hour']}时"
        
    except Exception as e:
        result['message'] = f"执行异常：{str(e)}"
    
    return result


# 测试验证
def test_fix():
    """测试修复函数"""
    test_cases = [
        '2026-03-27 01',
        '2026-03-27-01',
        '2026032701',
        '2026/03/27 01',
    ]
    
    all_passed = True
    for step_id in test_cases:
        result = fix_flow_step_execution(step_id)
        if not result['success']:
            print(f"测试失败：{step_id} - {result['message']}")
            all_passed = False
        else:
            print(f"测试通过：{step_id} - {result['message']}")
    
    # 测试无效输入
    invalid_result = fix_flow_step_execution('invalid-format')
    if invalid_result['success']:
        print("测试失败：应拒绝无效格式")
        all_passed = False
    else:
        print("测试通过：正确拒绝无效格式")
    
    return all_passed


if __name__ == '__main__':
    # 运行测试
    test_result = test_fix()
    print(f"\n所有测试{'通过' if test_result else '失败'}")
    
    # 修复原始问题
    original_step = '2026-03-27 01'
    fix_result = fix_flow_step_execution(original_step)
    print(f"\n原始问题修复结果：{fix_result}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
