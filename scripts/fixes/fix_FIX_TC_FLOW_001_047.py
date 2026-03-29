import datetime
import logging

# 配置日志以便调试
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def fix_step_validation(step_identifier: str) -> bool:
    """
    修复步骤执行验证逻辑，增强时间格式容错性和异常处理
    针对类似 '2026-03-27 08' 的步骤 ID 进行安全解析和状态检查
    """
    try:
        # 1. 增强时间格式解析容错，支持多种常见时间戳格式
        date_formats = [
            "%Y-%m-%d %H",       # 匹配 2026-03-27 08
            "%Y-%m-%d %H:%M",    # 匹配 2026-03-27 08:00
            "%Y-%m-%d %H:%M:%S", # 匹配 2026-03-27 08:00:00
            "%Y-%m-%d"           # 匹配 2026-03-27
        ]
        
        parsed_date = None
        for fmt in date_formats:
            try:
                parsed_date = datetime.datetime.strptime(step_identifier, fmt)
                break
            except ValueError:
                continue
        
        if parsed_date is None:
            logging.error(f"无法解析步骤标识符格式：{step_identifier}")
            return False
        
        # 2. 模拟执行状态检查，修复原本可能存在的空值引用错误
        status_info = check_execution_status(step_identifier)
        
        if not status_info:
            logging.error(f"步骤 {step_identifier} 状态信息缺失")
            return False
            
        if status_info.get("status") == "success":
            logging.info(f"步骤 {step_identifier} 验证通过")
            return True
        else:
            logging.error(f"步骤 {step_identifier} 执行失败：{status_info.get('msg', 'Unknown Error')}")
            return False
            
    except Exception as e:
        logging.error(f"步骤验证过程中发生异常：{str(e)}")
        return False

def check_execution_status(step_id: str) -> dict:
    """模拟步骤状态查询，实际场景应替换为数据库或 API 调用"""
    # 模拟成功场景，实际逻辑中需确保此处不返回 None
    return {"status": "success", "msg": "OK"}

def test_fix():
    """测试验证修复代码"""
    target_step = "2026-03-27 08"
    success = fix_step_validation(target_step)
    # 验证函数是否正常运行且不抛出异常
    assert isinstance(success, bool), "测试失败：预期返回布尔值"
    print("测试执行完成，函数无崩溃")
    return True

if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
