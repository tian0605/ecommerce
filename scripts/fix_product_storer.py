#!/usr/bin/env python3
"""修复 ProductStorer 接口问题"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/skills')

def main():
    print("开始修复 ProductStorer 接口...")
    
    # 检查 ProductStorer 类的正确方法名
    try:
        from product_storer.storer import ProductStorer
        storer = ProductStorer()
        
        # 检查可用方法
        methods = [m for m in dir(storer) if not m.startswith('_')]
        print(f"可用方法: {methods}")
        
        # 查找可能是save_product的方法
        for m in methods:
            if 'save' in m.lower() or 'add' in m.lower() or 'insert' in m.lower() or 'create' in m.lower():
                print(f"  可能的方法: {m}")
        
        return True
    except Exception as e:
        print(f"导入失败: {e}")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
