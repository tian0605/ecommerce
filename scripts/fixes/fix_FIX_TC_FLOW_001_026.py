from datetime import datetime
import re

def fix_datetime_parse(datetime_str):
    """修复日期时间字符串解析问题"""
    if not datetime_str or not isinstance(datetime_str, str):
        raise ValueError("无效的日期时间字符串")
    
    # 清理字符串
    datetime_str = datetime_str.strip()
    
    # 尝试多种常见格式
    formats = [
        "%Y-%m-%d %H",      # 2026-03-27 03
        "%Y-%m-%d %H:%M",   # 2026-03-27 03:00
        "%Y-%m-%d %H:%M:%S", # 2026-03-27 03:00:00
        "%Y-%m-%dT%H",      # 2026-03-27T03
        "%Y-%m-%dT%H:%M",   # 2026-03-27T03:00
        "%Y-%m-%d",         # 2026-03-27
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    # 如果都失败，尝试智能解析
    match = re.match(r'(\d{4})-(\d{2})-(\d{2})\s*(\d{0,2})?', datetime_str)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        hour = int(match.group(4)) if match.group(4) else 0
        return datetime(year, month, day, hour, 0, 0)
    
    raise ValueError(f"无法解析日期时间：{datetime_str}")

def validate_flow_step(step_name, step_time):
    """验证流程步骤执行"""
    try:
        parsed_time = fix_datetime_parse(step_time)
        # 检查时间是否合理（不过远未来）
        max_future = datetime.now().replace(year=2030)
        if parsed_time > max_future:
            raise ValueError(f"步骤时间超出合理范围：{step_time}")
        return {"status": "success", "step": step_name, "time": parsed_time.isoformat()}
    except Exception as e:
        return {"status": "failed", "step": step_name, "error": str(e)}

def execute_flow_step(step_config):
    """执行流程步骤并返回结果"""
    step_name = step_config.get("step_name", "unknown")
    step_time = step_config.get("step_time", "")
    
    result = validate_flow_step(step_name, step_time)
    
    if result["status"] == "success":
        # 模拟步骤执行成功
        result["executed"] = True
    else:
        result["executed"] = False
    
    return result

# 测试验证
def test_fix():
    """测试修复代码"""
    # 测试原始失败场景
    test_config = {
        "step_name": "2026-03-27 03",
        "step_time": "2026-03-27 03"
    }
    
    result = execute_flow_step(test_config)
    assert result["status"] == "success", f"测试失败：{result}"
    assert result["executed"] == True
    
    # 测试其他格式
    test_cases = [
        "2026-03-27 03:00",
        "2026-03-27 03:00:00",
        "2026-03-27",
    ]
    
    for case in test_cases:
        parsed = fix_datetime_parse(case)
        assert parsed is not None, f"无法解析：{case}"
    
    return True

if __name__ == "__main__":
    success = test_fix()
    print(f"测试 {'通过' if success else '失败'}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
