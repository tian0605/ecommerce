import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze(data: Optional[Dict[str, Any]] = None, 
            data_source: Optional[str] = None) -> Dict[str, Any]:
    """
    电商运营数据分析函数
    
    Args:
        data: 待分析的数据字典
        data_source: 数据来源标识
    
    Returns:
        分析结果字典
    """
    result = {
        'status': 'success',
        'timestamp': datetime.now().isoformat(),
        'data_source': data_source,
        'metrics': {},
        'errors': []
    }
    
    try:
        # 1. 验证输入数据
        if data is None:
            logger.warning("输入数据为空，使用默认空数据")
            data = {}
        
        # 2. 确保数据是字典类型
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                result['status'] = 'failed'
                result['errors'].append(f"JSON解析失败：{str(e)}")
                logger.error(f"JSON解析失败：{e}")
                return result
        
        if not isinstance(data, dict):
            result['status'] = 'failed'
            result['errors'].append(f"数据类型错误，期望dict，得到{type(data)}")
            logger.error(f"数据类型错误：{type(data)}")
            return result
        
        # 3. 执行数据分析
        result['metrics'] = _perform_analysis(data)
        
        # 4. 验证分析结果
        if not result['metrics']:
            logger.warning("分析结果为空")
        
        logger.info(f"分析完成，状态：{result['status']}")
        
    except Exception as e:
        result['status'] = 'failed'
        result['errors'].append(f"分析过程异常：{str(e)}")
        logger.error(f"分析异常：{e}", exc_info=True)
    
    return result


def _perform_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行实际的数据分析逻辑
    
    Args:
        data: 输入数据
    
    Returns:
        分析指标字典
    """
    metrics = {
        'total_records': 0,
        'valid_records': 0,
        'error_records': 0,
        'summary': {}
    }
    
    try:
        # 统计记录数
        if 'records' in data:
            records = data.get('records', [])
            metrics['total_records'] = len(records) if isinstance(records, list) else 0
            
            # 验证每条记录
            for record in records:
                if _validate_record(record):
                    metrics['valid_records'] += 1
                else:
                    metrics['error_records'] += 1
        
        # 计算汇总指标
        if 'sales' in data:
            sales_data = data.get('sales', [])
            if isinstance(sales_data, list) and sales_data:
                metrics['summary']['total_sales'] = sum(
                    item.get('amount', 0) for item in sales_data 
                    if isinstance(item, dict)
                )
                metrics['summary']['avg_sales'] = (
                    metrics['summary']['total_sales'] / len(sales_data)
                    if len(sales_data) > 0 else 0
                )
        
        # 添加分析时间
        metrics['analysis_time'] = datetime.now().isoformat()
        
    except Exception as e:
        logger.error(f"分析执行失败：{e}")
        metrics['error'] = str(e)
    
    return metrics


def _validate_record(record: Any) -> bool:
    """
    验证单条记录是否有效
    
    Args:
        record: 待验证的记录
    
    Returns:
        是否有效
    """
    if record is None:
        return False
    if not isinstance(record, dict):
        return False
    # 检查必要字段
    required_fields = ['id', 'status']
    for field in required_fields:
        if field not in record:
            return False
    return True


def test_analyze():
    """测试analyze函数"""
    # 测试1：正常数据
    test_data = {
        'records': [
            {'id': 1, 'status': 'active'},
            {'id': 2, 'status': 'active'},
            {'id': 3, 'status': 'inactive'}
        ],
        'sales': [
            {'amount': 100},
            {'amount': 200},
            {'amount': 300}
        ]
    }
    
    result = analyze(data=test_data, data_source='test_source')
    assert result['status'] == 'success', f"测试1失败：{result}"
    assert result['metrics']['total_records'] == 3, f"测试1记录数错误"
    print("测试1通过：正常数据处理")
    
    # 测试2：空数据
    result = analyze(data=None)
    assert result['status'] == 'success', f"测试2失败：{result}"
    print("测试2通过：空数据处理")
    
    # 测试3：JSON字符串
    result = analyze(data=json.dumps(test_data))
    assert result['status'] == 'success', f"测试3失败：{result}"
    print("测试3通过：JSON字符串处理")
    
    # 测试4：无效数据类型
    result = analyze(data="invalid json")
    assert result['status'] == 'failed', f"测试4失败：{result}"
    print("测试4通过：无效数据处理")
    
    print("\n所有测试通过！")
    return True


if __name__ == '__main__':
    test_analyze()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
