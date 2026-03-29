import os

def safe_file_write(filepath, content):
    """
    安全文件写入函数，自动处理类型转换
    修复 write() argument must be str, not int 错误
    """
    # 确保内容转换为字符串
    if not isinstance(content, str):
        content = str(content)
    
    # 确保目录存在
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    # 写入文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True

def write_data_to_file(filepath, data):
    """
    写入数据到文件，支持多种数据类型
    电商运营数据持久化专用函数
    """
    # 处理不同类型的数据
    if isinstance(data, (int, float)):
        content = str(data)
    elif isinstance(data, (list, dict)):
        import json
        content = json.dumps(data, ensure_ascii=False, indent=2)
    elif isinstance(data, str):
        content = data
    else:
        content = str(data)
    
    # 使用安全写入函数
    return safe_file_write(filepath, content)

# 测试验证
def test_fix():
    """测试修复代码是否正常工作"""
    import tempfile
    
    # 测试整数写入
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
        tmp_path = tmp.name
    
    try:
        # 测试场景1: 直接写入整数（原错误场景）
        result1 = safe_file_write(tmp_path, 12345)
        assert result1 == True
        
        # 验证文件内容
        with open(tmp_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == "12345"
        
        # 测试场景2: 写入字符串
        result2 = safe_file_write(tmp_path, "test string")
        assert result2 == True
        
        # 测试场景3: 写入字典
        result3 = write_data_to_file(tmp_path, {"order_id": 1001, "status": "success"})
        assert result3 == True
        
        # 测试场景4: 写入列表
        result4 = write_data_to_file(tmp_path, [1, 2, 3, 4, 5])
        assert result4 == True
        
        print("所有测试通过！")
        return True
        
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
