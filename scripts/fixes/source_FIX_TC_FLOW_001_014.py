import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze(data: Optional[Dict[str, Any]] = None, 
            data_source: Optional[str] = None,
            metrics: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    电商运营数据分析函数
    
    参数:
        data: 待分析的数据字典
        data_source: 数据源标识
        metrics: 需要分析的指标列表
    
    返回:
        分析结果字典
    """
    result = {
        'success': False,
        'timestamp': datetime.now().isoformat(),
        'data': None,
        'error': None
    }
    
    try:
        # 1. 参数验证
        if data is None and data_source is None:
            raise ValueError("必须提供 data 或 data_source 参数")
        
        # 2. 数据加载
        if data is None:
            data = _load_data_from_source(data_source)
        
        # 3. 数据完整性检查
        if not isinstance(data, dict):
            raise TypeError(f"数据必须是字典类型，当前类型: {type(data)}")
        
        if len(data) == 0:
            raise ValueError("数据不能为空")
        
        # 4. 执行分析
        analysis_result = _perform_analysis(data, metrics)
        
        # 5. 构建成功结果
        result['success'] = True
        result['data'] = analysis_result
        logger.info(f"分析成功，处理了 {len(data)} 条数据")
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"分析失败: {str(e)}")
    
    return result


def _load_data_from_source(source: str) -> Dict[str, Any]:
    """从数据源加载数据"""
    if not source:
        raise ValueError("数据源不能为空")
    
    # 模拟数据加载，实际场景可替换为数据库或API调用
    logger.info(f"从数据源加载: {source}")
    return {
        'source': source,
        'records': []
    }


def _perform_analysis(data: Dict[str, Any], 
                      metrics: Optional[List[str]] = None) -> Dict[str, Any]:
    """执行数据分析"""
    if metrics is None:
        metrics = ['total', 'average', 'trend']
    
    analysis = {
        'metrics': metrics,
        'summary': {},
        'details': data
    }
    
    # 模拟分析逻辑
    for metric in metrics:
        analysis['summary'][metric] = _calculate_metric(data, metric)
    
    return analysis


def _calculate_metric(data: Dict[str, Any], metric: str) -> Any:
    """计算单个指标"""
    if metric == 'total':
        return len(data.get('records', []))
    elif metric == 'average':
        records = data.get('records', [])
        if records:
            return sum(records) / len(records) if all(isinstance(r, (int, float)) for r in records) else 0
        return 0
    elif metric == 'trend':
        return 'stable'
    else:
        return None


def test_analyze():
    """测试函数"""
    # 测试用例1: 正常数据
    test_data = {'records': [100, 200, 300], 'source': 'test'}
    result1 = analyze(data=test_data, metrics=['total', 'average'])
    assert result1['success'] == True
    assert result1['error'] is None
    
    # 测试用例2: 空数据
    result2 = analyze(data={})
    assert result2['success'] == False
    assert result2['error'] is not None
    
    # 测试用例3: 无参数
    result3 = analyze()
    assert result3['success'] == False
    assert result3['error'] is not None
    
    print("所有测试通过!")
    return True


if __name__ == '__main__':
    test_analyze()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
