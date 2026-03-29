import os
import tempfile

def safe_file_write(file_path, content):
    """
    安全写入文件工具函数
    修复 write() argument must be str, not int 错误
    自动将非字符串内容转换为字符串后再写入
    """
    # 核心修复：确保内容转换为字符串，避免类型错误
    if not isinstance(content, str):
        content = str(content)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"文件写入失败：{e}")
        return False

def test_fix():
    """测试验证修复代码是否有效"""
    # 创建临时文件路径
    test_file = tempfile.mktemp(suffix=".txt")
    
    try:
        # 测试场景：传入整数（原本会报错的场景）
        success = safe_file_write(test_file, 10086)
        
        if not success:
            return False
            
        # 验证文件内容是否正确转换为字符串写入
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
            
        # 断言内容是否为字符串形式的整数
        return content == "10086"
    except Exception as e:
        print(f"测试执行异常：{e}")
        return False

if __name__ == "__main__":
    # 独立运行测试
    result = test_fix()
    print(f"修复验证结果：{'通过' if result else '失败'}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
