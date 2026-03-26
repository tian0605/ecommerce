#!/usr/bin/env python3
"""
workflow_runner.py - 自动化工作流运行器

完整流程：
1. miaoshou-collector - 采集1688商品到妙手
2. collector-scraper - 提取商品数据
3. 本地1688服务 - 获取准确重量/尺寸
4. product-storer - 数据落库
5. listing-optimizer - LLM优化
6. miaoshou-updater - 回写妙手
7. profit-analyzer - 利润分析

用法：
    python workflow_runner.py --url "https://detail.1688.com/offer/1027205078815.html"
"""
import argparse
import json
import sys
import time
from pathlib import Path

# 添加shared模块路径
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/shared')
sys.path.insert(0, '/home/ubuntu/.openclaw')

from logger import setup_logger
import db

logger = setup_logger('workflow-runner')

# 导入各模块
try:
    from skills.collector_scraper.scraper import CollectorScraper
    from skills.remote_weight_caller import fetch_weight_from_local
    from skills.product_storer.storer import ProductStorer
    from skills.listing_optimizer.optimizer import ListingOptimizer  
    from skills.miaoshou_updater.updater import MiaoshouUpdater
    from skills.profit_analyzer.analyzer import ProfitAnalyzer
except ImportError as e:
    logger.warning(f"部分模块导入失败: {e}")

class WorkflowRunner:
    """工作流运行器"""
    
    def __init__(self):
        self.collector = None
        self.scraper = None
        self.storer = None
        self.optimizer = None
        self.updater = None
        self.analyzer = None
    
    def step1_collect(self, url: str) -> dict:
        """步骤1: 妙手采集并认领"""
        logger.info("=" * 50)
        logger.info("[步骤1] 妙手采集认领")
        logger.info("=" * 50)
        
        try:
            from skills.miaoshou_collector.collector import MiaoshouCollector
            collector = MiaoshouCollector()
            collector.launch()  # 启动浏览器
            result = collector.collect(url)
            collector.close()
            
            if result.get('success'):
                logger.info("✅ 采集成功")
            else:
                logger.warning(f"⚠️ 采集返回: {result}")
            
            return result
        except Exception as e:
            logger.error(f"❌ 采集失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def step2_scrape(self) -> dict:
        """步骤2: 提取商品数据"""
        logger.info("=" * 50)
        logger.info("[步骤2] 提取商品数据")
        logger.info("=" * 50)
        
        try:
            scraper = CollectorScraper()
            scraper.launch()
            data = scraper.scrape_product(product_index=0)
            scraper.close()
            
            if data:
                logger.info(f"✅ 提取成功: 货源ID={data.get('alibaba_product_id')}")
                return {'success': True, 'data': data}
            else:
                logger.error("❌ 提取失败")
                return {'success': False, 'error': 'No data'}
        except Exception as e:
            logger.error(f"❌ 提取失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def step3_local_weight(self, alibaba_product_id: str) -> dict:
        """步骤3: 本地1688服务获取重量"""
        logger.info("=" * 50)
        logger.info("[步骤3] 本地1688服务获取重量/尺寸")
        logger.info("=" * 50)
        
        try:
            result = fetch_weight_from_local(alibaba_product_id, timeout=120)
            
            if result and result.get('success'):
                sku_count = result.get('sku_count', 0)
                logger.info(f"✅ 获取成功: {sku_count} 个SKU")
                for sku in result.get('sku_list', []):
                    logger.info(f"   - {sku.get('sku_name')}: {sku.get('weight_g')}g, {sku.get('length_cm')}x{sku.get('width_cm')}x{sku.get('height_cm')}cm")
                return {'success': True, 'data': result}
            else:
                logger.warning(f"⚠️ 获取失败: {result}")
                return {'success': False, 'error': result.get('error') if result else 'Unknown'}
        except Exception as e:
            logger.error(f"❌ 获取失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def step4_store(self, scrape_data: dict, weight_data: dict) -> dict:
        """步骤4: 数据落库"""
        logger.info("=" * 50)
        logger.info("[步骤4] 数据落库")
        logger.info("=" * 50)
        
        try:
            storer = ProductStorer()
            
            # 合并数据
            product_data = scrape_data.copy() if scrape_data else {}
            
            # 添加本地1688的重量数据
            if weight_data and weight_data.get('success'):
                product_data['local_1688_weight'] = weight_data.get('data', {})
            
            result = storer.save_product(product_data)
            
            if result.get('success'):
                logger.info(f"✅ 落库成功: 主货号={result.get('main_product_no')}")
            else:
                logger.warning(f"⚠️ 落库返回: {result}")
            
            return result
        except Exception as e:
            logger.error(f"❌ 落库失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def step5_optimize(self, product_id: str) -> dict:
        """步骤5: Listing优化"""
        logger.info("=" * 50)
        logger.info("[步骤5] Listing优化")
        logger.info("=" * 50)
        
        try:
            optimizer = ListingOptimizer()
            result = optimizer.optimize(product_id)
            
            if result.get('success'):
                logger.info(f"✅ 优化成功")
            else:
                logger.warning(f"⚠️ 优化返回: {result}")
            
            return result
        except Exception as e:
            logger.error(f"❌ 优化失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def step6_update(self, product_id: str) -> dict:
        """步骤6: 回写妙手"""
        logger.info("=" * 50)
        logger.info("[步骤6] 回写妙手ERP")
        logger.info("=" * 50)
        
        try:
            updater = MiaoshouUpdater()
            result = updater.update_product(product_id)
            
            if result.get('success'):
                logger.info(f"✅ 回写成功")
            else:
                logger.warning(f"⚠️ 回写返回: {result}")
            
            return result
        except Exception as e:
            logger.error(f"❌ 回写失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def step7_analyze(self, product_id: str, weight_g: float = None) -> dict:
        """步骤7: 利润分析"""
        logger.info("=" * 50)
        logger.info("[步骤7] 利润分析")
        logger.info("=" * 50)
        
        try:
            analyzer = ProfitAnalyzer()
            
            # 构造商品数据（包含本地1688的重量）
            product = {
                'product_id': product_id,
                'alibaba_product_id': product_id,
                'weight_g': weight_g  # 从本地1688服务获取的重量
            }
            
            result = analyzer.analyze_product(product)
            
            if result.get('status') == 'success':
                logger.info(f"✅ 分析成功:")
                logger.info(f"   采购价: {result.get('purchase_price_cny')} CNY")
                logger.info(f"   重量: {result.get('weight_kg')} kg")
                logger.info(f"   建议售价: {result.get('suggested_price_twd')} TWD")
                logger.info(f"   预估利润: {result.get('profit_cny')} CNY")
                logger.info(f"   利润率: {result.get('profit_rate')}")
            else:
                logger.warning(f"⚠️ 分析返回: {result}")
            
            return result
        except Exception as e:
            logger.error(f"❌ 分析失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_full(self, url: str) -> dict:
        """运行完整工作流"""
        logger.info("=" * 60)
        logger.info("🚀 自动化工作流开始")
        logger.info("=" * 60)
        
        results = {}
        
        # 步骤1: 采集
        r1 = self.step1_collect(url)
        results['collect'] = r1
        if not r1.get('success'):
            logger.error("采集失败，终止工作流")
            return results
        
        time.sleep(2)
        
        # 步骤2: 提取
        r2 = self.step2_scrape()
        results['scrape'] = r2
        if not r2.get('success'):
            logger.error("提取失败，终止工作流")
            return results
        
        scrape_data = r2.get('data', {})
        alibaba_id = scrape_data.get('alibaba_product_id')
        
        # 步骤3: 本地1688获取重量
        r3 = self.step3_local_weight(alibaba_id)
        results['weight'] = r3
        
        time.sleep(1)
        
        # 步骤4: 落库
        r4 = self.step4_store(scrape_data, r3.get('data'))
        results['store'] = r4
        if not r4.get('success'):
            logger.warning("落库失败，继续后续步骤")
        
        product_id = r4.get('product_id') or alibaba_id
        
        # 步骤5: 优化
        r5 = self.step5_optimize(product_id)
        results['optimize'] = r5
        
        # 步骤6: 回写
        r6 = self.step6_update(product_id)
        results['update'] = r6
        
        # 步骤7: 利润分析
        # 从本地1688数据获取重量（克转为千克）
        weight_g = None
        if r3.get('success') and r3.get('data', {}).get('sku_list'):
            first_sku = r3['data']['sku_list'][0]
            weight_g = first_sku.get('weight_g')
        
        r7 = self.step7_analyze(product_id, weight_g)
        results['analyze'] = r7
        
        logger.info("=" * 60)
        logger.info("🏁 工作流完成")
        logger.info("=" * 60)
        
        return results
    
    def run_lightweight(self, url: str) -> dict:
        """
        轻量级工作流（跳过采集步骤，假设商品已在采集箱）
        用于处理已有商品
        """
        logger.info("=" * 60)
        logger.info("🚀 轻量级工作流开始（跳过采集）")
        logger.info("=" * 60)
        
        results = {}
        
        # 步骤2: 提取
        r2 = self.step2_scrape()
        results['scrape'] = r2
        if not r2.get('success'):
            logger.error("提取失败，终止工作流")
            return results
        
        scrape_data = r2.get('data', {})
        alibaba_id = scrape_data.get('alibaba_product_id')
        
        # 步骤3: 本地1688获取重量
        r3 = self.step3_local_weight(alibaba_id)
        results['weight'] = r3
        
        # 步骤4: 落库
        r4 = self.step4_store(scrape_data, r3.get('data'))
        results['store'] = r4
        
        product_id = r4.get('product_id') or alibaba_id
        
        # 步骤5: 优化
        r5 = self.step5_optimize(product_id)
        results['optimize'] = r5
        
        # 步骤6: 回写
        r6 = self.step6_update(product_id)
        results['update'] = r6
        
        # 步骤7: 利润分析
        weight_g = None
        if r3.get('success') and r3.get('data', {}).get('sku_list'):
            first_sku = r3['data']['sku_list'][0]
            weight_g = first_sku.get('weight_g')
        
        r7 = self.step7_analyze(product_id, weight_g)
        results['analyze'] = r7
        
        logger.info("=" * 60)
        logger.info("🏁 工作流完成")
        logger.info("=" * 60)
        
        return results


def main():
    parser = argparse.ArgumentParser(description='自动化工作流运行器')
    parser.add_argument('--url', type=str, help='1688商品URL')
    parser.add_argument('--lightweight', action='store_true', help='跳过采集步骤（商品已在采集箱）')
    parser.add_argument('--url-file', type=str, help='批量处理URL文件')
    args = parser.parse_args()
    
    runner = WorkflowRunner()
    
    if args.url:
        # 单个商品
        if args.lightweight:
            results = runner.run_lightweight(args.url)
        else:
            results = runner.run_full(args.url)
        
        print("\n" + "=" * 50)
        print("工作流结果汇总:")
        print("=" * 50)
        for step, result in results.items():
            status = "✅" if result.get('success') else "❌"
            print(f"  {step}: {status}")
        
    elif args.url_file:
        # 批量处理
        with open(args.url_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        print(f"批量处理 {len(urls)} 个商品...")
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] 处理: {url}")
            results = runner.run_full(url)
            status = "✅" if all(r.get('success') for r in results.values()) else "❌"
            print(f"结果: {status}")
            
    else:
        print("请提供 --url 或 --url-file 参数")
        print("示例:")
        print("  python workflow_runner.py --url 'https://detail.1688.com/offer/1027205078815.html'")
        print("  python workflow_runner.py --url '...' --lightweight")


if __name__ == '__main__':
    main()
