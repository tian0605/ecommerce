import os

def safe_write_file(file_path, content):
    """
    修复 write() 参数类型错误，确保内容转换为字符串后写入文件
    :param file_path: 文件路径
    :param content: 写入内容（支持 int 或 str）
    :return: 是否写入成功
    """
    try:
        # 核心修复：确保写入内容必须是字符串，防止 TypeError
        if not isinstance(content, str):
            content = str(content)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"写入失败：{e}")
        return False

def test_fix():
    """测试修复函数是否能正确处理整数输入"""
    test_file = "test_fix_output.txt"
    try:
        # 测试场景 1: 传入整数（复现原错误场景）
        success = safe_write_file(test_file, 10086)
        assert success == True, "写入应成功"
        
        # 验证文件内容是否为字符串形式的整数
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == "10086", f"内容应为 '10086', 实际为 {content}"
            
        # 测试场景 2: 传入字符串（确保不影响正常流程）
        success = safe_write_file(test_file, "hello world")
        assert success == True
        
        with open(test_file, 'r', encoding='utf-8') as f:
            assert f.read() == "hello world"
            
        print("所有测试通过")
        return True
    except AssertionError as e:
        print(f"测试失败：{e}")
        return False
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)

if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
