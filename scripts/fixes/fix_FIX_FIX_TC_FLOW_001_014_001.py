import os
import tempfile

def safe_write_to_file(file_path, content):
    """
    安全写入数据到文件，自动处理类型转换以避免 write() 参数类型错误
    修复：write() argument must be str, not int
    """
    # 关键修复：确保写入的内容是字符串类型
    if not isinstance(content, str):
        content = str(content)
    
    # 使用 utf-8 编码打开文件，确保兼容性
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True

def test_fix():
    """测试验证修复代码是否有效"""
    # 创建临时文件
    temp_file = tempfile.mktemp(suffix='.txt')
    
    try:
        # 测试场景：原本会报错的整数写入操作
        test_data = 200  # 模拟状态码或整数数据
        
        # 执行修复后的写入函数
        result = safe_write_to_file(temp_file, test_data)
        
        # 验证文件内容
        with open(temp_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 断言验证
        assert result == True, "写入函数应返回 True"
        assert content == '200', f"文件内容应为字符串 '200'，实际为 {content}"
        assert isinstance(content, str), "读取的内容必须是字符串"
        
        print("测试通过：整数已成功转换为字符串并写入文件")
        return True
        
    except Exception as e:
        print(f"测试失败：{e}")
        return False
    finally:
        # 清理临时文件
        if os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == '__main__':
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
