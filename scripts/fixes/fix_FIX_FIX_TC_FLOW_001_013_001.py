import io

def safe_write(stream, content):
    """
    安全写入函数，自动将非字符串内容转换为字符串
    用于修复 write() argument must be str, not int 错误
    """
    if not isinstance(content, str):
        content = str(content)
    return stream.write(content)

def fix_write_type_error():
    """
    修复写入类型错误的主函数
    模拟文件写入场景并验证修复效果
    返回 True 表示修复验证通过
    """
    try:
        # 使用 StringIO 模拟文件对象流
        stream = io.StringIO()
        
        # 模拟原本会报错的场景：直接写入整数
        # 错误写法：stream.write(1001) -> TypeError
        # 修复写法：使用安全写入封装或显式转换
        safe_write(stream, 1001)
        safe_write(stream, "\n")
        safe_write(stream, 2002)
        
        # 验证写入内容
        result = stream.getvalue()
        expected = "1001\n2002"
        
        if result == expected:
            return True
        else:
            return False
    except TypeError as e:
        # 如果仍然捕获到类型错误，说明修复未生效
        if "must be str, not int" in str(e):
            return False
        raise

if __name__ == "__main__":
    success = fix_write_type_error()
    print(f"修复验证结果：{'成功' if success else '失败'}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
