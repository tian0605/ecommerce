import time
import random
from typing import Callable, Any, Optional

# 模拟自动化驱动中的元素找不到异常
class ElementNotFoundException(Exception):
    pass

# 模拟自动化驱动中的元素不可交互异常
class ElementNotInteractableException(Exception):
    pass

def robust_ui_write_back(
    find_element_func: Callable, 
    action_func: Callable, 
    max_retries: int = 5, 
    base_wait: float = 1.0
) -> bool:
    """
    稳健的 UI 回写操作函数
    修复了因页面加载未完成导致的选择器失败问题
    """
    for attempt in range(1, max_retries + 1):
        try:
            # 1. 尝试查找元素
            element = find_element_func()
            
            # 2. 执行操作（如输入、点击）
            action_func(element)
            
            print(f"[成功] 第 {attempt} 次尝试回写成功")
            return True
            
        except (ElementNotFoundException, ElementNotInteractableException) as e:
            if attempt == max_retries:
                print(f"[失败] 达到最大重试次数 {max_retries}，最后一次错误：{str(e)}")
                return False
            
            # 3. 指数退避等待，给页面加载留出时间
            wait_time = base_wait * (1 + random.random()) * attempt
            print(f"[等待] 第 {attempt} 次失败，等待 {wait_time:.2f} 秒后重试...")
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"[错误] 发生未知错误：{str(e)}")
            return False
    
    return False

# --- 测试验证部分 (模拟真实场景) ---

class MockElement:
    def __init__(self):
        self.value = ""
    def send_keys(self, text):
        self.value = text

class MockDriver:
    def __init__(self):
        self.page_loaded = False
        self.load_delay = 2  # 模拟页面加载需要 2 秒
    
    def simulate_page_load(self):
        """模拟页面异步加载过程"""
        time.sleep(self.load_delay)
        self.page_loaded = True
    
    def find_element(self, selector):
        if not self.page_loaded:
            raise ElementNotFoundException(f"Selector '{selector}' not found yet")
        return MockElement()

def test_fix():
    """测试修复逻辑是否有效"""
    print("--- 开始测试 UI 回写修复逻辑 ---")
    
    driver = MockDriver()
    selector = "input#stock_price"
    
    # 启动后台线程模拟页面加载
    import threading
    load_thread = threading.Thread(target=driver.simulate_page_load)
    load_thread.start()
    
    # 定义查找和操作闭包
    def find_action():
        return driver.find_element(selector)
    
    def write_action(el):
        el.send_keys("99.00")
    
    # 执行修复后的函数
    start_time = time.time()
    success = robust_ui_write_back(find_action, write_action, max_retries=5, base_wait=0.5)
    elapsed = time.time() - start_time
    
    load_thread.join()
    
    # 验证结果
    assert success == True, "回写操作应该成功"
    assert elapsed >= driver.load_delay, "应该等待了页面加载时间"
    print(f"--- 测试通过，总耗时 {elapsed:.2f} 秒 ---")
    return True

if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
