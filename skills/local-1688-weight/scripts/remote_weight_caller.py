# remote_weight_caller.py
# 远程服务器调用本地服务的模块
# 通过 SSH 隧道访问本地 HTTP 服务

import json
import logging
import re
from typing import Optional, Dict, Any, List, Tuple

import requests

logger = logging.getLogger(__name__)

# 本地服务地址（通过隧道映射）
# 注意：8080端口是用户调整后的隧道端口
LOCAL_SERVICE_URL = "http://43.139.213.66:8080"
DEFAULT_PROBE_PRODUCT_ID = "1031400982378"

DIMENSION_PATTERNS = [
    re.compile(r'(?P<length>\d+(?:\.\d+)?)\s*[xX×*＊]\s*(?P<width>\d+(?:\.\d+)?)\s*[xX×*＊]\s*(?P<height>\d+(?:\.\d+)?)\s*(?P<unit>cm|厘米|公分|mm|毫米)?', re.IGNORECASE),
    re.compile(r'长\s*(?P<length>\d+(?:\.\d+)?)\s*(?:cm|厘米|公分)?\s*[，,、 ]*宽\s*(?P<width>\d+(?:\.\d+)?)\s*(?:cm|厘米|公分)?\s*[，,、 ]*高\s*(?P<height>\d+(?:\.\d+)?)\s*(?P<unit>cm|厘米|公分|mm|毫米)?', re.IGNORECASE),
]


def _normalize_sku_name(value: Any) -> str:
    return re.sub(r'[\s\u00a0]+', '', str(value or '')).strip().lower()


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    candidates = [text.strip()]
    fenced_match = re.search(r'```(?:json)?\s*(\{[\s\S]*\}|\[[\s\S]*\])\s*```', text, re.IGNORECASE)
    if fenced_match:
        candidates.insert(0, fenced_match.group(1).strip())
    brace_match = re.search(r'(\{[\s\S]*\})', text)
    if brace_match:
        candidates.append(brace_match.group(1).strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _extract_partial_dimension_payload(text: str) -> Optional[Dict[str, Any]]:
    raw_text = str(text or '').strip()
    if not raw_text:
        return None

    values: Dict[str, Any] = {}
    for field in ('length_cm', 'width_cm', 'height_cm'):
        match = re.search(rf'"{field}"\s*:\s*(null|-?\d+(?:\.\d+)?)', raw_text, re.IGNORECASE)
        if not match:
            return None
        token = match.group(1).lower()
        values[field] = None if token == 'null' else float(token)

    evidence_match = re.search(r'"evidence"\s*:\s*"([^\"]*)', raw_text, re.IGNORECASE)
    if evidence_match:
        values['evidence'] = evidence_match.group(1)
    return values


def _coerce_dimension_triplet(length: Any, width: Any, height: Any, unit: str = 'cm') -> Optional[Tuple[float, float, float]]:
    dims = [_safe_float(length), _safe_float(width), _safe_float(height)]
    if any(value is None or value <= 0 for value in dims):
        return None
    normalized_unit = str(unit or 'cm').lower()
    if normalized_unit in {'mm', '毫米'}:
        dims = [round(value / 10.0, 2) for value in dims]
    return dims[0], dims[1], dims[2]


def _extract_dimension_candidates(text: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen = set()
    normalized = str(text or '')
    if not normalized:
        return candidates

    for pattern in DIMENSION_PATTERNS:
        for match in pattern.finditer(normalized):
            triplet = _coerce_dimension_triplet(
                match.group('length'),
                match.group('width'),
                match.group('height'),
                match.groupdict().get('unit') or 'cm',
            )
            if not triplet:
                continue
            key = tuple(round(value, 2) for value in triplet)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                'length_cm': triplet[0],
                'width_cm': triplet[1],
                'height_cm': triplet[2],
                'evidence': match.group(0),
            })
    return candidates


def _complete_dimensions(sku: Dict[str, Any]) -> bool:
    return all(_safe_float(sku.get(field)) for field in ('length_cm', 'width_cm', 'height_cm'))


def _apply_dimensions(target: Dict[str, Any], source: Dict[str, Any], *, overwrite: bool = False) -> bool:
    changed = False
    for field in ('length_cm', 'width_cm', 'height_cm'):
        current = _safe_float(target.get(field))
        incoming = _safe_float(source.get(field))
        if incoming is None or incoming <= 0:
            continue
        if overwrite or current in (None, 0):
            if current != incoming:
                target[field] = incoming
                changed = True

    if changed:
        if source.get('dimension_source'):
            target['dimension_source'] = source.get('dimension_source')
        if source.get('dimension_confidence') is not None:
            target['dimension_confidence'] = source.get('dimension_confidence')
        if source.get('dimension_evidence'):
            target['dimension_evidence'] = source.get('dimension_evidence')
        if source.get('dimension_source_sku_name'):
            target['dimension_source_sku_name'] = source.get('dimension_source_sku_name')
    return changed


def _collect_description_text(scrape_data: Optional[Dict[str, Any]]) -> str:
    if not isinstance(scrape_data, dict):
        return ''
    fragments: List[str] = []
    for value in [
        scrape_data.get('description'),
        (scrape_data.get('raw_data') or {}).get('dialog_text') if isinstance(scrape_data.get('raw_data'), dict) else None,
    ]:
        if isinstance(value, str) and value.strip():
            fragments.append(value.strip())
    return '\n'.join(fragments)


def _line_matches_sku(line: str, sku_name: str) -> bool:
    normalized_line = _normalize_sku_name(line)
    normalized_sku = _normalize_sku_name(sku_name)
    if not normalized_line or not normalized_sku:
        return False

    if normalized_sku in normalized_line:
        return True

    parts = [part for part in re.split(r'[-/|｜,，、（）()\[\]]+', str(sku_name or '')) if len(part.strip()) >= 2]
    parts = [_normalize_sku_name(part) for part in parts if _normalize_sku_name(part)]
    if not parts:
        return False
    return any(part in normalized_line for part in parts)


def _resolve_dimensions_from_description_rules(sku: Dict[str, Any], description_text: str) -> Optional[Dict[str, Any]]:
    sku_name = str(sku.get('sku_name') or '')

    for candidate in _extract_dimension_candidates(sku_name):
        return {
            **candidate,
            'dimension_source': 'description_rule',
            'dimension_confidence': 0.82,
            'dimension_evidence': candidate.get('evidence') or sku_name,
        }

    if not description_text:
        return None

    lines = [line.strip() for line in re.split(r'[\n\r]+', description_text) if line.strip()]
    matching_lines = [line for line in lines if _line_matches_sku(line, sku_name)]
    for line in matching_lines:
        candidates = _extract_dimension_candidates(line)
        if candidates:
            candidate = candidates[0]
            return {
                **candidate,
                'dimension_source': 'description_rule',
                'dimension_confidence': 0.78,
                'dimension_evidence': line[:180],
            }

    all_candidates = _extract_dimension_candidates(description_text)
    if len(all_candidates) == 1:
        candidate = all_candidates[0]
        return {
            **candidate,
            'dimension_source': 'description_rule',
            'dimension_confidence': 0.58,
            'dimension_evidence': candidate.get('evidence') or description_text[:180],
        }
    return None


def _call_doubao_json(messages: List[Dict[str, Any]], max_tokens: int = 900, timeout: int = 120) -> Optional[Dict[str, Any]]:
    try:
        import sys
        from pathlib import Path

        config_path = Path('/root/.openclaw/workspace-e-commerce/config')
        if str(config_path) not in sys.path:
            sys.path.insert(0, str(config_path))
        from llm_caller import call_doubao  # type: ignore
    except Exception as exc:
        logger.warning(f'加载 Doubao 调用器失败: {exc}')
        return None

    response_text = call_doubao(messages, max_tokens=max_tokens, timeout=timeout)
    return _extract_json_block(response_text or '')


def _call_doubao_text(messages: List[Dict[str, Any]], max_tokens: int = 900, timeout: int = 120) -> Optional[str]:
    try:
        import sys
        from pathlib import Path

        config_path = Path('/root/.openclaw/workspace-e-commerce/config')
        if str(config_path) not in sys.path:
            sys.path.insert(0, str(config_path))
        from llm_caller import call_doubao  # type: ignore
    except Exception as exc:
        logger.warning(f'加载 Doubao 调用器失败: {exc}')
        return None

    return call_doubao(messages, max_tokens=max_tokens, timeout=timeout)


def _resolve_dimensions_from_description_llm(description_text: str, missing_skus: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    if not description_text or not missing_skus:
        return {}

    sku_names = [str(item.get('sku_name') or '').strip() for item in missing_skus if str(item.get('sku_name') or '').strip()]
    if not sku_names:
        return {}

    prompt = (
        '你是电商商品尺寸抽取助手。根据商品原始描述，只提取描述中明确出现的 SKU 尺寸。\n'
        '要求：\n'
        '1. 只返回 JSON，对象格式为 {"items": [{"sku_name": "", "length_cm": 0, "width_cm": 0, "height_cm": 0, "evidence": ""}]}。\n'
        '2. 没有明确尺寸的 SKU 不要猜测。\n'
        '3. 单位统一换算成 cm。\n'
        '4. 仅处理下面这些 SKU：' + '、'.join(sku_names) + '\n\n'
        '商品描述：\n' + description_text[:6000]
    )
    payload = _call_doubao_json([{'role': 'user', 'content': prompt}], max_tokens=1200, timeout=150)
    items = payload.get('items') if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}

    resolved: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        sku_name = str(item.get('sku_name') or '').strip()
        triplet = _coerce_dimension_triplet(item.get('length_cm'), item.get('width_cm'), item.get('height_cm'))
        if not sku_name or not triplet:
            continue
        resolved[_normalize_sku_name(sku_name)] = {
            'length_cm': triplet[0],
            'width_cm': triplet[1],
            'height_cm': triplet[2],
            'dimension_source': 'description_llm',
            'dimension_confidence': 0.66,
            'dimension_evidence': str(item.get('evidence') or '')[:200],
        }
    return resolved


def _resolve_dimensions_from_sku_image_llm(sku: Dict[str, Any], cache: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    image_url = str(sku.get('image_url') or '').strip()
    sku_name = str(sku.get('sku_name') or '').strip()
    if not image_url or not sku_name:
        return None

    if image_url in cache:
        return cache[image_url]

    prompt_content = [
        {
            'type': 'text',
            'text': (
                '你是电商商品尺寸识别助手。请只识别图片里和该 SKU 对应的明确尺寸信息，不要猜测。\n'
                f'SKU 名称：{sku_name}\n'
                '返回 JSON：{"length_cm": 0, "width_cm": 0, "height_cm": 0, "evidence": ""}。\n'
                '如果图片里没有明确尺寸，返回 {"length_cm": null, "width_cm": null, "height_cm": null, "evidence": ""}。'
            ),
        },
        {'type': 'image_url', 'image_url': {'url': image_url}},
    ]
    for _ in range(2):
        response_text = _call_doubao_text([{'role': 'user', 'content': prompt_content}], max_tokens=400, timeout=150)
        payload = _extract_json_block(response_text or '') or _extract_partial_dimension_payload(response_text or '')
        triplet = _coerce_dimension_triplet(
            payload.get('length_cm') if isinstance(payload, dict) else None,
            payload.get('width_cm') if isinstance(payload, dict) else None,
            payload.get('height_cm') if isinstance(payload, dict) else None,
        )
        if not triplet:
            continue

        resolved = {
            'length_cm': triplet[0],
            'width_cm': triplet[1],
            'height_cm': triplet[2],
            'dimension_source': 'sku_image_llm',
            'dimension_confidence': 0.62,
            'dimension_evidence': str(payload.get('evidence') if isinstance(payload, dict) else '')[:200],
        }
        cache[image_url] = resolved
        return resolved

    cache[image_url] = {}
    return None


def _build_sku_list_from_scrape(scrape_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(scrape_data, dict):
        return []

    sku_list: List[Dict[str, Any]] = []
    for sku in scrape_data.get('skus') or []:
        if not isinstance(sku, dict):
            continue
        sku_name = str(sku.get('name') or sku.get('sku_name') or '').strip()
        if not sku_name:
            continue
        sku_list.append({
            'sku_name': sku_name,
            'weight_g': _safe_float(sku.get('weight_g')),
            'length_cm': _safe_float(sku.get('length_cm')),
            'width_cm': _safe_float(sku.get('width_cm')),
            'height_cm': _safe_float(sku.get('height_cm')),
            'image_url': sku.get('image') if isinstance(sku.get('image'), str) else None,
            'dimension_source': None,
            'dimension_confidence': None,
            'dimension_evidence': None,
        })
    return sku_list


def _merge_local_and_scraped_skus(local_skus: List[Dict[str, Any]], scrape_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    local_map = {_normalize_sku_name(item.get('sku_name')): item for item in local_skus or [] if _normalize_sku_name(item.get('sku_name'))}
    scraped_skus = _build_sku_list_from_scrape(scrape_data)
    seen = set()

    for scraped in scraped_skus:
        sku_key = _normalize_sku_name(scraped.get('sku_name'))
        local_item = local_map.get(sku_key) or {}
        merged_item = {
            'sku_name': scraped.get('sku_name'),
            'weight_g': _safe_float(local_item.get('weight_g')) or _safe_float(scraped.get('weight_g')),
            'length_cm': _safe_float(local_item.get('length_cm')) or _safe_float(scraped.get('length_cm')),
            'width_cm': _safe_float(local_item.get('width_cm')) or _safe_float(scraped.get('width_cm')),
            'height_cm': _safe_float(local_item.get('height_cm')) or _safe_float(scraped.get('height_cm')),
            'image_url': scraped.get('image_url'),
            'dimension_source': 'local_service' if _complete_dimensions(local_item) else scraped.get('dimension_source'),
            'dimension_confidence': 0.98 if _complete_dimensions(local_item) else scraped.get('dimension_confidence'),
            'dimension_evidence': local_item.get('sku_name') if _complete_dimensions(local_item) else scraped.get('dimension_evidence'),
        }
        merged.append(merged_item)
        seen.add(sku_key)

    for local_item in local_skus or []:
        sku_key = _normalize_sku_name(local_item.get('sku_name'))
        if not sku_key or sku_key in seen:
            continue
        merged.append({
            'sku_name': local_item.get('sku_name'),
            'weight_g': _safe_float(local_item.get('weight_g')),
            'length_cm': _safe_float(local_item.get('length_cm')),
            'width_cm': _safe_float(local_item.get('width_cm')),
            'height_cm': _safe_float(local_item.get('height_cm')),
            'image_url': None,
            'dimension_source': 'local_service' if _complete_dimensions(local_item) else None,
            'dimension_confidence': 0.98 if _complete_dimensions(local_item) else None,
            'dimension_evidence': local_item.get('sku_name') if _complete_dimensions(local_item) else None,
        })

    return merged


def _dimension_group_key(sku: Dict[str, Any]) -> str:
    sku_name = str(sku.get('sku_name') or '')
    if not sku_name:
        return ''

    # Remove color labels so color-only variants can still share dimensions.
    without_color = re.sub(r'【[^】]*色[^】]*】', '', sku_name)
    without_color = re.sub(r'\[[^\]]*color[^\]]*\]', '', without_color, flags=re.IGNORECASE)

    candidates = [part.strip() for part in re.split(r'[-/|｜,，、]', without_color) if part.strip()]
    generic_tokens = {
        '不粘底', '防冻裂', '送纳米无痕胶', '送无痕胶', '送胶', '防滑', '加厚',
        '耐摔', '耐用', '防尘', '防潮', '厨房', '家用',
    }
    informative = [part for part in candidates if _normalize_sku_name(part) not in {_normalize_sku_name(token) for token in generic_tokens}]

    if informative:
        preferred = max(informative, key=lambda value: len(_normalize_sku_name(value)))
    elif candidates:
        preferred = max(candidates, key=lambda value: len(_normalize_sku_name(value)))
    else:
        preferred = without_color or sku_name

    return _normalize_sku_name(preferred)


def _summarize_dimension_sources(sku_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_source: Dict[str, int] = {}
    completed = 0
    for sku in sku_list:
        source = str(sku.get('dimension_source') or 'missing')
        by_source[source] = by_source.get(source, 0) + 1
        if _complete_dimensions(sku):
            completed += 1
    return {
        'total_skus': len(sku_list),
        'completed_dimension_skus': completed,
        'sources': by_source,
    }

def fetch_weight_from_local(product_id: str, timeout: int = 30, scrape_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    通过隧道调用本地服务获取1688商品重量和尺寸
    
    Args:
        product_id: 1688商品ID或URL
        timeout: 超时时间（秒）
    
    Returns:
        {
            'success': True/False,
            'weight_g': 1500,  # 克
            'length_cm': 30,
            'width_cm': 20,
            'height_cm': 15,
            'freight_info': {...},
            'error': None 或错误信息
        }
        如果失败返回 None
    """
    local_result: Dict[str, Any] = {
        'success': False,
        'sku_count': 0,
        'sku_list': [],
        'freight_info': None,
        'error': None,
    }

    try:
        logger.info(f"通过本地服务获取商品重量: {product_id}")
        
        response = requests.post(
            f"{LOCAL_SERVICE_URL}/fetch-weight",
            json={'product_id': product_id},
            timeout=timeout
        )
        
        if response.status_code != 200:
            logger.error(f"本地服务响应错误: HTTP {response.status_code}")
            local_result['error'] = f'HTTP {response.status_code}'
            response = None
        else:
            data = response.json()
        
        if response is not None and data.get('success'):
            # 解析新的per-SKU结构
            spec_list = data.get('spec_list', [])
            
            # 构建SKU列表（每个spec有自己的重量）
            sku_list = []
            for spec in spec_list:
                sku_name = spec.get('name', '')
                
                # per-SKU的重量和尺寸
                weight_g = spec.get('weight_g')
                length_cm = spec.get('length_cm')
                width_cm = spec.get('width_cm')
                height_cm = spec.get('height_cm')
                
                # 如果spec没有尺寸但名称包含尺寸信息，尝试解析
                if not all([length_cm, width_cm, height_cm]) and 'cm' in sku_name:
                    import re
                    size_match = re.search(r'(\d+)\*(\d+)\*(\d+)', sku_name)
                    if size_match:
                        length_cm = length_cm or int(size_match.group(1))
                        width_cm = width_cm or int(size_match.group(2))
                        height_cm = height_cm or int(size_match.group(3))
                
                sku_list.append({
                    'sku_name': sku_name,
                    'weight_g': weight_g,
                    'length_cm': length_cm,
                    'width_cm': width_cm,
                    'height_cm': height_cm,
                    'dimension_source': 'local_service' if all([length_cm, width_cm, height_cm]) else None,
                    'dimension_confidence': 0.98 if all([length_cm, width_cm, height_cm]) else None,
                    'dimension_evidence': sku_name if all([length_cm, width_cm, height_cm]) else None,
                })
            
            # 兼容旧结构：如果spec_list为空但有weight_info，创建默认SKU
            weight_info = data.get('weight_info', {})
            if not sku_list and weight_info:
                default_weight = weight_info.get('weight_g')
                applies_to_all = weight_info.get('applies_to_all', True)
                if default_weight:
                    sku_list.append({
                        'sku_name': '默认',
                        'weight_g': default_weight,
                        'length_cm': None,
                        'width_cm': None,
                        'height_cm': None,
                        'dimension_source': None,
                        'dimension_confidence': None,
                        'dimension_evidence': None,
                    })
            
            # 如果所有SKU都没有weight_g但有weight_info，用weight_info补充
            if sku_list and weight_info:
                default_weight = weight_info.get('weight_g')
                if default_weight:
                    for sku in sku_list:
                        if not sku.get('weight_g'):
                            sku['weight_g'] = default_weight
            
            # 计算总重量用于日志
            total_weight = sum((s.get('weight_g') or 0) for s in sku_list) if sku_list else 0
            logger.info(f"成功获取重量: {len(sku_list)} 个SKU, 总重约{total_weight}g")
            for sku in sku_list[:3]:  # 只打印前3个
                logger.info(f"   - {sku.get('sku_name')}: {sku.get('weight_g')}g, "
                           f"{sku.get('length_cm') or 'N/A'}x{sku.get('width_cm') or 'N/A'}x{sku.get('height_cm') or 'N/A'}cm")
            
            local_result = {
                'success': True,
                'sku_count': len(sku_list),
                'sku_list': sku_list,
                'freight_info': data.get('freight_info'),
                'error': None,
            }
        elif response is not None:
            logger.warning(f"本地服务未能提取数据: {data.get('error')}")
            local_result = {
                'success': False,
                'sku_count': 0,
                'sku_list': [],
                'freight_info': data.get('freight_info'),
                'error': data.get('error'),
            }
            
    except requests.exceptions.ConnectionError:
        logger.error("无法连接到本地服务，请检查隧道是否建立")
        local_result['error'] = 'connection_error'
    except requests.exceptions.Timeout:
        logger.error(f"本地服务响应超时 ({timeout}s)")
        local_result['error'] = 'timeout'
    except Exception as e:
        logger.error(f"调用本地服务异常: {e}")
        local_result['error'] = str(e)

    merged_sku_list = _merge_local_and_scraped_skus(local_result.get('sku_list') or [], scrape_data)
    description_text = _collect_description_text(scrape_data)

    for sku in merged_sku_list:
        if _complete_dimensions(sku):
            continue
        rule_match = _resolve_dimensions_from_description_rules(sku, description_text)
        if rule_match:
            _apply_dimensions(sku, rule_match)

    missing_after_rules = [sku for sku in merged_sku_list if not _complete_dimensions(sku)]
    llm_desc_results = _resolve_dimensions_from_description_llm(description_text, missing_after_rules)
    for sku in missing_after_rules:
        llm_match = llm_desc_results.get(_normalize_sku_name(sku.get('sku_name')))
        if llm_match:
            _apply_dimensions(sku, llm_match)

    image_cache: Dict[str, Dict[str, Any]] = {}
    for sku in merged_sku_list:
        if _complete_dimensions(sku):
            continue
        image_match = _resolve_dimensions_from_sku_image_llm(sku, image_cache)
        if image_match:
            _apply_dimensions(sku, image_match)

    grouped_completed: Dict[str, Dict[str, Any]] = {}
    for sku in merged_sku_list:
        if _complete_dimensions(sku):
            group_key = _dimension_group_key(sku)
            if group_key and group_key not in grouped_completed:
                grouped_completed[group_key] = sku

    for sku in merged_sku_list:
        if _complete_dimensions(sku):
            continue
        donor = grouped_completed.get(_dimension_group_key(sku))
        if donor and donor is not sku:
            propagated = {
                'length_cm': donor.get('length_cm'),
                'width_cm': donor.get('width_cm'),
                'height_cm': donor.get('height_cm'),
                'dimension_source': 'propagated_from_sibling',
                'dimension_confidence': 0.45,
                'dimension_evidence': donor.get('dimension_evidence') or donor.get('sku_name'),
                'dimension_source_sku_name': donor.get('sku_name'),
            }
            _apply_dimensions(sku, propagated)

    dimension_summary = _summarize_dimension_sources(merged_sku_list)
    overall_success = bool(local_result.get('success') or merged_sku_list or scrape_data)
    if merged_sku_list:
        logger.info(
            '尺寸解析完成: total=%s, completed=%s, sources=%s',
            dimension_summary.get('total_skus'),
            dimension_summary.get('completed_dimension_skus'),
            dimension_summary.get('sources'),
        )

    return {
        'success': overall_success,
        'sku_count': len(merged_sku_list),
        'sku_list': merged_sku_list,
        'freight_info': local_result.get('freight_info'),
        'error': local_result.get('error'),
        'dimension_summary': dimension_summary,
    }

def check_local_service_health() -> bool:
    """检查本地服务是否可用"""
    try:
        response = requests.get(f"{LOCAL_SERVICE_URL}/health", timeout=5)
        if response.status_code == 200:
            logger.info("本地服务健康检查通过")
            return True

        logger.warning(
            "本地服务 /health 返回非200，继续验证 /fetch-weight 是否可用: HTTP %s",
            response.status_code,
        )
    except Exception as e:
        logger.warning(f"本地服务 /health 不可用，继续验证业务接口: {e}")

    try:
        response = requests.post(
            f"{LOCAL_SERVICE_URL}/fetch-weight",
            json={'product_id': DEFAULT_PROBE_PRODUCT_ID},
            timeout=30
        )
        if response.status_code != 200:
            logger.warning(f"本地服务 /fetch-weight 不可用: HTTP {response.status_code}")
            return False

        data = response.json()
        if isinstance(data, dict) and 'success' in data:
            logger.info("本地服务业务接口检查通过")
            return True

        logger.warning(f"本地服务 /fetch-weight 返回格式异常: {data}")
    except Exception as e:
        logger.warning(f"本地服务业务接口检查失败: {e}")

    return False

if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    # 检查服务
    if check_local_service_health():
        # 测试获取
        result = fetch_weight_from_local("1027205078815")
        print(f"结果: {result}")
    else:
        print("本地服务不可用，请检查隧道")
