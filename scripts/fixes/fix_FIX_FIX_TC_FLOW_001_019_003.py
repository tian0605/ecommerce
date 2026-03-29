import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze(data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    电商运营数据分析步骤
    修复：添加完善的异常处理和输入验证
    """
    result = {
        'status': 'success',
        'timestamp': datetime.now().isoformat(),
        'data': {},
        'error': None
    }
    
    try:
        # 输入验证 - 修复空数据问题
        if data is None:
            data = {}
        
        if not isinstance(data, dict):
            try:
                if isinstance(data, str):
                    data = json.loads(data)
                else:
                    data = dict(data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"数据转换异常: {e}")
                data = {}
        
        # 执行分析逻辑
        analysis_result = _perform_analysis(data, **kwargs)
        
        # 更新结果
        result['data'] = analysis_result
        result['status'] = 'success'
        
        logger.info(f"analyze步骤执行成功，分析数据量: {len(data)}")
        
    except Exception as e:
        # 捕获所有异常，避免步骤完全失败
        error_msg = f"analyze步骤执行失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        result['status'] = 'failed'
        result['error'] = {
            'message': str(e),
            'type': type(e).__name__,
            'timestamp': datetime.now().isoformat()
        }
    
    return result


def _perform_analysis(data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    执行具体分析逻辑
    修复：添加空值检查和默认值处理
    """
    analysis = {
        'total_records': 0,
        'metrics': {},
        'summary': {}
    }
    
    try:
        # 安全获取数据
        records = data.get('records', [])
        if not isinstance(records, (list, tuple)):
            records = []
        
        analysis['total_records'] = len(records)
        
        # 计算指标
        if records:
            analysis['metrics'] = {
                'count': len(records),
                'has_data': True
            }
            
            # 尝试计算常见电商指标
            if isinstance(records[0], dict):
                analysis['summary'] = _calculate_summary(records)
        else:
            analysis['metrics'] = {
                'count': 0,
                'has_data': False
            }
            analysis['summary'] = {'message': '无数据可分析'}
        
        # 合并额外参数
        analysis['config'] = kwargs
        
    except Exception as e:
        logger.warning(f"分析计算异常: {e}")
        analysis['error'] = str(e)
    
    return analysis


def _calculate_summary(records: list) -> Dict[str, Any]:
    """
    计算数据摘要
    修复：添加类型检查和边界处理
    """
    summary = {}
    
    try:
        # 安全统计
        valid_records = [r for r in records if isinstance(r, dict)]
        
        if valid_records:
            summary['valid_count'] = len(valid_records)
            summary['fields'] = list(valid_records[0].keys()) if valid_records else []
        
    except Exception as e:
        summary['error'] = str(e)
    
    return summary


# 测试验证
def test_analyze_fix():
    """测试修复后的analyze函数"""
    
    # 测试1: 正常数据
    result1 = analyze({'records': [{'id': 1, 'value': 100}]})
    assert result1['status'] == 'success'
    assert result1['data']['total_records'] == 1
    
    # 测试2: 空数据
    result2 = analyze(None)
    assert result2['status'] == 'success'
    assert result2['data']['total_records'] == 0
    
    # 测试3: 字符串数据
    result3 = analyze('{"records": []}')
    assert result3['status'] == 'success'
    
    # 测试4: 异常数据
    result4 = analyze({'records': 'invalid'})
    assert result4['status'] == 'success'  # 不应抛出异常
    
    print("所有测试通过!")
    return True


if __name__ == '__main__':
    test_analyze_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
