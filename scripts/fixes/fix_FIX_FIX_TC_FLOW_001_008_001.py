import os

def safe_write_to_file(file_path, data):
    """
    安全写入文件，自动处理数据类型转换，避免 write() argument must be str, not int 错误
    :param file_path: 文件路径
    :param data: 待写入的数据（支持 int, str 等类型）
    :return: 写入是否成功
    """
    try:
        # 核心修复：确保写入前数据转换为字符串
        if not isinstance(data, str):
            data = str(data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"写入失败：{e}")
        return False

def test_fix():
    """测试修复代码是否有效"""
    test_file = "test_fix_output.txt"
    
    # 测试场景：传入整数（原本会报错 write() argument must be str, not int）
    success = safe_write_to_file(test_file, 10086)
    assert success == True, "写入操作应成功"
    
    # 验证文件内容是否正确转换为字符串
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert content == "10086", f"文件内容应为字符串 '10086', 实际为 {content}"
    
    # 清理测试文件
    if os.path.exists(test_file):
        os.remove(test_file)
        
    print("测试通过：整数写入已自动转换为字符串")
    return True

if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
