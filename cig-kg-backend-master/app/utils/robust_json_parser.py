#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强健的JSON解析器 - 异常15修复

专门处理大模型返回的不完整或截断的JSON数据，提供多种容错机制和兜底策略。
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional, Union, Tuple

logger = logging.getLogger(__name__)

class RobustJSONParser:
    """强健的JSON解析器，支持多种容错机制"""
    
    def __init__(self):
        self.repair_attempts = 0
        self.max_repair_attempts = 10
    
    def parse(self, response: str, fallback_structure: Optional[Dict] = None) -> Dict[str, Any]:
        """
        主解析方法，提供完整的容错机制
        
        Args:
            response: 大模型返回的响应
            fallback_structure: 当所有解析失败时的兜底数据结构
            
        Returns:
            解析后的字典，或兜底结构
        """
        if not response or not response.strip():
            logger.warning("响应为空，返回兜底结构")
            return fallback_structure or {"entities": [], "relations": []}
        
        self.repair_attempts = 0
        original_response = response
        response = response.strip()
        
        logger.info(f"开始解析JSON，原始长度: {len(response)}")
        
        # 策略1: 直接解析
        result = self._try_direct_parse(response)
        if result is not None:
            return result
        
        # 策略2: 提取并解析markdown代码块
        result = self._try_markdown_parse(response)
        if result is not None:
            return result
        
        # 策略3: 边界提取解析
        result = self._try_boundary_parse(response)
        if result is not None:
            return result
        
        # 策略4: 增强的截断修复
        result = self._try_enhanced_truncation_repair(response)
        if result is not None:
            return result
        
        # 策略5: 分段提取解析
        result = self._try_segment_parse(response)
        if result is not None:
            return result
        
        # 策略6: 模式匹配提取
        result = self._try_pattern_extraction(response)
        if result is not None:
            return result
        
        # 所有策略失败，记录详细信息并返回兜底结构
        logger.error("所有JSON解析策略都失败了")
        self._log_parse_failure(original_response)
        
        return fallback_structure or {
            "entities": [],
            "relations": [],
            "_parse_error": True,
            "_error_info": "JSON解析完全失败"
        }
    
    def _try_direct_parse(self, response: str) -> Optional[Dict]:
        """策略1: 直接解析"""
        try:
            result = json.loads(response)
            # 异常16修复：记录解析成功的详细信息
            entities_count = len(result.get("entities", []))
            relations_count = len(result.get("relations", []))
            logger.info(f"策略1成功: 直接JSON解析 - {entities_count}个实体, {relations_count}个关系")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"直接解析失败: {e}")
            return None
    
    def _try_markdown_parse(self, response: str) -> Optional[Dict]:
        """策略2: 提取并解析markdown代码块"""
        json_pattern = r'```(?:json)?\s*(.*?)\s*```'
        match = re.search(json_pattern, response, re.DOTALL | re.IGNORECASE)
        
        if match:
            json_content = match.group(1).strip()
            try:
                result = json.loads(json_content)
                # 异常16修复：记录解析成功的详细信息
                entities_count = len(result.get("entities", []))
                relations_count = len(result.get("relations", []))
                logger.info(f"策略2成功: markdown代码块解析 - {entities_count}个实体, {relations_count}个关系")
                return result
            except json.JSONDecodeError as e:
                logger.debug(f"markdown代码块解析失败: {e}")
        
        return None
    
    def _try_boundary_parse(self, response: str) -> Optional[Dict]:
        """策略3: 边界提取解析"""
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_content = response[start_idx:end_idx + 1]
            try:
                result = json.loads(json_content)
                # 异常16修复：记录解析成功的详细信息
                entities_count = len(result.get("entities", []))
                relations_count = len(result.get("relations", []))
                logger.info(f"策略3成功: 边界提取解析 - {entities_count}个实体, {relations_count}个关系")
                return result
            except json.JSONDecodeError as e:
                logger.debug(f"边界提取解析失败: {e}")
        
        return None
    
    def _try_enhanced_truncation_repair(self, response: str) -> Optional[Dict]:
        """策略4: 增强的截断修复 - 异常15的核心修复"""
        logger.debug("开始增强截断修复...")
        
        # 首先尝试找到JSON内容
        json_content = self._extract_json_content(response)
        if not json_content:
            return None
        
        # 检测截断类型和位置
        truncation_info = self._detect_truncation(json_content)
        logger.debug(f"截断检测结果: {truncation_info}")
        
        # 根据截断类型选择修复策略
        if truncation_info['type'] == 'string_truncation':
            result = self._repair_string_truncation(json_content, truncation_info)
        elif truncation_info['type'] == 'object_truncation':
            result = self._repair_object_truncation(json_content, truncation_info)
        elif truncation_info['type'] == 'array_truncation':
            result = self._repair_array_truncation(json_content, truncation_info)
        else:
            result = self._repair_general_truncation(json_content)
        
        if result:
            # 异常16修复：记录解析成功的详细信息
            entities_count = len(result.get("entities", []))
            relations_count = len(result.get("relations", []))
            logger.info(f"策略4成功: 增强截断修复 - {entities_count}个实体, {relations_count}个关系")
            return result
        
        return None
    
    def _detect_truncation(self, json_str: str) -> Dict[str, Any]:
        """检测JSON截断的类型和位置"""
        truncation_info = {
            'type': 'unknown',
            'position': len(json_str),
            'context': '',
            'missing_chars': []
        }
        
        # 检查字符串截断
        if self._is_string_truncation(json_str):
            truncation_info['type'] = 'string_truncation'
            truncation_info['missing_chars'] = ['"']
        
        # 检查对象截断
        elif self._is_object_truncation(json_str):
            truncation_info['type'] = 'object_truncation'
            open_braces = json_str.count('{')
            close_braces = json_str.count('}')
            truncation_info['missing_chars'] = ['}'] * (open_braces - close_braces)
        
        # 检查数组截断
        elif self._is_array_truncation(json_str):
            truncation_info['type'] = 'array_truncation'
            open_brackets = json_str.count('[')
            close_brackets = json_str.count(']')
            truncation_info['missing_chars'] = [']'] * (open_brackets - close_brackets)
        
        # 获取截断位置的上下文
        if len(json_str) > 100:
            truncation_info['context'] = json_str[-100:]
        
        return truncation_info
    
    def _is_string_truncation(self, json_str: str) -> bool:
        """检查是否为字符串截断"""
        # 查找未闭合的字符串
        in_string = False
        escape_next = False
        
        for i, char in enumerate(json_str):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
        
        # 如果最后仍在字符串中，说明字符串被截断
        return in_string
    
    def _is_object_truncation(self, json_str: str) -> bool:
        """检查是否为对象截断"""
        return json_str.count('{') > json_str.count('}')
    
    def _is_array_truncation(self, json_str: str) -> bool:
        """检查是否为数组截断"""
        return json_str.count('[') > json_str.count(']')
    
    def _repair_string_truncation(self, json_str: str, truncation_info: Dict) -> Optional[Dict]:
        """修复字符串截断"""
        logger.debug("修复字符串截断...")
        
        # 添加缺失的引号
        repaired = json_str + '"'
        
        # 检查是否还需要其他修复
        if self._is_object_truncation(repaired):
            open_braces = repaired.count('{')
            close_braces = repaired.count('}')
            repaired += '}' * (open_braces - close_braces)
        
        if self._is_array_truncation(repaired):
            open_brackets = repaired.count('[')
            close_brackets = repaired.count(']')
            repaired += ']' * (open_brackets - close_brackets)
        
        # 清理尾随逗号
        repaired = self._clean_trailing_commas(repaired)
        
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None
    
    def _repair_object_truncation(self, json_str: str, truncation_info: Dict) -> Optional[Dict]:
        """修复对象截断"""
        logger.debug("修复对象截断...")
        
        # 添加缺失的大括号
        missing_braces = truncation_info['missing_chars']
        repaired = json_str + ''.join(missing_braces)
        
        # 清理尾随逗号
        repaired = self._clean_trailing_commas(repaired)
        
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None
    
    def _repair_array_truncation(self, json_str: str, truncation_info: Dict) -> Optional[Dict]:
        """修复数组截断"""
        logger.debug("修复数组截断...")
        
        # 添加缺失的方括号
        missing_brackets = truncation_info['missing_chars']
        repaired = json_str + ''.join(missing_brackets)
        
        # 清理尾随逗号
        repaired = self._clean_trailing_commas(repaired)
        
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None
    
    def _repair_general_truncation(self, json_str: str) -> Optional[Dict]:
        """通用截断修复"""
        logger.debug("通用截断修复...")
        
        # 尝试从后往前找到最后一个可能的完整结构
        for i in range(len(json_str), 0, -1):
            candidate = json_str[:i]
            
            # 尝试补全结构
            if candidate.count('{') > candidate.count('}'):
                candidate += '}' * (candidate.count('{') - candidate.count('}'))
            
            if candidate.count('[') > candidate.count(']'):
                candidate += ']' * (candidate.count('[') - candidate.count(']'))
            
            # 修复可能的字符串截断
            if self._is_string_truncation(candidate):
                candidate += '"'
            
            # 清理尾随逗号
            candidate = self._clean_trailing_commas(candidate)
            
            try:
                result = json.loads(candidate)
                logger.info(f"通用截断修复成功，从{len(json_str)}截断到{len(candidate)}")
                return result
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _try_segment_parse(self, response: str) -> Optional[Dict]:
        """策略5: 分段提取解析 - 尝试提取部分有效数据"""
        logger.debug("开始分段提取解析...")
        
        # 尝试提取entities数组
        entities = self._extract_entities_array(response)
        
        # 尝试提取relations数组
        relations = self._extract_relations_array(response)
        
        if entities is not None or relations is not None:
            result = {
                "entities": entities or [],
                "relations": relations or [],
                "_partial_parse": True
            }
            # 异常16修复：记录解析成功的详细信息
            entities_count = len(entities or [])
            relations_count = len(relations or [])
            logger.info(f"策略5成功: 分段提取解析 - {entities_count}个实体, {relations_count}个关系")
            return result
        
        return None
    
    def _extract_entities_array(self, response: str) -> Optional[List]:
        """提取entities数组"""
        # 查找entities字段
        pattern = r'"entities"\s*:\s*\[(.*?)\]'
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            entities_str = '[' + match.group(1) + ']'
            try:
                return json.loads(entities_str)
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _extract_relations_array(self, response: str) -> Optional[List]:
        """提取relations数组"""
        # 查找relations字段
        pattern = r'"relations"\s*:\s*\[(.*?)\]'
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            relations_str = '[' + match.group(1) + ']'
            try:
                return json.loads(relations_str)
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _try_pattern_extraction(self, response: str) -> Optional[Dict]:
        """策略6: 模式匹配提取 - 使用正则表达式提取关键信息"""
        logger.debug("开始模式匹配提取...")
        
        entities = []
        relations = []
        
        # 提取实体模式
        entity_patterns = [
            r'"entity_id"\s*:\s*(\d+).*?"entity_name"\s*:\s*"([^"]*)".*?"type"\s*:\s*"([^"]*)"',
            r'"id"\s*:\s*(\d+).*?"name"\s*:\s*"([^"]*)".*?"type"\s*:\s*"([^"]*)"'
        ]
        
        for pattern in entity_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for match in matches:
                entity = {
                    "entity_id": int(match[0]),
                    "entity_name": match[1],
                    "type": match[2],
                    "confidence": 1.0,
                    "occurrence_count": 1
                }
                entities.append(entity)
        
        # 提取关系模式
        relation_patterns = [
            r'"relation_name"\s*:\s*"([^"]*)".*?"head_entity"\s*:\s*"([^"]*)".*?"tail_entity"\s*:\s*"([^"]*)"'
        ]
        
        for pattern in relation_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for match in matches:
                relation = {
                    "relation_name": match[0],
                    "head_entity": match[1],
                    "tail_entity": match[2]
                }
                relations.append(relation)
        
        if entities or relations:
            result = {
                "entities": entities,
                "relations": relations,
                "_pattern_extracted": True
            }
            logger.info(f"策略6成功: 模式匹配提取 - {len(entities)}个实体, {len(relations)}个关系")
            return result
        
        return None
    
    def _extract_json_content(self, response: str) -> Optional[str]:
        """提取JSON内容"""
        # 优先提取markdown代码块
        json_pattern = r'```(?:json)?\s*(.*?)\s*```'
        match = re.search(json_pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # 寻找JSON对象边界
        start_pos = response.find('{')
        if start_pos == -1:
            return None
        
        # 从开始位置到最后一个可能的结束位置
        end_pos = response.rfind('}')
        if end_pos > start_pos:
            return response[start_pos:end_pos + 1]
        
        # 如果没找到结束括号，返回从开始到结尾
        return response[start_pos:]
    
    def _clean_trailing_commas(self, json_str: str) -> str:
        """清理尾随逗号"""
        # 清理对象中的尾随逗号
        json_str = re.sub(r',\s*}', '}', json_str)
        # 清理数组中的尾随逗号
        json_str = re.sub(r',\s*]', ']', json_str)
        return json_str
    
    def _log_parse_failure(self, response: str):
        """记录解析失败的详细信息"""
        logger.error("=== JSON解析失败详细信息 ===")
        logger.error(f"响应总长度: {len(response)}")
        logger.error(f"响应前500字符: {response[:500]}")
        logger.error(f"响应后500字符: {response[-500:]}")
        
        # 查找可能的JSON标记
        markers = ['{', '}', '[', ']', '"entities"', '"relations"', '```json', '```']
        logger.error("JSON标记位置:")
        for marker in markers:
            if marker in response:
                positions = [i for i, char in enumerate(response) if response[i:i+len(marker)] == marker]
                logger.error(f"  {marker}: {positions[:5]}...")  # 只显示前5个位置
        
        # 统计字符
        stats = {
            'open_braces': response.count('{'),
            'close_braces': response.count('}'),
            'open_brackets': response.count('['),
            'close_brackets': response.count(']'),
            'quotes': response.count('"')
        }
        logger.error(f"字符统计: {stats}")

def create_fallback_structure(data_type: str) -> Dict[str, Any]:
    """创建兜底数据结构"""
    if data_type == "entities":
        return {
            "entities": [],
            "_fallback": True,
            "_error": "实体识别JSON解析失败"
        }
    elif data_type == "relations":
        return {
            "relations": [],
            "_fallback": True,
            "_error": "关系抽取JSON解析失败"
        }
    else:
        return {
            "entities": [],
            "relations": [],
            "_fallback": True,
            "_error": "通用JSON解析失败"
        }