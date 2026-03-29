import logging
from datetime import datetime

# 配置日志以便调试
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def validate_and_parse_step_date(date_string):
    """
    修复日期解析逻辑，支持多种常见格式并抛出明确异常
    """
    if not date_string or not isinstance(date_string, str):
        raise ValueError(f"无效的日期输入：{date_string}")
    
    # 定义可能的日期格式列表，增加兼容性
    date_formats = [
        "%Y-%m-%d %H",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]
    
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_string.strip(), fmt)
            logging.info(f"成功解析日期：{date_string} 使用格式 {fmt}")
            return parsed_date
        except ValueError:
            continue
    
    # 如果所有格式都失败，抛出明确错误以便追踪
    error_msg = f"无法解析日期字符串：{date_string}，支持的格式：{date_formats}"
    logging.error(error_msg)
    raise ValueError(error_msg)

def execute_step_07_fixed(step_date_param):
    """
    修复后的步骤执行函数，包含完整的错误处理和状态返回
    """
    try:
        # 1. 验证并解析日期
        parsed_date = validate_and_parse_step_date(step_date_param)
        
        # 2. 模拟业务逻辑检查（例如防止日期过早或过晚）
        if parsed_date.year < 2024:
            logging.warning(f"日期 {parsed_date} 早于预期，可能影响业务逻辑")
            
        # 3. 返回成功状态
        return {
            "status": "success",
            "step_id": "FIX-TC-FLOW-001-039",
            "parsed_date": parsed_date.isoformat(),
            "message": "步骤执行成功"
        }
        
    except Exception as e:
        # 4. 捕获所有异常并记录详细错误，避免静默失败
        logging.error(f"步骤执行失败：{str(e)}")
        return {
            "status": "failed",
            "step_id": "FIX-TC-FLOW-001-039",
            "error": str(e),
            "message": "步骤执行异常，请检查日志"
        }

if __name__ == "__main__":
    # 测试验证
    test_input = "2026-03-27 07"
    print(f"正在测试输入：{test_input}")
    result = execute_step_07_fixed(test_input)
    print(f"执行结果：{result}")
    
    # 断言验证修复是否生效
    assert result["status"] == "success", "修复后应该成功解析该日期格式"
    assert "2026-03-27" in result["parsed_date"], "解析后的日期应包含原日期信息"
    print("测试通过：代码修复有效")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
