import asyncio
from typing import Optional
from playwright.async_api import Page, Locator

async def find_product_edit_button(page: Page, product_id: str, timeout: int = 10000) -> Optional[Locator]:
    """
    修复商品编辑按钮查找逻辑
    优化选择器以正确匹配目标商品行内的编辑按钮
    
    参数:
        page: Playwright Page 对象
        product_id: 商品 ID
        timeout: 超时时间（毫秒）
    
    返回:
        编辑按钮的 Locator 对象，未找到返回 None
    """
    try:
        # 方案1：先定位商品行，再在行内查找编辑按钮（推荐）
        # 假设商品行包含 product_id，根据实际情况调整选择器
        product_row = page.locator(
            f'tr:has-text("{product_id}"), div:has-text("{product_id}"), .product-row:has-text("{product_id}")'
        ).first
        
        # 等待商品行加载
        await product_row.wait_for(state='visible', timeout=timeout)
        
        # 在商品行内查找编辑按钮，使用多种选择器备选
        edit_button_selectors = [
            'button:has-text("编辑")',
            'button:has-text("编辑 ")',
            'button:has-text(" 编辑")',
            'a:has-text("编辑")',
            'span:has-text("编辑")',
            '[data-action="edit"]',
            '.edit-btn',
            '.btn-edit'
        ]
        
        for selector in edit_button_selectors:
            try:
                edit_btn = product_row.locator(selector).first
                await edit_btn.wait_for(state='visible', timeout=2000)
                return edit_btn
            except:
                continue
        
        # 方案2：如果方案1失败，尝试全局查找并验证所属商品行
        edit_buttons = page.locator('button:has-text("编辑")')
        count = await edit_buttons.count()
        
        for i in range(count):
            btn = edit_buttons.nth(i)
            # 获取按钮所在行的文本，验证是否包含目标商品 ID
            parent_row = btn.locator('xpath=ancestor::tr | ancestor::div[contains(@class, "row")] | ancestor::div[contains(@class, "product")]').first
            try:
                row_text = await parent_row.inner_text(timeout=2000)
                if product_id in row_text:
                    await btn.wait_for(state='visible', timeout=2000)
                    return btn
            except:
                continue
        
        return None
        
    except Exception as e:
        print(f"查找编辑按钮失败: {str(e)}")
        return None


async def click_product_edit_button(page: Page, product_id: str, timeout: int = 10000) -> bool:
    """
    点击商品编辑按钮的完整流程
    
    参数:
        page: Playwright Page 对象
        product_id: 商品 ID
        timeout: 超时时间（毫秒）
    
    返回:
        是否成功点击
    """
    edit_btn = await find_product_edit_button(page, product_id, timeout)
    
    if edit_btn is None:
        print(f"错误：未找到商品 {product_id} 的编辑按钮")
        return False
    
    try:
        # 滚动到视图并点击
        await edit_btn.scroll_into_view_if_needed()
        await edit_btn.click()
        print(f"成功点击商品 {product_id} 的编辑按钮")
        return True
    except Exception as e:
        print(f"点击编辑按钮失败: {str(e)}")
        return False


# 测试验证代码
async def test_fix():
    """测试修复代码"""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 模拟商品列表页面
        await page.set_content('''
        <html>
        <body>
            <table>
                <tr class="product-row">
                    <td class="product-id">1031400982378</td>
                    <td class="product-name">测试商品</td>
                    <td><button>编辑</button></td>
                </tr>
                <tr class="product-row">
                    <td class="product-id">1031400982379</td>
                    <td class="product-name">测试商品 2</td>
                    <td><button>编辑</button></td>
                </tr>
            </table>
        </body>
        </html>
        ''')
        
        # 测试查找编辑按钮
        product_id = "1031400982378"
        edit_btn = await find_product_edit_button(page, product_id)
        
        await browser.close()
        
        if edit_btn is not None:
            print(f"✓ 测试通过：成功找到商品 {product_id} 的编辑按钮")
            return True
        else:
            print(f"✗ 测试失败：未找到商品 {product_id} 的编辑按钮")
            return False


# 直接运行测试
if __name__ == "__main__":
    result = asyncio.run(test_fix())
    print(f"测试结果：{'成功' if result else '失败'}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
