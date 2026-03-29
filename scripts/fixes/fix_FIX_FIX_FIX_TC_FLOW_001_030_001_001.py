from functools import wraps

def safe_decorator(func):
    """
    一个使用 wraps 的正确装饰器示例
    修复了 name 'wraps' is not defined 的错误
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        """包装函数"""
        return func(*args, **kwargs)
    return wrapper

@safe_decorator
def example_function():
    """示例业务函数"""
    return "success"

def test_fix():
    """验证修复是否生效"""
    try:
        # 如果 wraps 未导入，上面定义装饰器时就会报错
        result = example_function()
        # 检查元数据是否被保留（wraps 的作用）
        assert example_function.__name__ == 'example_function'
        return True
    except NameError as e:
        if "wraps" in str(e):
            return False
        raise

if __name__ == "__main__":
    if test_fix():
        print("修复成功：wraps 已正确导入并使用")
    else:
        print("修复失败")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
