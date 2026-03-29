import os

def safe_file_write(filepath, content):
    """
    安全文件写入函数，自动处理类型转换
    修复 write() argument must be str, not int 错误
    """
    # 确保内容转换为字符串类型
    if not isinstance(content, str):
        content = str(content)
    
    # 确保目录存在
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    # 执行写入操作
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True

def safe_file_write_lines(filepath, lines):
    """
    安全写入多行内容，自动处理类型转换
    """
    # 确保目录存在
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        for line in lines:
            # 每行都转换为字符串
            if not isinstance(line, str):
                line = str(line)
            # 确保每行有换行符
            if not line.endswith('\n'):
                line += '\n'
            f.write(line)
    
    return True

def fix_write_argument(value):
    """
    修复写入参数的类型转换工具函数
    """
    if value is None:
        return ''
    return str(value)

# 测试验证
def test_fix():
    import tempfile
    
    # 测试1: 整数写入
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
        tmp_path = tmp.name
    
    try:
        # 测试整数写入
        result = safe_file_write(tmp_path, 12345)
        assert result == True
        
        with open(tmp_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == '12345'
        
        # 测试混合类型写入
        safe_file_write_lines(tmp_path, [1, 'hello', 3.14, None])
        with open(tmp_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        assert lines[0].strip() == '1'
        assert lines[1].strip() == 'hello'
        assert lines[2].strip() == '3.14'
        assert lines[3].strip() == ''
        
        # 测试类型转换函数
        assert fix_write_argument(100) == '100'
        assert fix_write_argument(None) == ''
        assert fix_write_argument('test') == 'test'
        
        return True
    finally:
        # 清理测试文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == '__main__':
    success = test_fix()
    print(f"测试通过: {success}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
