def safe_write_to_file(content, file_path='output.txt'):
    """
    修复 write() 参数类型错误，确保写入内容为字符串
    适用于电商自动化脚本中日志记录或数据导出场景
    """
    # 核心修复：确保内容转换为字符串，避免 write() 参数类型错误
    if not isinstance(content, str):
        content = str(content)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"写入失败：{e}")
        return False

def test_fix():
    """测试验证修复代码是否有效"""
    import os
    
    # 测试传入整数的情况（原本会报错的场景）
    test_file = 'test_fix_output.txt'
    result = safe_write_to_file(12345, test_file)
    assert result == True, "写入函数应返回成功"
    
    # 验证文件内容是否正确转换为字符串
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert content == "12345", f"内容应为字符串 '12345', 实际为 {content}"
    
    # 清理测试文件
    if os.path.exists(test_file):
        os.remove(test_file)
    
    return True

if __name__ == '__main__':
    if test_fix():
        print("修复验证通过：整数已成功转换为字符串并写入")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
