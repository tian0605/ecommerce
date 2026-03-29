import os

def safe_file_write(filepath, content, mode='w', encoding='utf-8'):
    """
    安全文件写入函数，自动处理类型转换
    修复 write() argument must be str, not int 错误
    """
    # 确保目录存在
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    # 类型转换：确保写入内容是字符串
    if isinstance(content, (int, float)):
        content = str(content)
    elif isinstance(content, (dict, list)):
        import json
        content = json.dumps(content, ensure_ascii=False, indent=2)
    elif isinstance(content, bytes):
        content = content.decode(encoding)
    
    # 执行写入
    with open(filepath, mode, encoding=encoding) as f:
        f.write(content)
    
    return True

def write_log_entry(log_file, message, level='INFO'):
    """
    写入日志条目，自动处理类型转换
    """
    import datetime
    
    # 确保消息是字符串
    if not isinstance(message, str):
        message = str(message)
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_entry)
    
    return True

def write_data_record(filepath, record_id, data):
    """
    写入数据记录，修复整数ID写入错误
    """
    # 确保record_id转换为字符串
    record_id = str(record_id) if not isinstance(record_id, str) else record_id
    
    # 确保data是字符串格式
    if isinstance(data, (dict, list)):
        import json
        data_str = json.dumps(data, ensure_ascii=False)
    else:
        data_str = str(data)
    
    line = f"{record_id}|{data_str}\n"
    
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(line)
    
    return True

# 测试验证
def test_fix():
    """测试修复代码是否正确处理类型转换"""
    import tempfile
    import os
    
    # 创建临时文件
    temp_file = tempfile.mktemp(suffix='.txt')
    
    try:
        # 测试1：写入整数
        result1 = safe_file_write(temp_file, 12345)
        assert result1 == True
        
        # 验证内容
        with open(temp_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == '12345'
        
        # 测试2：写入字典
        result2 = safe_file_write(temp_file, {'key': 'value'})
        assert result2 == True
        
        # 测试3：写入日志
        log_file = tempfile.mktemp(suffix='.log')
        result3 = write_log_entry(log_file, 999, 'ERROR')
        assert result3 == True
        
        # 测试4：写入数据记录
        data_file = tempfile.mktemp(suffix='.dat')
        result4 = write_data_record(data_file, 1001, {'status': 'success'})
        assert result4 == True
        
        # 清理临时文件
        for f in [temp_file, log_file, data_file]:
            if os.path.exists(f):
                os.remove(f)
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        return False

if __name__ == '__main__':
    # 运行测试
    success = test_fix()
    print(f"修复验证: {'通过' if success else '失败'}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
