from functools import wraps

def create_fixed_decorator():
    """
    创建一个正确使用 wraps 的装饰器，修复 name 'wraps' is not defined 错误
    """
    def decorator(func):
        @wraps(func)  # 确保 wraps 已从上方的 functools 导入
        def wrapper(*args, **kwargs):
            """Wrapper function"""
            return func(*args, **kwargs)
        return wrapper
    return decorator

def test_wraps_fix():
    """
    测试修复后的装饰器是否能正确保留函数元数据
    """
    my_decorator = create_fixed_decorator()
    
    @my_decorator
    def original_function():
        """Original docstring"""
        pass
    
    # 验证函数名和文档字符串是否被正确保留
    assert original_function.__name__ == 'original_function', "函数名未保留"
    assert original_function.__doc__ == 'Original docstring', "文档字符串未保留"
    
    return True

if __name__ == '__main__':
    try:
        result = test_wraps_fix()
        print(f"修复验证成功: {result}")
    except Exception as e:
        print(f"修复验证失败: {e}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
