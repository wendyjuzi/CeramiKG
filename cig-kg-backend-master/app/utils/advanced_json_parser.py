#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级JSON解析器 - 异常33修复

基于异常33.md的要求，实现更加健壮的JSON解析功能，处理以下问题：
- 响应里含有不可见/控制字符或特殊引号
- 模型输出被截断或含有额外尾部垃圾
- 字符串内存在不合法的转义
- 输出被包裹在说明文字中或包含 Markdown ```json ``` 块
- 解析后又在后续处理中误删字段
"""

import json
import re
import logging
from json import JSONDecodeError
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _remove_control_chars(s: str) -> str:
    """去掉不可见控制字符（保留 \\n, \\r, \\t）"""
    return re.sub(r'[\u0000-\b\u000b\f\u000e-\u001f]', '', s)


def _normalize_quotes(s: str) -> str:
    """把常见的 Unicode 引号替换为标准双引号/单引号"""
    mapping = {
        '"': '"', '"': '"', ''': "'", ''': "'", 
        '„': '"', '‟': '"', '″': '"'
    }
    for k, v in mapping.items():
        s = s.replace(k, v)
    return s


def _escape_bad_backslashes(s: str) -> str:
    """
    将那些不符合 JSON 转义规范的反斜杠进行逃逸。
    将 `\\` 后面不是合法转义字符 (" \/ b f n r t u) 的情形替换为 \\\\。
    这能修复模型输出中孤立的反斜线，常导致 JSONDecodeError。
    """
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', s)


def _remove_trailing_commas(s: str) -> str:
    """删除对象/数组中诸如 `,}` 或 `,]` 的尾随逗号"""
    s = re.sub(r',\s*([}\]])', r'\1', s)
    return s


def _find_first_balanced_json_substring(s: str) -> Optional[Tuple[int, int, str]]:
    """
    找到第一个从 { 或 [ 开始的、并能配对闭合括号的子串（如果能匹配），
    返回 (start_index, end_index_inclusive, substring)，否则返回 None（但会返回从 start 到末尾的子串）。
    """
    if not s:
        return None
    pairs = {'{': '}', '[': ']'}
    for m in re.finditer(r'[{[]', s):
        start = m.start()
        open_ch = s[start]
        close_ch = pairs[open_ch]
        stack = []
        for i in range(start, len(s)):
            ch = s[i]
            if ch == open_ch:
                stack.append(open_ch)
            elif ch == close_ch:
                if stack:
                    stack.pop()
                if not stack:
                    return (start, i + 1, s[start:i + 1])
        # 未能找到闭合括号，返回从 start 到末尾（供后续修复尝试）
        return (start, len(s), s[start:])
    return None


def _find_json_with_decoder(s: str) -> Optional[Any]:
    """
    使用 JSONDecoder.raw_decode 从可能的起始位置尝试解析。
    """
    decoder = json.JSONDecoder()
    for m in re.finditer(r'[{[]', s):
        idx = m.start()
        try:
            obj, end = decoder.raw_decode(s, idx=idx)
            return obj
        except JSONDecodeError:
            continue
    return None


def safe_parse_json_response(raw: str) -> Tuple[Optional[Any], Dict[str, Any]]:
    """
    尝试按多种策略解析 raw（字符串），返回 (parsed_obj_or_None, diagnostics)
    diagnostics 包含用于排查的策略和错误信息。
    """
    diagnostics: Dict[str, Any] = {
        "length": len(raw) if raw is not None else 0,
        "tried": []
    }

    if raw is None:
        diagnostics["error"] = "raw is None"
        return None, diagnostics

    # 如果 raw 不是 str，尝试 decode
    if not isinstance(raw, str):
        try:
            raw = raw.decode('utf-8', errors='replace')  # type: ignore
        except Exception:
            raw = str(raw)

    # 1) 直接尝试 json.loads
    try:
        parsed = json.loads(raw)
        diagnostics["tried"].append("json.loads(raw)")
        diagnostics["strategy"] = "direct"
        return parsed, diagnostics
    except Exception as e:
        diagnostics["tried"].append(("json.loads", str(e)))

    # 2) 使用 JSONDecoder 从文本中寻找可解析片段
    try:
        parsed = _find_json_with_decoder(raw)
        if parsed is not None:
            diagnostics["tried"].append("json.decoder.search(raw)")
            diagnostics["strategy"] = "decoder_search_raw"
            return parsed, diagnostics
    except Exception as e:
        diagnostics["tried"].append(("decoder_search_raw", str(e)))

    # 3) 基础清洗与修复尝试：移除控制字符、规范引号、转义孤立反斜线、删除尾随逗号
    cleaned = _remove_control_chars(raw)
    cleaned = _normalize_quotes(cleaned)
    cleaned = _escape_bad_backslashes(cleaned)
    cleaned = _remove_trailing_commas(cleaned)
    diagnostics["cleaned_len"] = len(cleaned)
    diagnostics["tried"].append("basic_clean")

    try:
        parsed = json.loads(cleaned)
        diagnostics["tried"].append("json.loads(cleaned)")
        diagnostics["strategy"] = "cleaned"
        return parsed, diagnostics
    except Exception as e:
        diagnostics["tried"].append(("json.loads(cleaned)", str(e)))

    # 4) 尝试在 cleaned 文本中使用 JSONDecoder 搜索
    try:
        parsed = _find_json_with_decoder(cleaned)
        if parsed is not None:
            diagnostics["tried"].append("decoder_search_cleaned")
            diagnostics["strategy"] = "decoder_search_cleaned"
            return parsed, diagnostics
    except Exception as e:
        diagnostics["tried"].append(("decoder_search_cleaned", str(e)))

    # 5) 提取第一个平衡子串，修复后尝试解析
    found = _find_first_balanced_json_substring(raw)
    if found:
        start, end, sub = found
        diagnostics["json_sub_start_end"] = (start, end)
        # 再次对 sub 做清洗与尾部补齐尝试
        sub_clean = _remove_control_chars(sub)
        sub_clean = _normalize_quotes(sub_clean)
        sub_clean = _escape_bad_backslashes(sub_clean)
        sub_clean = _remove_trailing_commas(sub_clean)

        try:
            parsed = json.loads(sub_clean)
            diagnostics["tried"].append("json.loads(sub_clean)")
            diagnostics["strategy"] = "substring_cleaned"
            return parsed, diagnostics
        except Exception as e:
            diagnostics["tried"].append(("json.loads(sub_clean)", str(e)))
            # 如果 sub_clean 末尾仍然缺闭合括号，尝试补齐（基于括号计数）
            add = ''
            lbrace = sub_clean.count('{') - sub_clean.count('}')
            lbrack = sub_clean.count('[') - sub_clean.count(']')
            if lbrace > 0:
                add += '}' * lbrace
            if lbrack > 0:
                add += ']' * lbrack
            if add:
                try:
                    parsed = json.loads(sub_clean + add)
                    diagnostics["tried"].append("json.loads(sub_clean + add)")
                    diagnostics["strategy"] = "substring_cleaned_plus_closing"
                    return parsed, diagnostics
                except Exception as e2:
                    diagnostics["tried"].append(("json.loads(sub_clean+add)", str(e2)))

    # 6) 最后尝试：在原始文本中提取所有 {...} 或 [...] 片段，逐一尝试解析（兜底）
    fragments = re.findall(r'(\{(?:.|\n)*?\}|\[(?:.|\n)*?\])', raw, flags=re.DOTALL)
    for i, frag in enumerate(fragments):
        frag_clean = _remove_control_chars(frag)
        frag_clean = _normalize_quotes(frag_clean)
        frag_clean = _escape_bad_backslashes(frag_clean)
        frag_clean = _remove_trailing_commas(frag_clean)
        try:
            parsed = json.loads(frag_clean)
            diagnostics["tried"].append(f"fragment_{i}")
            diagnostics["strategy"] = "fragment_guess"
            return parsed, diagnostics
        except Exception as e:
            diagnostics["tried"].append((f"fragment_{i}", str(e)))
            continue

    # 全部失败，返回 diagnostics 以便进一步排查
    diagnostics["error"] = "all_strategies_failed"
    logger.warning("JSON parse failed; diagnostics: %s", diagnostics)
    return None, diagnostics


def safe_extract_json_from_response(response: str, data_type: str = "general") -> Dict[str, Any]:
    """
    替换原有的 _extract_json_from_response 函数
    使用异常33的健壮JSON解析策略
    """
    logger.info(f"开始使用高级JSON解析器解析响应，数据类型: {data_type}")
    
    if not response or not response.strip():
        logger.warning("响应为空，返回兜底结构")
        return _create_fallback_structure(data_type)
    
    # 记录原始响应的部分内容用于调试
    if len(response) > 2000:
        logger.debug(f"原始响应前1000字符: {response[:1000]}")
        logger.debug(f"原始响应后1000字符: {response[-1000:]}")
    else:
        logger.debug(f"完整原始响应: {response}")
    
    # 使用新的健壮解析函数
    parsed_result, diagnostics = safe_parse_json_response(response)
    
    # 记录诊断信息
    logger.info(f"解析诊断信息: {diagnostics}")
    
    if parsed_result is not None:
        # 验证解析结果的结构
        if isinstance(parsed_result, dict):
            # 检查是否包含预期字段
            if data_type == "entities" and "entities" in parsed_result:
                entities_count = len(parsed_result.get("entities", []))
                logger.info(f"实体解析成功，策略: {diagnostics.get('strategy', 'unknown')}, 实体数量: {entities_count}")
                return parsed_result
            elif data_type == "relations" and "relations" in parsed_result:
                relations_count = len(parsed_result.get("relations", []))
                logger.info(f"关系解析成功，策略: {diagnostics.get('strategy', 'unknown')}, 关系数量: {relations_count}")
                return parsed_result
            elif data_type == "general":
                logger.info(f"通用解析成功，策略: {diagnostics.get('strategy', 'unknown')}")
                return parsed_result
            else:
                logger.warning(f"解析成功但缺少预期字段，数据类型: {data_type}, 解析结果keys: {list(parsed_result.keys())}")
                # 尝试字段映射或修复
                fixed_result = _try_fix_missing_fields(parsed_result, data_type)
                if fixed_result:
                    return fixed_result
        else:
            logger.warning(f"解析结果不是字典类型: {type(parsed_result)}")
            # 异常34修复：处理非字典类型（如数组）的解析结果
            fixed_result = _try_fix_missing_fields(parsed_result, data_type)
            if fixed_result:
                logger.info(f"非字典类型结果修复成功，数据类型: {data_type}")
                return fixed_result
    
    # 解析失败，返回兜底结构
    logger.error(f"JSON解析完全失败，数据类型: {data_type}")
    return _create_fallback_structure(data_type)


def _create_fallback_structure(data_type: str) -> Dict[str, Any]:
    """创建兜底数据结构"""
    base_structure = {
        "_parse_error": True,
        "_error_info": "JSON解析完全失败",
        "_fallback": True
    }
    
    if data_type == "entities":
        base_structure["entities"] = []
    elif data_type == "relations":
        base_structure["relations"] = []
    else:
        base_structure.update({
            "entities": [],
            "relations": []
        })
    
    return base_structure


def _try_fix_missing_fields(parsed_result: Any, data_type: str) -> Optional[Dict[str, Any]]:
    """尝试修复缺少的字段（异常34&35修复）"""
    # 处理非字典类型输入（如数组）
    if not isinstance(parsed_result, dict):
        if isinstance(parsed_result, list):
            entity_fields = ["entity_name", "entity_type", "entity_id"]
            relation_fields = ["relation_name", "relation_id", "head_entity", "tail_entity", "head_entity_id", "tail_entity_id"]
            
            if data_type == "entities" and parsed_result and any(field in parsed_result[0] for field in entity_fields):
                logger.info("检测到直接的实体数组（非字典输入），包装为entities结构")
                return {"entities": parsed_result}
            elif data_type == "relations" and parsed_result and any(field in parsed_result[0] for field in relation_fields):
                logger.info("检测到直接的关系数组（非字典输入），包装为relations结构")  
                return {"relations": parsed_result}
        return None
    
    # 异常35修复：验证解析结果的有效性
    if not _is_valid_parsed_result(parsed_result, data_type):
        logger.warning(f"解析结果无效，数据类型: {data_type}, keys: {list(parsed_result.keys()) if isinstance(parsed_result, dict) else 'N/A'}")
        return None
    
    if data_type == "entities":
        # 策略1: 尝试从其他可能的字段名中找到实体数组
        for possible_key in ["entity", "entity_list", "results", "data"]:
            if possible_key in parsed_result and isinstance(parsed_result[possible_key], list):
                logger.info(f"找到实体数据在字段: {possible_key}")
                return {"entities": parsed_result[possible_key]}
        
        # 策略2: 检查是否是直接的实体对象（异常34修复）
        entity_fields = ["entity_name", "entity_type", "entity_id"]
        if any(field in parsed_result for field in entity_fields):
            logger.info("检测到直接的实体对象，转换为entities数组")
            return {"entities": [parsed_result]}
        
        # 策略3: 检查是否解析结果就是实体数组
        if isinstance(parsed_result, list):
            # 检查数组元素是否包含实体字段
            if parsed_result and any(field in parsed_result[0] for field in entity_fields):
                logger.info("检测到直接的实体数组，包装为entities结构")
                return {"entities": parsed_result}
                
    elif data_type == "relations":
        # 策略1: 尝试从其他可能的字段名中找到关系数组
        for possible_key in ["relation", "relation_list", "results", "data"]:
            if possible_key in parsed_result and isinstance(parsed_result[possible_key], list):
                logger.info(f"找到关系数据在字段: {possible_key}")
                return {"relations": parsed_result[possible_key]}
        
        # 策略2: 检查是否是直接的关系对象（异常34修复）  
        relation_fields = ["relation_name", "relation_id", "head_entity", "tail_entity", "head_entity_id", "tail_entity_id"]
        if any(field in parsed_result for field in relation_fields):
            logger.info("检测到直接的关系对象，转换为relations数组")
            return {"relations": [parsed_result]}
        
        # 策略3: 检查是否解析结果就是关系数组
        if isinstance(parsed_result, list):
            # 检查数组元素是否包含关系字段
            if parsed_result and any(field in parsed_result[0] for field in relation_fields):
                logger.info("检测到直接的关系数组，包装为relations结构")
                return {"relations": parsed_result}
    
    return None


def _is_valid_parsed_result(parsed_result: Dict[str, Any], data_type: str) -> bool:
    """验证解析结果的有效性（异常35修复）"""
    if not isinstance(parsed_result, dict):
        return False
    
    # 常见的无效字段（通常是实体的属性而不是实体对象本身）
    invalid_only_fields = {
        "型号", "功率", "产地", "重量", "尺寸", "颜色", "材质", "品牌", 
        "版本", "规格", "容量", "温度", "压力", "速度", "长度", "宽度", 
        "高度", "直径", "厚度", "面积", "体积", "数量", "价格", "成本",
        "model", "power", "weight", "size", "color", "brand", "version"
    }
    
    if data_type == "entities":
        # 检查是否只包含属性字段
        keys = set(parsed_result.keys())
        
        # 如果只有一个key并且是常见的属性字段，认为无效
        if len(keys) == 1 and keys.issubset(invalid_only_fields):
            logger.warning(f"检测到只包含属性字段的无效实体解析结果: {list(keys)}")
            return False
        
        # 如果所有keys都是属性字段，也认为无效
        if keys and keys.issubset(invalid_only_fields):
            logger.warning(f"检测到只包含属性字段的无效实体解析结果: {list(keys)}")
            return False
        
        # 检查是否包含有效的实体字段
        valid_entity_fields = {"entity_name", "entity_type", "entity_id", "name", "type", "id"}
        if not keys.intersection(valid_entity_fields):
            # 如果没有任何有效的实体字段，检查是否可能是属性对象
            if len(keys) <= 3 and all(len(k) <= 10 for k in keys):  # 短字段名，可能是属性
                logger.warning(f"检测到疑似属性对象而非实体对象: {list(keys)}")
                return False
                
    elif data_type == "relations":
        # 检查是否包含有效的关系字段
        valid_relation_fields = {
            "relation_name", "relation_id", "head_entity", "tail_entity", 
            "head_entity_id", "tail_entity_id", "name", "source", "target"
        }
        keys = set(parsed_result.keys())
        
        if not keys.intersection(valid_relation_fields):
            logger.warning(f"检测到无效的关系解析结果，缺少关系字段: {list(keys)}")
            return False
    
    return True


def test_advanced_json_parser():
    """测试高级JSON解析器的功能"""
    logger.info("开始测试高级JSON解析器...")
    
    # 测试用例1: 包含控制字符的JSON
    test_cases = [
        # 正常JSON
        '{"entities": [{"name": "test", "type": "entity"}]}',
        
        # 包含特殊引号的JSON
        '{"entities": [{"name": "test", "type": "entity"}]}',
        
        # 包含孤立反斜线的JSON
        '{"entities": [{"name": "test\\path", "type": "entity"}]}',
        
        # 包含尾随逗号的JSON
        '{"entities": [{"name": "test", "type": "entity",}]}',
        
        # 被markdown包裹的JSON
        '```json\n{"entities": [{"name": "test", "type": "entity"}]}\n```',
        
        # 截断的JSON
        '{"entities": [{"name": "test", "type": "entity"}',
        
        # 包含额外文字的JSON
        'Here is the result: {"entities": [{"name": "test", "type": "entity"}]} End of response.'
    ]
    
    for i, test_case in enumerate(test_cases):
        logger.info(f"测试用例 {i+1}: {test_case[:50]}...")
        result, diagnostics = safe_parse_json_response(test_case)
        logger.info(f"结果: {result is not None}, 策略: {diagnostics.get('strategy', 'failed')}")
    
    logger.info("高级JSON解析器测试完成")


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    test_advanced_json_parser()