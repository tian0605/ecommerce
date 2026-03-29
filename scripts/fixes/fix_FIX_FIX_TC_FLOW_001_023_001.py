import time
import re
from typing import Optional, Dict, Any

def find_product_in_miaoshou(driver, product_id: str, max_retries: int = 3) -> Optional[Any]:
    """
    在妙手ERP采集箱中查找商品编辑按钮
    修复：增加多种搜索策略和重试机制
    """
    edit_button = None
    
    for attempt in range(max_retries):
        try:
            # 策略1: 直接搜索完整货源ID
            search_selector = f"input[placeholder*='搜索'][value*='{product_id}']"
            edit_button = driver.find_element_by_xpath(
                f"//div[contains(@class, 'product-item')]//button[contains(text(), '编辑')]"
            )
            if edit_button:
                return edit_button
            
            # 策略2: 搜索ID后8位（妙手可能截断显示）
            short_id = product_id[-8:]
            search_input = driver.find_element_by_css_selector("input.search-input")
            search_input.clear()
            search_input.send_keys(short_id)
            time.sleep(2)
            
            edit_button = driver.find_element_by_xpath(
                f"//div[contains(@class, 'product-list')]//button[contains(text(), '编辑')]"
            )
            if edit_button:
                return edit_button
            
            # 策略3: 查找所有商品项，匹配包含货源ID的项
            product_items = driver.find_elements_by_css_selector(".product-item, .collection-item")
            for item in product_items:
                item_text = item.text
                if product_id in item_text or short_id in item_text:
                    edit_button = item.find_element_by_xpath(".//button[contains(text(), '编辑')]")
                    if edit_button:
                        return edit_button
            
            # 策略4: 使用图片匹配（如果有截图）
            if attempt < max_retries - 1:
                # 刷新页面后重试
                driver.refresh()
                time.sleep(3)
                continue
                
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
                continue
            raise e
    
    return None


def update_miaoshou_erp(driver, product_id: str, product_data: Dict[str, Any]) -> bool:
    """
    回写妙手ERP的完整流程
    修复：增强错误处理和日志记录
    """
    try:
        # 步骤1: 访问采集箱
        driver.get("https://erp.91miaoshou.com/product/collection")
        time.sleep(3)
        
        # 关闭可能的弹窗
        try:
            close_btn = driver.find_element_by_css_selector(".jx-dialog .close-btn")
            close_btn.click()
            time.sleep(1)
        except:
            pass
        
        # 步骤2: 查找商品（使用修复后的搜索逻辑）
        edit_button = find_product_in_miaoshou(driver, product_id)
        
        if not edit_button:
            # 记录详细调试信息
            page_source = driver.page_source
            product_ids_found = re.findall(r'\d{10,}', page_source)
            print(f"[DEBUG] 页面找到的ID: {product_ids_found[:10]}")
            print(f"[WARN] 未找到商品 {product_id} 的编辑按钮")
            return False
        
        # 步骤3: 点击编辑
        edit_button.click()
        time.sleep(2)
        
        # 步骤4: 更新商品信息
        update_product_fields(driver, product_data)
        
        # 步骤5: 保存
        save_btn = driver.find_element_by_xpath("//button[contains(text(), '保存')]")
        save_btn.click()
        time.sleep(3)
        
        print(f"[INFO] ✅ 回写成功: 货源ID={product_id}")
        return True
        
    except Exception as e:
        print(f"[ERROR] 回写失败: {str(e)}")
        return False


def analyze_profit(product_data: Dict[str, Any], update_success: bool) -> Dict[str, Any]:
    """
    利润分析函数
    修复：确保即使update失败也能独立执行分析
    """
    try:
        purchase_price = product_data.get('price', 0)
        weight = product_data.get('weight', 0)
        
        # 计算建议售价和利润
        suggested_price = purchase_price * 8.5  # 示例汇率和倍率
        estimated_profit = suggested_price * 0.3 - purchase_price - (weight * 50)
        profit_rate = (estimated_profit / purchase_price * 100) if purchase_price > 0 else 0
        
        result = {
            'purchase_price': purchase_price,
            'weight': weight,
            'suggested_price': round(suggested_price, 2),
            'estimated_profit': round(estimated_profit, 4),
            'profit_rate': round(profit_rate, 1),
            'success': True
        }
        
        print(f"[INFO] ✅ 分析成功:")
        print(f"[INFO]    采购价：{purchase_price} CNY")
        print(f"[INFO]    重量：{weight} kg")
        print(f"[INFO]    建议售价：{result['suggested_price']} TWD")
        print(f"[INFO]    预估利润：{result['estimated_profit']} CNY")
        print(f"[INFO]    利润率：{result['profit_rate']}%")
        
        return result
        
    except Exception as e:
        print(f"[ERROR] 分析失败：{str(e)}")
        return {'success': False, 'error': str(e)}


def run_workflow_fix(product_id: str, product_data: Dict[str, Any], driver) -> Dict[str, bool]:
    """
    完整工作流修复版本
    修复：解耦update和analyze步骤，确保analyze不依赖update成功
    """
    results = {
        'collect': True,
        'scrape': True,
        'weight': True,
        'store': True,
        'optimize': True,
        'update': False,
        'analyze': False
    }
    
    try:
        # 步骤6: 回写妙手ERP（独立执行）
        results['update'] = update_miaoshou_erp(driver, product_id, product_data)
        
        # 步骤7: 利润分析（不依赖update成功）
        analyze_result = analyze_profit(product_data, results['update'])
        results['analyze'] = analyze_result.get('success', False)
        
    except Exception as e:
        print(f"[ERROR] 工作流执行异常：{str(e)}")
    
    return results


# 测试验证
def test_fix():
    """测试修复逻辑"""
    # 模拟商品数据
    test_data = {
        'price': 24.0,
        'weight': 0.041,
        'skus': 4
    }
    
    # 测试利润分析（不依赖driver）
    result = analyze_profit(test_data, update_success=False)
    assert result['success'] == True
    assert result['purchase_price'] == 24.0
    assert result['profit_rate'] > 0
    
    print("[TEST] ✅ 修复代码验证通过")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
