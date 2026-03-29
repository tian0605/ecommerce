import sys
import os
import tempfile
import shutil
import importlib

def setup_workflow_path(base_dir):
    """
    修复路径配置：将包含技能模块的目录显式添加到 sys.path
    """
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"模块目录不存在：{base_dir}")
    
    # 确保路径不在 sys.path 中重复添加
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    
    return True

def load_workflow_modules():
    """
    修复导入逻辑：移除静默失败的 try/except，显式导入并验证
    """
    try:
        # 假设模块结构为 ListingOptimizer.MiaoshouUpdater.ProfitAnalyzer
        # 这里使用 importlib 确保动态加载的可靠性，也可以直接用 import 语句
        from ListingOptimizer.MiaoshouUpdater import ProfitAnalyzer
        return ProfitAnalyzer
    except ImportError as e:
        # 关键修复：不再静默捕获，而是抛出明确错误以便调试
        raise ImportError(f"工作流模块加载失败，请检查路径配置：{str(e)}")

def create_mock_modules(temp_dir):
    """
    测试辅助：创建模拟的模块结构以验证修复逻辑
    """
    skills_dir = os.path.join(temp_dir, 'skills')
    optimizer_dir = os.path.join(skills_dir, 'ListingOptimizer')
    
    os.makedirs(optimizer_dir)
    
    # 创建 __init__.py
    with open(os.path.join(skills_dir, '__init__.py'), 'w') as f:
        f.write("")
    with open(os.path.join(optimizer_dir, '__init__.py'), 'w') as f:
        f.write("")
    
    # 创建 MiaoshouUpdater.py 并定义 ProfitAnalyzer
    updater_path = os.path.join(optimizer_dir, 'MiaoshouUpdater.py')
    with open(updater_path, 'w') as f:
        f.write("""
class ProfitAnalyzer:
    def analyze(self):
        return "Profit Analysis Successful"
""")
    
    return skills_dir

def test_fix():
    """
    验证修复代码是否有效
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # 1. 创建模拟模块结构
        skills_path = create_mock_modules(temp_dir)
        
        # 2. 执行路径修复
        setup_workflow_path(skills_path)
        
        # 3. 执行导入修复
        ProfitAnalyzer = load_workflow_modules()
        
        # 4. 验证模块可用
        instance = ProfitAnalyzer()
        result = instance.analyze()
        
        assert result == "Profit Analysis Successful", "模块功能验证失败"
        
        print("修复验证成功：模块路径配置正确且导入无误")
        return True
    except Exception as e:
        print(f"修复验证失败：{str(e)}")
        return False
    finally:
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)
        # 清理 sys.path 中添加的测试路径
        if temp_dir in sys.path:
            sys.path.remove(temp_dir)

if __name__ == "__main__":
    success = test_fix()
    sys.exit(0 if success else 1)
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
