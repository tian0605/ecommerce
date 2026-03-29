from datetime import datetime
import re

def parse_datetime_step(datetime_str):
    """
    修复日期时间步骤解析错误
    支持多种日期格式并返回标准化结果
    """
    if not datetime_str or not isinstance(datetime_str, str):
        raise ValueError("日期时间字符串不能为空或非字符串类型")
    
    # 清理字符串
    datetime_str = datetime_str.strip()
    
    # 定义支持的日期格式列表
    date_formats = [
        "%Y-%m-%d %H",      # 2026-03-27 01
        "%Y-%m-%d %H:%M",   # 2026-03-27 01:30
        "%Y-%m-%d %H:%M:%S", # 2026-03-27 01:30:00
        "%Y-%m-%dT%H",      # 2026-03-27T01
        "%Y-%m-%dT%H:%M",   # 2026-03-27T01:30
        "%Y/%m/%d %H",      # 2026/03/27 01
        "%Y%m%d%H",         # 2026032701
    ]
    
    parsed_datetime = None
    
    # 尝试多种格式解析
    for fmt in date_formats:
        try:
            parsed_datetime = datetime.strptime(datetime_str, fmt)
            break
        except ValueError:
            continue
    
    if parsed_datetime is None:
        # 尝试提取日期和小时部分
        match = re.match(r'(\d{4})-(\d{2})-(\d{2})\s*(\d{2})?', datetime_str)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            hour = int(match.group(4)) if match.group(4) else 0
            parsed_datetime = datetime(year, month, day, hour, 0, 0)
        else:
            raise ValueError(f"无法解析日期时间格式：{datetime_str}")
    
    return {
        "datetime": parsed_datetime,
        "datetime_str": parsed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "year": parsed_datetime.year,
        "month": parsed_datetime.month,
        "day": parsed_datetime.day,
        "hour": parsed_datetime.hour,
        "step_id": f"{parsed_datetime.strftime('%Y%m%d')}{parsed_datetime.hour:02d}"
    }


def validate_flow_step(step_info):
    """
    验证流程步骤信息是否完整有效
    """
    required_fields = ["datetime", "step_id"]
    
    if not isinstance(step_info, dict):
        return False, "步骤信息必须是字典类型"
    
    for field in required_fields:
        if field not in step_info:
            return False, f"缺少必要字段：{field}"
    
    return True, "验证通过"


def fix_tc_flow_step(task_id, datetime_str):
    """
    主修复函数：处理 TC-FLOW 任务步骤执行失败问题
    """
    try:
        # 解析日期时间
        parsed = parse_datetime_step(datetime_str)
        
        # 验证步骤信息
        is_valid, message = validate_flow_step(parsed)
        
        if not is_valid:
            return {
                "success": False,
                "task_id": task_id,
                "error": message,
                "datetime_str": datetime_str
            }
        
        return {
            "success": True,
            "task_id": task_id,
            "parsed_datetime": parsed["datetime_str"],
            "step_id": parsed["step_id"],
            "year": parsed["year"],
            "month": parsed["month"],
            "day": parsed["day"],
            "hour": parsed["hour"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "task_id": task_id,
            "error": str(e),
            "datetime_str": datetime_str
        }


# 测试验证
def test_fix():
    """测试修复函数"""
    # 测试用例 1: 标准格式
    result1 = fix_tc_flow_step("FIX-TC-FLOW-001-019", "2026-03-27 01")
    assert result1["success"] == True, f"测试 1 失败：{result1}"
    assert result1["step_id"] == "2026032701", f"测试 1 step_id 错误：{result1}"
    
    # 测试用例 2: 带分钟格式
    result2 = fix_tc_flow_step("FIX-TC-FLOW-001-019", "2026-03-27 01:30")
    assert result2["success"] == True, f"测试 2 失败：{result2}"
    
    # 测试用例 3: 空字符串应失败
    result3 = fix_tc_flow_step("FIX-TC-FLOW-001-019", "")
    assert result3["success"] == False, f"测试 3 应该失败：{result3}"
    
    # 测试用例 4: None 应失败
    result4 = fix_tc_flow_step("FIX-TC-FLOW-001-019", None)
    assert result4["success"] == False, f"测试 4 应该失败：{result4}"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    # 运行测试
    test_fix()
    
    # 演示实际使用
    print("\n=== 实际任务修复演示 ===")
    result = fix_tc_flow_step("FIX-TC-FLOW-001-019", "2026-03-27 01")
    print(f"任务 ID: {result['task_id']}")
    print(f"修复状态：{'成功' if result['success'] else '失败'}")
    if result['success']:
        print(f"解析时间：{result['parsed_datetime']}")
        print(f"步骤 ID: {result['step_id']}")
    else:
        print(f"错误信息：{result['error']}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
