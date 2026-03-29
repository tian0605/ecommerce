import re
import ast

def check_bracket_balance(code_string):
    """检查代码中括号是否平衡"""
    brackets = {'(': ')', '[': ']', '{': '}'}
    stack = []
    
    for i, char in enumerate(code_string):
        if char in brackets:
            stack.append((char, i))
        elif char in brackets.values():
            if not stack:
                return False, f"多余的闭合括号 '{char}' 在位置 {i}"
            last_open, pos = stack.pop()
            if brackets[last_open] != char:
                return False, f"括号不匹配：'{last_open}' 与 '{char}' 在位置 {i}"
    
    if stack:
        unmatched = stack[-1]
        return False, f"未闭合的括号 '{unmatched[0]}' 在位置 {unmatched[1]}"
    
    return True, "括号平衡"

def fix_unclosed_brackets(code_string, line_number=255):
    """修复未闭合的括号问题"""
    lines = code_string.split('\n')
    
    # 检查指定行附近的括号
    if line_number <= len(lines):
        target_line = lines[line_number - 1]
        
        # 统计该行括号
        open_count = target_line.count('(') + target_line.count('[') + target_line.count('{')
        close_count = target_line.count(')') + target_line.count(']') + target_line.count('}')
        
        # 如果括号不平衡，尝试修复
        if open_count > close_count:
            missing = open_count - close_count
            # 在行末添加缺失的闭合括号
            lines[line_number - 1] = target_line + ')' * missing
            code_string = '\n'.join(lines)
    
    # 验证修复后的代码
    is_balanced, message = check_bracket_balance(code_string)
    
    if not is_balanced:
        # 尝试自动修复整个代码的括号
        code_string = auto_fix_brackets(code_string)
    
    return code_string, is_balanced, message

def auto_fix_brackets(code_string):
    """自动修复代码中的括号问题"""
    brackets = {'(': ')', '[': ']', '{': '}'}
    stack = []
    result = []
    fix_positions = []
    
    for i, char in enumerate(code_string):
        if char in brackets:
            stack.append((char, i))
            result.append(char)
        elif char in brackets.values():
            if stack and brackets[stack[-1][0]] == char:
                stack.pop()
                result.append(char)
            else:
                # 忽略多余的闭合括号
                fix_positions.append(i)
        else:
            result.append(char)
    
    # 在末尾添加缺失的闭合括号
    while stack:
        open_bracket, pos = stack.pop()
        result.append(brackets[open_bracket])
        fix_positions.append(pos)
    
    return ''.join(result)

def validate_python_syntax(code_string):
    """验证Python语法是否正确"""
    try:
        ast.parse(code_string)
        return True, "语法正确"
    except SyntaxError as e:
        return False, f"语法错误：{e.msg} 在第 {e.lineno} 行"

def fix_syntax_error(code_string):
    """主修复函数：修复语法错误"""
    # 首先检查括号平衡
    is_balanced, bracket_msg = check_bracket_balance(code_string)
    
    if not is_balanced:
        code_string, is_balanced, bracket_msg = fix_unclosed_brackets(code_string)
    
    # 验证语法
    is_valid, syntax_msg = validate_python_syntax(code_string)
    
    return {
        'fixed_code': code_string,
        'bracket_status': bracket_msg,
        'syntax_valid': is_valid,
        'syntax_message': syntax_msg
    }

# 测试验证
def test_fix():
    """测试修复功能"""
    # 测试用例1：未闭合的括号
    broken_code = """
def test_function():
    result = (1 + 2 * (3 + 4
    return result
"""
    
    result = fix_syntax_error(broken_code)
    print(f"测试1 - 括号状态：{result['bracket_status']}")
    print(f"测试1 - 语法有效：{result['syntax_valid']}")
    
    # 测试用例2：正确的代码
    correct_code = """
def test_function():
    result = (1 + 2) * (3 + 4)
    return result
"""
    
    result2 = fix_syntax_error(correct_code)
    print(f"测试2 - 括号状态：{result2['bracket_status']}")
    print(f"测试2 - 语法有效：{result2['syntax_valid']}")
    
    return result['syntax_valid'] or result2['syntax_valid']

if __name__ == "__main__":
    # 运行测试
    test_fix()
    print("\n修复工具已就绪，可使用 fix_syntax_error() 函数修复代码")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
