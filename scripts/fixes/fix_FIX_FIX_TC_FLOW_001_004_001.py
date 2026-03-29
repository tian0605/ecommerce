import io

def safe_write(file_obj, data):
    """
    安全写入数据辅助函数
    自动将非字符串类型转换为字符串，避免 TypeError
    """
    if not isinstance(data, str):
        data = str(data)
    file_obj.write(data)

def fix_write_argument_error():
    """
    修复 write() argument must be str, not int 错误
    模拟电商场景中写入订单ID等整数数据的场景
    """
    # 使用 StringIO 模拟文件写入流
    buffer = io.StringIO()
    
    try:
        # 模拟原本会导致报错的整数数据（如订单号、数量等）
        order_id = 10086
        quantity = 5
        
        # 修复前写法：buffer.write(order_id) 会抛出 TypeError
        # 修复后写法：使用安全写入函数或显式转换
        safe_write(buffer, order_id)
        safe_write(buffer, ",")
        safe_write(buffer, quantity)
        safe_write(buffer, "\n")
        
        result = buffer.getvalue()
        buffer.close()
        return result
    except TypeError as e:
        return f"Error: {e}"

if __name__ == "__main__":
    # 执行修复验证
    output = fix_write_argument_error()
    print(f"写入结果：{output}")
    
    # 验证结果是否符合预期
    assert "10086" in output, "订单号写入失败"
    assert "5" in output, "数量写入失败"
    print("修复验证成功：整数已正确转换为字符串写入")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
