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
    elif not isinstance(content, str):
        content = str(content)
    
    # 执行写入操作
    with open(filepath, mode, encoding=encoding) as f:
        f.write(content)
    
    return True

def write_log_entry(log_file, message, level='INFO'):
    """
    写入日志条目，自动处理各种数据类型
    """
    import datetime
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    
    return safe_file_write(log_file, log_entry, mode='a')

def write_data_record(filepath, record_id, data_dict):
    """
    写入数据记录，修复整数ID写入错误
    """
    # 将整数record_id转换为字符串
    record_id = str(record_id)
    
    # 构建记录内容
    import json
    content = {
        'id': record_id,
        'data': data_dict,
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }
    
    return safe_file_write(filepath, json.dumps(content, ensure_ascii=False) + '\n', mode='a')

# 测试验证
def test_fix():
    """测试修复代码是否正常工作"""
    import tempfile
    import os
    
    # 创建临时文件
    temp_file = tempfile.mktemp(suffix='.txt')
    
    try:
        # 测试1：写入整数
        result1 = safe_file_write(temp_file, 12345)
        assert result1 == True
        
        # 验证文件内容
        with open(temp_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == '12345'
        
        # 测试2：写入日志
        log_file = tempfile.mktemp(suffix='.log')
        result2 = write_log_entry(log_file, '测试消息', 'INFO')
        assert result2 == True
        
        # 测试3：写入数据记录（整数ID）
        data_file = tempfile.mktemp(suffix='.json')
        result3 = write_data_record(data_file, 1001, {'product': 'test'})
        assert result3 == True
        
        # 清理临时文件
        for f in [temp_file, log_file, data_file]:
            if os.path.exists(f):
                os.remove(f)
        
        return True
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        return False

if __name__ == '__main__':
    # 运行测试
    success = test_fix()
    print(f"修复验证: {'成功' if success else '失败'}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
