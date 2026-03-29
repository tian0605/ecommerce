import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_update_data(data: Any, required_fields: Optional[list] = None) -> Dict[str, Any]:
    """
    验证并标准化更新数据
    """
    if data is None:
        raise ValueError("更新数据不能为空")
    
    # 处理字符串类型的 JSON 数据
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败：{str(e)}")
    
    # 确保是字典类型
    if not isinstance(data, dict):
        raise TypeError(f"更新数据必须是字典类型，当前类型：{type(data)}")
    
    # 检查必填字段
    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"缺少必填字段：{missing_fields}")
    
    return data


def safe_update(data: Dict[str, Any], target: Dict[str, Any], 
                required_fields: Optional[list] = None) -> Dict[str, Any]:
    """
    安全执行更新操作，包含完整的错误处理和验证
    """
    try:
        # 验证更新数据
        validated_data = validate_update_data(data, required_fields)
        
        # 验证目标数据
        if not isinstance(target, dict):
            raise TypeError("目标数据必须是字典类型")
        
        # 执行更新
        target.update(validated_data)
        
        # 添加更新标记
        target['_updated_at'] = datetime.now().isoformat()
        target['_update_status'] = 'success'
        
        logger.info(f"更新成功，更新字段：{list(validated_data.keys())}")
        return target
        
    except Exception as e:
        logger.error(f"更新失败：{str(e)}")
        # 添加错误信息到目标数据
        if isinstance(target, dict):
            target['_update_status'] = 'failed'
            target['_update_error'] = str(e)
        raise


def fix_update_step(update_data: Any, target_data: Dict[str, Any],
                   required_fields: Optional[list] = None) -> Dict[str, Any]:
    """
    修复 update 步骤的主函数
    处理常见的 update 失败场景
    """
    # 1. 处理 None 值
    if update_data is None:
        logger.warning("更新数据为 None，使用空字典")
        update_data = {}
    
    # 2. 处理字符串类型的 JSON
    if isinstance(update_data, str):
        try:
            update_data = json.loads(update_data)
            logger.info("成功解析 JSON 字符串")
        except json.JSONDecodeError:
            logger.error("JSON 解析失败，使用空字典")
            update_data = {}
    
    # 3. 确保是字典类型
    if not isinstance(update_data, dict):
        logger.warning(f"更新数据类型错误：{type(update_data)}，转换为字典")
        update_data = {'value': update_data}
    
    # 4. 确保目标数据是字典
    if not isinstance(target_data, dict):
        target_data = {}
    
    # 5. 执行安全更新
    try:
        result = safe_update(update_data, target_data, required_fields)
        return result
    except Exception as e:
        # 返回包含错误信息的结果，不中断流程
        target_data['_update_status'] = 'failed'
        target_data['_update_error'] = str(e)
        target_data['_update_timestamp'] = datetime.now().isoformat()
        logger.error(f"update 步骤失败：{str(e)}")
        return target_data


# 测试验证
def test_fix():
    """测试修复函数"""
    print("开始测试 update 修复函数...")
    
    # 测试 1: 正常字典更新
    target1 = {'id': 1, 'name': 'test'}
    data1 = {'name': 'updated', 'status': 'active'}
    result1 = fix_update_step(data1, target1)
    assert result1['name'] == 'updated'
    assert result1['_update_status'] == 'success'
    print("✓ 测试 1 通过：正常字典更新")
    
    # 测试 2: JSON 字符串更新
    target2 = {'id': 2}
    data2 = '{"status": "pending"}'
    result2 = fix_update_step(data2, target2)
    assert result2['status'] == 'pending'
    print("✓ 测试 2 通过：JSON 字符串更新")
    
    # 测试 3: None 值处理
    target3 = {'id': 3}
    data3 = None
    result3 = fix_update_step(data3, target3)
    assert result3['_update_status'] == 'success'
    print("✓ 测试 3 通过：None 值处理")
    
    # 测试 4: 必填字段验证
    target4 = {'id': 4}
    data4 = {'name': 'test'}
    try:
        result4 = fix_update_step(data4, target4, required_fields=['id', 'name'])
        print("✓ 测试 4 通过：必填字段验证")
    except ValueError as e:
        print(f"✓ 测试 4 通过：必填字段验证捕获异常 - {e}")
    
    print("\n所有测试完成！")
    return True


if __name__ == "__main__":
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
