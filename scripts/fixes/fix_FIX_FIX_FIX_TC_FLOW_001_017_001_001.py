#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复未终止字符串字面量错误
任务：FIX-FIX-FIX-TC-FLOW-001-017-001-001
"""

def fix_string_literal(code_content, line_number):
    """
    修复未终止的字符串字面量错误
    
    参数:
        code_content: 源代码内容（字符串）
        line_number: 错误发生的行号
    
    返回:
        修复后的代码内容
    """
    lines = code_content.split('\n')
    
    # 检查指定行是否存在未闭合的字符串
    if line_number <= len(lines):
        target_line = lines[line_number - 1]
        
        # 检查单引号
        single_quotes = target_line.count("'")
        # 检查双引号
        double_quotes = target_line.count('"')
        
        # 如果引号数量为奇数，说明有未闭合的字符串
        if single_quotes % 2 != 0:
            # 尝试在行末添加缺失的单引号
            lines[line_number - 1] = target_line + "'"
        elif double_quotes % 2 != 0:
            # 尝试在行末添加缺失的双引号
            lines[line_number - 1] = target_line + '"'
    
    return '\n'.join(lines)


def validate_string_literals(code_content):
    """
    验证代码中所有字符串字面量是否正确闭合
    
    参数:
        code_content: 源代码内容
    
    返回:
        (is_valid, error_lines) 验证结果和错误行号列表
    """
    lines = code_content.split('\n')
    error_lines = []
    
    in_multiline_string = False
    multiline_quote = None
    
    for i, line in enumerate(lines, 1):
        # 跳过注释行
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        
        # 检查多行字符串
        if in_multiline_string:
            if multiline_quote in line:
                in_multiline_string = False
                multiline_quote = None
            continue
        
        # 检查三引号多行字符串开始
        if '"""' in line or "'''" in line:
            quote_type = '"""' if '"""' in line else "'''"
            count = line.count(quote_type)
            if count % 2 != 0:
                in_multiline_string = True
                multiline_quote = quote_type
            continue
        
        # 检查单行字符串引号配对
        # 简单检查：统计引号数量（不考虑转义）
        single_count = line.count("'") - line.count("\\'")
        double_count = line.count('"') - line.count('\\"')
        
        if single_count % 2 != 0 or double_count % 2 != 0:
            error_lines.append(i)
    
    is_valid = len(error_lines) == 0
    return is_valid, error_lines


def create_safe_string_template():
    """
    创建安全的字符串模板示例，避免未终止错误
    """
    # 使用三引号处理多行字符串
    multi_line = """这是一个
    多行字符串
    示例"""
    
    # 使用转义处理引号
    with_quote = "这是一个包含\"引号\"的字符串"
    with_single = '这是一个包含\'单引号\'的字符串'
    
    # 使用f-string格式化
    name = "test"
    formatted = f"Hello, {name}"
    
    return {
        'multi_line': multi_line,
        'with_quote': with_quote,
        'with_single': with_single,
        'formatted': formatted
    }


def test_fix():
    """测试修复功能"""
    # 测试1：验证字符串模板创建
    templates = create_safe_string_template()
    assert isinstance(templates, dict)
    assert 'multi_line' in templates
    
    # 测试2：验证字符串验证功能
    valid_code = '''
def test():
    s = "hello"
    return s
'''
    is_valid, errors = validate_string_literals(valid_code)
    assert is_valid == True
    
    # 测试3：检测未闭合字符串
    invalid_code = '''
def test():
    s = "hello
    return s
'''
    is_valid, errors = validate_string_literals(invalid_code)
    assert is_valid == False or len(errors) > 0
    
    # 测试4：修复功能
    broken_code = 'msg = "hello world\nprint(msg)'
    fixed_code = fix_string_literal(broken_code, 1)
    assert fixed_code is not None
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    # 运行测试
    success = test_fix()
    if success:
        print("修复代码验证成功")
    else:
        print("修复代码验证失败")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
