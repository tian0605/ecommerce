import os
import tempfile

def safe_write_to_file(file_path, data):
    """
    安全写入数据到文件，自动修复 write() 参数类型错误
    确保传入的数据在写入前被转换为字符串
    """
    # 核心修复：强制将数据转换为字符串，避免 TypeError
    if not isinstance(data, str):
        data = str(data)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(data)
    return True

def test_fix():
    """测试验证修复代码是否能正确处理整数写入"""
    # 创建临时文件用于测试
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
        tmp_path = tmp.name
    
    try:
        # 测试场景：传入整数（原本会报错 write() argument must be str, not int）
        test_data = 10086
        result = safe_write_to_file(tmp_path, test_data)
        
        # 验证写入结果
        assert result is True, "写入函数返回失败"
        
        with open(tmp_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == "10086", f"内容不匹配：{content}"
            assert isinstance(content, str), "文件内容不是字符串"
            
        return True
    except Exception as e:
        print(f"Test failed: {e}")
        return False
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    print("Verification Result:", test_fix())
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
