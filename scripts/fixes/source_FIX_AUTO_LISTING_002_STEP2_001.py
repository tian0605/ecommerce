import sys
import os
import subprocess

def safe_import_collector_scraper():
    """
    安全导入collector_scraper模块，自动处理路径缺失、未安装等常见问题
    返回导入成功的模块对象，导入失败抛出明确提示
    """
    # 补充常用路径到Python搜索路径，解决自定义模块路径找不到的问题
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    work_dir = os.getcwd()
    for add_path in [script_dir, parent_dir, work_dir]:
        if add_path not in sys.path:
            sys.path.insert(0, add_path)
    
    # 第一次尝试导入
    try:
        import collector_scraper
        return collector_scraper
    except ModuleNotFoundError:
        # 导入失败尝试pip安装（第三方包名通常横线分隔，导入名下划线分隔）
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "collector-scraper"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            import collector_scraper
            return collector_scraper
        except Exception as e:
            raise RuntimeError(
                "无法导入collector_scraper模块，请按以下步骤排查：\n"
                "1. 检查模块名称是否拼写错误\n"
                "2. 自定义模块请确认文件是否存在于搜索路径中\n"
                "3. 第三方模块请手动执行pip install collector-scraper安装"
            ) from e

# 测试验证
def test_import():
    try:
        scraper_module = safe_import_collector_scraper()
        print(f"✅ 导入成功，模块路径: {getattr(scraper_module, '__file__', '内置模块')}")
        return True
    except RuntimeError as e:
        print(f"⚠️ 导入提示: {e}")
        return False

if __name__ == "__main__":
    test_import()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
