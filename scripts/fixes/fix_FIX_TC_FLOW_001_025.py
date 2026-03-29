from datetime import datetime
from typing import Optional, Union
import re

def fix_datetime_format(date_str: Optional[str], target_format: str = "%Y-%m-%d %H:%M:%S") -> Optional[str]:
    """
    修复日期时间格式解析问题
    处理多种常见日期格式，返回统一格式
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    # 清理字符串
    date_str = date_str.strip()
    
    # 定义多种可能的日期格式
    date_formats = [
        "%Y-%m-%d %H",           # 2026-03-27 03
        "%Y-%m-%d %H:%M",        # 2026-03-27 03:00
        "%Y-%m-%d %H:%M:%S",     # 2026-03-27 03:00:00
        "%Y-%m-%dT%H:%M:%S",     # ISO格式
        "%Y-%m-%d",              # 仅日期
        "%Y/%m/%d %H:%M:%S",     # 斜杠分隔
        "%d-%m-%Y %H:%M:%S",     # 日月年
        "%Y年%m月%d日 %H时",     # 中文格式
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime(target_format)
        except ValueError:
            continue
    
    # 尝试提取数字部分重新组合
    numbers = re.findall(r'\d+', date_str)
    if len(numbers) >= 3:
        try:
            year = int(numbers[0])
            month = int(numbers[1])
            day = int(numbers[2])
            hour = int(numbers[3]) if len(numbers) > 3 else 0
            minute = int(numbers[4]) if len(numbers) > 4 else 0
            second = int(numbers[5]) if len(numbers) > 5 else 0
            dt = datetime(year, month, day, hour, minute, second)
            return dt.strftime(target_format)
        except (ValueError, IndexError):
            pass
    
    # 如果都无法解析，返回原字符串并记录警告
    print(f"警告：无法解析日期格式 '{date_str}'，返回原值")
    return date_str


def validate_flow_step(step_date: Optional[str], step_id: str = "03") -> dict:
    """
    验证并修复流程步骤的日期时间
    用于电商自动化流程中的步骤执行检查
    """
    result = {
        "step_id": step_id,
        "original_date": step_date,
        "fixed_date": None,
        "status": "pending",
        "error": None
    }
    
    try:
        if not step_date:
            result["status"] = "failed"
            result["error"] = "日期时间为空"
            return result
        
        fixed_date = fix_datetime_format(step_date)
        
        if fixed_date:
            result["fixed_date"] = fixed_date
            result["status"] = "success"
        else:
            result["status"] = "failed"
            result["error"] = "日期格式修复失败"
            
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
    
    return result


def test_fix():
    """测试验证修复函数"""
    # 测试用例1：标准格式
    test1 = fix_datetime_format("2026-03-27 03")
    assert test1 == "2026-03-27 03:00:00", f"测试1失败：{test1}"
    
    # 测试用例2：完整时间格式
    test2 = fix_datetime_format("2026-03-27 03:30:45")
    assert test2 == "2026-03-27 03:30:45", f"测试2失败：{test2}"
    
    # 测试用例3：空值处理
    test3 = fix_datetime_format(None)
    assert test3 is None, f"测试3失败：{test3}"
    
    # 测试用例4：流程步骤验证
    test4 = validate_flow_step("2026-03-27 03", "03")
    assert test4["status"] == "success", f"测试4失败：{test4}"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    # 执行测试
    test_fix()
    
    # 示例：修复任务中的日期问题
    print("\n修复示例：")
    result = validate_flow_step("2026-03-27 03", "03")
    print(f"步骤ID: {result['step_id']}")
    print(f"原始日期：{result['original_date']}")
    print(f"修复后日期：{result['fixed_date']}")
    print(f"状态：{result['status']}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
