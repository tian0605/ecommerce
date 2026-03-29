import io
import os

def safe_write_data(file_obj, data):
    """
    安全写入数据到文件对象，自动处理整数到字符串的转换
    修复 write() argument must be str, not int 错误
    """
    # 确保写入的数据是字符串类型
    if not isinstance(data, str):
        data = str(data)
    
    # 执行写入操作
    return file_obj.write(data)

def fix_write_operation(file_path, content):
    """
    封装文件写入操作，确保内容类型正确
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        safe_write_data(f, content)

def test_fix():
    """测试修复代码是否有效"""
    # 使用内存文件对象进行测试
    buffer = io.StringIO()
    
    # 测试写入整数（原本会报错的场景）
    try:
        safe_write_data(buffer, 10086)
        safe_write_data(buffer, 2023)
        result = buffer.getvalue()
        
        # 验证结果是否为字符串拼接
        assert result == "100862023", f"Expected '100862023', got '{result}'"
        print("测试通过：整数已成功转换为字符串并写入")
        return True
    except TypeError as e:
        print(f"测试失败：{e}")
        return False

if __name__ == "__main__":
    # 运行测试验证
    success = test_fix()
    
    # 示例：实际文件写入测试
    test_file = "test_fix_output.txt"
    try:
        fix_write_operation(test_file, 9527)
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == "9527"
        print("文件写入测试通过")
        os.remove(test_file)
    except Exception as e:
        print(f"文件测试异常：{e}")
    
    if success:
        print("修复验证完成")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
