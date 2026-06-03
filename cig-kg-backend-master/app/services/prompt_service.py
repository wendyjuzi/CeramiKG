import json
import re
import openai
from typing import Dict, List, Any, Optional
from app.config import settings
from app.models.schemas import Document, Term, Entity, Relation, EntityPosition
from app.utils.robust_json_parser import RobustJSONParser, create_fallback_structure
import logging

logger = logging.getLogger(__name__)

class PromptService:
    def __init__(self):
        """初始化 PromptService"""
        # 异常15修复：初始化强健JSON解析器
        self.json_parser = RobustJSONParser()
        # 通用实体识别提示词（无术语时使用）
        self.general_entity_prompt_template = """
你是一位专业的卷烟工业知识抽取专家。请识别以下文本中的所有重要实体，并返回详细的实体信息。

## 识别重点：
优先识别以下类型的实体：
1. **设备实体**：机械设备、生产设备、测量仪器、控制装置等
2. **工艺实体**：生产工艺、操作步骤、技术方法等  
3. **产品实体**：卷烟品牌、原材料、半成品、成品等
4. **人员实体**：操作工、技术人员、管理人员等
5. **部门机构**：生产车间、质检部门、管理部门等
6. **技术指标**：温度、湿度、压力、速度、质量标准等
7. **时间地点**：具体时间、生产地点、存储位置等

## 任务要求：
1. 仔细分析文档内容，识别出所有有意义的实体
2. 为每个实体分配唯一的递增ID（从1开始）
3. 准确标注实体在文档中的位置信息（字符位置）
4. 统计实体在文档中的出现次数
5. 根据上下文信息评估识别置信度（0-1之间，保留2位小数）
6. 尽可能识别实体的属性信息（如规格、型号、参数等）

## 文档内容：
{document_content}

## 输出格式：
**重要**：请直接返回纯JSON格式，不要使用markdown代码块标记（如```json），不要添加任何解释文字：
{{
  "entities": [
    {{
      "entity_id": 1,
      "entity_name": "实体名称",
      "type": "实体类型",
      "attributes": {{
        "属性名": "属性值"
      }},
      "description": "实体的详细描述和用途",
      "confidence": 0.95,
      "position": [
        {{
          "start": 10,
          "end": 15,
          "context": "包含该实体的上下文片段"
        }}
      ],
      "occurrence_count": 2
    }}
  ]
}}

请开始实体识别，直接返回JSON：
"""

        # 基于术语的实体识别提示词（有术语时使用）
        self.term_based_entity_prompt_template = """
你是一位专业的卷烟工业知识抽取专家。请从文档中识别实体，重点关注用户指定的术语实体，同时识别其他重要实体。

## 识别策略：
1. **优先识别**：术语库中指定的实体（这些是用户关注的重点实体）
2. **全面识别**：文档中出现的其他重要实体
3. **精确匹配**：对术语库中的实体名称进行精确匹配和变形匹配
4. **上下文分析**：结合上下文判断实体的准确含义和类型

## 用户指定的重要术语实体（必须优先识别）：
{entity_terms}

## 识别要求：
1. 仔细分析文档内容，首先查找术语库中的实体
2. 对于术语库实体，即使在文档中以不同形式出现也要识别出来
3. 为每个实体分配唯一的递增ID（从1开始）
4. 准确标注实体在文档中的位置信息（字符位置）
5. 统计实体的出现次数（包括同义词和变形）
6. 根据匹配程度和上下文评估置信度（0-1之间，保留2位小数）
7. 尽可能提取实体的属性信息和详细描述

## 文档内容：
{document_content}

## 输出格式：
**重要**：请直接返回纯JSON格式，不要使用markdown代码块标记（如```json），不要添加任何解释文字：
{{
  "entities": [
    {{
      "entity_id": 1,
      "entity_name": "实体名称",
      "type": "实体类型",
      "attributes": {{
        "属性名": "属性值"
      }},
      "description": "实体的详细描述和用途",
      "confidence": 0.95,
      "position": [
        {{
          "start": 10,
          "end": 15,
          "context": "包含该实体的上下文片段"
        }}
      ],
      "occurrence_count": 2
    }}
  ]
}}

请开始实体识别，直接返回JSON：
"""

        # 通用关系抽取提示词（无术语选择时使用）
        self.general_relation_prompt_template = """
你是一位专业的关系抽取专家。请从以下文本中抽取所有关系，尽可能识别出实体之间的各种关系。

## 任务要求：
1. 分析已识别的实体列表
2. 识别实体之间的所有可能关系
3. 确保关系的头实体和尾实体都在给定的实体列表中
4. 为每个关系分配唯一的递增ID和relation_id

## 已识别的实体：
{entities_list}

## 文档内容：
{document_content}

## 输出格式：
每条关系需要包含以下字段：
- id（序号）
- relation_id  
- relation_name
- head_entity
- tail_entity

**重要**：请直接返回纯JSON格式，不要使用markdown代码块标记（如```json），不要添加任何解释文字：
{{
  "relations": [
    {{
      "id": 1,
      "relation_id": "rel_001",
      "relation_name": "关系名称",
      "head_entity": "头实体名称",
      "tail_entity": "尾实体名称"
    }}
  ]
}}

请开始关系抽取，直接返回JSON：
"""

        # 基于术语的关系抽取提示词（有术语选择时使用）
        self.term_based_relation_prompt_template = """
你是一位专业的关系抽取专家。请从以下文本中抽取所有关系，特别是与以下术语相关的关系。

## 任务要求：
1. 分析已识别的实体列表
2. **优先识别**：术语库中指定的关系（这些是用户关注的重点关系）
3. **全面识别**：实体之间的其他重要关系
4. 确保关系的头实体和尾实体都在给定的实体列表中
5. 为每个关系分配唯一的递增ID和relation_id

## 已识别的实体：
{entities_list}

## 用户指定的重要关系术语：
{relation_terms}

## 文档内容：
{document_content}

## 输出格式：
每条关系需要包含以下字段：
- id（序号）
- relation_id
- relation_name  
- head_entity
- tail_entity

**重要**：请直接返回纯JSON格式，不要使用markdown代码块标记（如```json），不要添加任何解释文字：
{{
  "relations": [
    {{
      "id": 1,
      "relation_id": "rel_001", 
      "relation_name": "关系名称",
      "head_entity": "头实体名称",
      "tail_entity": "尾实体名称"
    }}
  ]
}}

请开始关系抽取，直接返回JSON：
"""
    
    def _build_entity_terms_text(self, terms: List[Term]) -> str:
        """构建实体术语文本"""
        entity_terms = [term for term in terms if term.type == "实体"]
        if not entity_terms:
            return "暂无实体类型定义"
        
        terms_text = []
        for term in entity_terms:
            term_desc = f"- {term.name}"
            if term.description:
                term_desc += f": {term.description}"
            terms_text.append(term_desc)
        
        return "\n".join(terms_text)
    
    def _build_relation_terms_text(self, terms: List[Term]) -> str:
        """构建关系术语文本"""
        relation_terms = [term for term in terms if term.type == "关系"]
        if not relation_terms:
            return "暂无关系类型定义"
        
        terms_text = []
        for term in relation_terms:
            term_desc = f"- {term.name}"
            if term.description:
                term_desc += f": {term.description}"
            terms_text.append(term_desc)
        
        return "\n".join(terms_text)
    
    def _build_entities_list_text(self, entities: List[Entity]) -> str:
        """构建实体列表文本"""
        if not entities:
            return "暂无已识别的实体"
        
        entities_text = []
        for entity in entities:
            entity_desc = f"- ID: {entity.entity_id}, 名称: {entity.entity_name}"
            if entity.type:
                entity_desc += f", 类型: {entity.type}"
            entities_text.append(entity_desc)
        
        return "\n".join(entities_text)

    def _extract_json_from_response(self, response: str, data_type: str = "general") -> Dict[str, Any]:
        """
        从LLM响应中提取JSON数据 (异常33修复)
        
        使用高级JSON解析器，支持更多容错机制：
        1. 直接解析
        2. JSONDecoder搜索
        3. 控制字符清理
        4. 引号规范化
        5. 反斜线转义修复
        6. 尾随逗号删除
        7. 平衡子串提取
        8. 片段提取
        """
        logger.debug("开始使用高级JSON解析器提取JSON (异常33)")
        
        # 使用新的高级JSON解析器
        from app.utils.advanced_json_parser import safe_extract_json_from_response
        
        try:
            result = safe_extract_json_from_response(response, data_type)
            return result
            
        except Exception as e:
            logger.error(f"高级JSON解析器异常: {e}")
            # 使用旧解析器作为兜底
            return self._legacy_extract_json_from_response(response, data_type)
    
    def _legacy_extract_json_from_response(self, response: str, data_type: str = "general") -> Dict[str, Any]:
        """
        旧版JSON解析器（兜底方案）
        """
        logger.debug("使用旧版JSON解析器作为兜底")
        
        from app.utils.robust_json_parser import create_fallback_structure
        
        if not response or not response.strip():
            logger.warning("LLM响应为空，返回兜底结构")
            return create_fallback_structure(data_type)
        
        # 使用旧版强健的JSON解析器
        try:
            # 根据数据类型创建兜底结构
            fallback = create_fallback_structure(data_type)
            result = self.json_parser.parse(response, fallback)
            
            # 检查是否是兜底结构
            if result.get("_fallback") or result.get("_parse_error"):
                logger.warning(f"旧版JSON解析使用了兜底策略: {result.get('_error', 'unknown')}")
            elif result.get("_partial_parse"):
                logger.info("旧版JSON解析成功但是部分解析")
            elif result.get("_pattern_extracted"):
                logger.info("旧版JSON解析通过模式匹配成功")
            else:
                logger.info("旧版JSON解析完全成功")
            
            return result
            
        except Exception as e:
            logger.error(f"旧版强健JSON解析器异常: {e}")
            # 最终兜底
            return create_fallback_structure(data_type)
    
    def _repair_json(self, response: str) -> str:
        """
        自动修复损坏的JSON格式 (异常10&11修复)
        
        处理常见的JSON损坏类型:
        1. 缺少逗号分隔符
        2. 未结束的字符串
        3. 未闭合的括号
        4. JSON截断
        5. 转义问题
        6. 基于字符位置的精确修复 (异常11增强)
        """
        logger.debug(f"开始JSON修复，原始长度: {len(response)}")
        
        # 预处理：提取可能的JSON内容
        json_content = self._extract_potential_json(response)
        if not json_content:
            logger.debug("未找到潜在的JSON内容")
            return None
        
        logger.debug(f"提取到潜在JSON内容，长度: {len(json_content)}")
        
        # 尝试直接解析，获取具体错误信息
        try:
            json.loads(json_content)
            logger.debug("JSON无需修复，直接返回")
            return json_content
        except json.JSONDecodeError as e:
            logger.debug(f"JSON解析错误: {e}")
            error_pos = getattr(e, 'pos', -1)
            error_msg = str(e)
            
            # 根据具体错误类型进行针对性修复
            if error_pos > 0:
                logger.debug(f"尝试基于错误位置 {error_pos} 进行精确修复")
                precise_repaired = self._precise_position_repair(json_content, error_pos, error_msg)
                if precise_repaired:
                    try:
                        json.loads(precise_repaired)
                        logger.info("基于位置的精确修复成功")
                        return precise_repaired
                    except json.JSONDecodeError:
                        logger.debug("精确修复失败，继续常规修复")
        
        # 应用多种修复策略 (按优化后的顺序)
        repaired_json = json_content
        
        # 策略1: 修复未闭合的字符串 (优先处理，因为影响后续解析)
        repaired_json = self._fix_unterminated_strings(repaired_json)
        
        # 策略2: 修复缺少的逗号 (第二优先，结构完整性)
        repaired_json = self._fix_missing_commas(repaired_json)
        
        # 策略3: 修复未闭合的括号 (结构完整性)
        repaired_json = self._fix_unclosed_brackets(repaired_json)
        
        # 策略4: 清理多余的逗号 (格式规范化)
        repaired_json = self._clean_trailing_commas(repaired_json)
        
        # 策略5: 修复转义问题 (最后处理，避免影响其他修复)
        repaired_json = self._fix_escape_issues(repaired_json)
        
        logger.debug(f"JSON修复完成，修复后长度: {len(repaired_json)}")
        
        # 验证修复结果
        try:
            json.loads(repaired_json)
            logger.info("JSON修复验证成功")
            return repaired_json
        except json.JSONDecodeError as e:
            logger.error(f"JSON修复验证失败: {e}")
            # 尝试截断策略
            return self._try_truncation_repair(repaired_json)
    
    def _extract_potential_json(self, response: str) -> str:
        """提取潜在的JSON内容"""
        response = response.strip()
        
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
    
    def _fix_unterminated_strings(self, json_str: str) -> str:
        """修复未结束的字符串"""
        logger.debug("修复未结束字符串...")
        
        # 更智能的字符串修复策略
        # 1. 查找明显的未结束字符串模式
        # 例如: "text": "some text, (缺少闭合引号，然后是逗号或换行)
        pattern = r'(":\s*"[^"]*)(,|\n|\s*\})'
        
        def fix_string_match(match):
            content = match.group(1)  # "text": "some text
            separator = match.group(2)  # , 或 \n 或 }
            
            # 如果字符串内容没有闭合引号，添加它
            if content.count('"') % 2 == 1:  # 奇数个引号，说明未闭合
                return content + '"' + separator
            return match.group(0)  # 不修改
        
        json_str = re.sub(pattern, fix_string_match, json_str)
        
        # 2. 处理行末未闭合的字符串
        lines = json_str.split('\n')
        fixed_lines = []
        
        for line in lines:
            # 检查这一行是否有未闭合的字符串
            in_string = False
            escape_next = False
            quote_count = 0
            
            for char in line:
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\':
                    escape_next = True
                    continue
                if char == '"':
                    quote_count += 1
            
            # 如果引号数量为奇数，且行末不是引号，可能需要修复
            if quote_count % 2 == 1 and not line.rstrip().endswith('"'):
                # 查找是否是字符串值的行
                if '":' in line and line.count('"') >= 3:
                    line = line.rstrip() + '"'
                    logger.debug(f"修复行末未闭合字符串: {line[-20:]}")
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_missing_commas(self, json_str: str) -> str:
        """修复缺少的逗号分隔符"""
        logger.debug("修复缺少的逗号...")
        
        # 更精确的逗号修复策略
        # 1. 处理对象之间缺少逗号: } {  ->  }, {
        pattern1 = r'(\}\s*\n?\s*)(\{)'
        json_str = re.sub(pattern1, r'\1,\2', json_str)
        
        # 2. 处理数组元素之间缺少逗号: ] [  ->  ], [
        pattern2 = r'(\]\s*\n?\s*)(\[)'
        json_str = re.sub(pattern2, r'\1,\2', json_str)
        
        # 3. 处理对象属性和下一个对象之间的逗号
        # 匹配: value } 换行 { 的模式
        pattern3 = r'(\d+|"[^"]*"|\}|\])\s*\n\s*(\{)'
        json_str = re.sub(pattern3, r'\1,\n    \2', json_str)
        
        return json_str
    
    def _fix_unclosed_brackets(self, json_str: str) -> str:
        """修复未闭合的括号"""
        logger.debug("修复未闭合的括号...")
        
        # 计算括号平衡
        brace_count = 0
        bracket_count = 0
        in_string = False
        escape_next = False
        
        for char in json_str:
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
        
        # 添加缺失的闭合括号
        result = json_str
        if brace_count > 0:
            result += '}' * brace_count
            logger.debug(f"添加了{brace_count}个闭合大括号")
        
        if bracket_count > 0:
            result += ']' * bracket_count
            logger.debug(f"添加了{bracket_count}个闭合中括号")
        
        return result
    
    def _clean_trailing_commas(self, json_str: str) -> str:
        """清理多余的逗号"""
        logger.debug("清理多余的逗号...")
        
        # 移除对象最后一个属性后的逗号: , }
        json_str = re.sub(r',\s*}', '}', json_str)
        
        # 移除数组最后一个元素后的逗号: , ]
        json_str = re.sub(r',\s*]', ']', json_str)
        
        return json_str
    
    def _fix_escape_issues(self, json_str: str) -> str:
        """修复转义问题"""
        logger.debug("修复转义问题...")
        
        # 修复常见的转义问题
        # 双重转义: \\" -> \"
        json_str = json_str.replace('\\"', '"')
        
        # 修复路径分隔符: C:\path -> C:\\path (在字符串值中)
        # 这个比较复杂，需要谨慎处理
        
        return json_str
    
    def _try_truncation_repair(self, json_str: str) -> str:
        """尝试截断修复策略"""
        logger.debug("尝试截断修复...")
        
        # 从后往前查找最后一个完整的对象或数组
        for i in range(len(json_str) - 1, 0, -1):
            candidate = json_str[:i]
            
            # 尝试补全结构
            if candidate.count('{') > candidate.count('}'):
                candidate += '}' * (candidate.count('{') - candidate.count('}'))
            
            if candidate.count('[') > candidate.count(']'):
                candidate += ']' * (candidate.count('[') - candidate.count(']'))
            
            # 清理尾随逗号
            candidate = self._clean_trailing_commas(candidate)
            
            try:
                json.loads(candidate)
                logger.info(f"通过截断修复成功，从{len(json_str)}截断到{len(candidate)}")
                return candidate
            except json.JSONDecodeError:
                continue
        
        logger.error("截断修复也失败了")
        return None
    
    def _precise_position_repair(self, json_str: str, error_pos: int, error_msg: str) -> str:
        """
        基于具体错误位置进行精确修复 (异常11核心功能)
        
        参数:
        - json_str: 损坏的JSON字符串
        - error_pos: 错误发生的字符位置
        - error_msg: 错误信息
        """
        logger.debug(f"开始精确位置修复: 位置 {error_pos}, 错误: {error_msg}")
        
        if error_pos <= 0 or error_pos >= len(json_str):
            logger.debug("错误位置超出范围")
            return None
        
        # 获取错误位置的上下文
        context_start = max(0, error_pos - 100)
        context_end = min(len(json_str), error_pos + 100)
        context = json_str[context_start:context_end]
        error_char = json_str[error_pos] if error_pos < len(json_str) else ''
        
        logger.debug(f"错误位置 {error_pos} 字符: '{error_char}'")
        logger.debug(f"上下文: ...{context}...")
        
        # 根据错误类型进行精确修复
        if "Expecting ',' delimiter" in error_msg:
            return self._fix_comma_at_position(json_str, error_pos)
        elif "Unterminated string" in error_msg:
            return self._fix_string_at_position(json_str, error_pos)
        elif "Expecting property name" in error_msg:
            return self._fix_property_at_position(json_str, error_pos)
        elif "Extra data" in error_msg:
            return self._fix_extra_data_at_position(json_str, error_pos)
        else:
            logger.debug(f"未识别的错误类型: {error_msg}")
            return None
    
    def _fix_comma_at_position(self, json_str: str, pos: int) -> str:
        """在指定位置修复缺少的逗号"""
        logger.debug(f"修复位置 {pos} 的逗号问题")
        
        # 获取错误位置前后的字符
        before_char = json_str[pos-1] if pos > 0 else ''
        current_char = json_str[pos] if pos < len(json_str) else ''
        after_char = json_str[pos+1] if pos + 1 < len(json_str) else ''
        
        logger.debug(f"位置字符: '{before_char}' | '{current_char}' | '{after_char}'")
        
        # 策略1: 如果是 } { 模式，在中间插入逗号
        if before_char == '}' and current_char in ' \n\t':
            # 寻找后面的 {
            next_brace_pos = pos
            while next_brace_pos < len(json_str) and json_str[next_brace_pos] in ' \n\t':
                next_brace_pos += 1
            
            if next_brace_pos < len(json_str) and json_str[next_brace_pos] == '{':
                # 在 } 后插入逗号
                result = json_str[:pos] + ',' + json_str[pos:]
                logger.debug("在 } 后插入逗号")
                return result
        
        # 策略2: 如果是 ] [ 模式，在中间插入逗号  
        if before_char == ']' and current_char in ' \n\t':
            # 寻找后面的 [
            next_bracket_pos = pos
            while next_bracket_pos < len(json_str) and json_str[next_bracket_pos] in ' \n\t':
                next_bracket_pos += 1
                
            if next_bracket_pos < len(json_str) and json_str[next_bracket_pos] == '[':
                # 在 ] 后插入逗号
                result = json_str[:pos] + ',' + json_str[pos:]
                logger.debug("在 ] 后插入逗号")
                return result
        
        # 策略3: 在对象属性之间插入逗号
        # 寻找前面的属性结束和后面的属性开始
        if self._is_between_properties(json_str, pos):
            # 在当前位置插入逗号和换行
            result = json_str[:pos] + ',\n    ' + json_str[pos:]
            logger.debug("在对象属性间插入逗号")
            return result
        
        logger.debug("无法确定逗号插入位置")
        return None
    
    def _fix_string_at_position(self, json_str: str, pos: int) -> str:
        """在指定位置修复未结束的字符串"""
        logger.debug(f"修复位置 {pos} 的字符串问题")
        
        # 向前查找字符串开始位置
        string_start = -1
        for i in range(pos - 1, -1, -1):
            if json_str[i] == '"' and (i == 0 or json_str[i-1] != '\\'):
                string_start = i
                break
        
        if string_start == -1:
            logger.debug("未找到字符串开始位置")
            return None
        
        # 检查字符串是否真的未结束
        quote_count = 0
        for i in range(string_start + 1, min(pos + 50, len(json_str))):
            if json_str[i] == '"' and (i == 0 or json_str[i-1] != '\\'):
                quote_count += 1
        
        if quote_count % 2 == 1:
            # 字符串确实已经结束，可能是其他问题
            logger.debug("字符串已经正确结束")
            return None
        
        # 在合适的位置插入闭合引号
        # 寻找下一个逻辑分隔符 (逗号、换行、括号)
        insert_pos = pos
        for i in range(pos, min(pos + 100, len(json_str))):
            if json_str[i] in ',\n}]':
                insert_pos = i
                break
        
        # 在分隔符前插入引号
        result = json_str[:insert_pos] + '"' + json_str[insert_pos:]
        logger.debug(f"在位置 {insert_pos} 插入闭合引号")
        return result
    
    def _fix_property_at_position(self, json_str: str, pos: int) -> str:
        """修复属性名问题"""
        logger.debug(f"修复位置 {pos} 的属性名问题")
        
        # 这种错误通常出现在多余的逗号后
        # 检查是否是尾随逗号问题
        context = json_str[max(0, pos-20):pos+20]
        if ',\n' in context and ('}' in context or ']' in context):
            # 移除多余的逗号
            comma_pos = json_str.rfind(',', 0, pos)
            if comma_pos > 0:
                result = json_str[:comma_pos] + json_str[comma_pos+1:]
                logger.debug(f"移除位置 {comma_pos} 的多余逗号")
                return result
        
        return None
    
    def _fix_extra_data_at_position(self, json_str: str, pos: int) -> str:
        """修复额外数据问题"""
        logger.debug(f"修复位置 {pos} 的额外数据问题")
        
        # Extra data 通常意味着JSON在某处已经完整结束
        # 但后面还有多余内容，直接截断到该位置
        result = json_str[:pos].rstrip()
        logger.debug(f"截断到位置 {pos}")
        return result
    
    def _is_between_properties(self, json_str: str, pos: int) -> bool:
        """检查位置是否在两个对象属性之间"""
        # 向前查找，看是否有属性结束模式 (如 "value", 数字, true, false, null 等)
        before_context = json_str[max(0, pos-50):pos]
        after_context = json_str[pos:min(len(json_str), pos+50)]
        
        # 检查前面是否有属性值结束
        before_patterns = [r'"\s*$', r'\d+\s*$', r'true\s*$', r'false\s*$', r'null\s*$', r'}\s*$', r']\s*$']
        before_match = any(re.search(pattern, before_context) for pattern in before_patterns)
        
        # 检查后面是否有属性名开始
        after_patterns = [r'^\s*"[\w\s]+"\s*:', r'^\s*\n\s*"[\w\s]+"\s*:']
        after_match = any(re.search(pattern, after_context) for pattern in after_patterns)
        
        return before_match and after_match

   
    async def _call_llm_api(self, prompt: str) -> str:
        """调用千问API - 直接使用环境变量"""
        try:
            import os
            from openai import OpenAI
            
            # 直接从环境变量获取配置
            API_KEY = os.getenv("API_KEY", "")
            BASE_URL = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            MODEL_NAME = os.getenv("MODEL_NAME", "Qwen3.6-27B")
            
            # 添加调试信息
            logger.info(f"千问API调用开始:")
            logger.info(f"  环境变量 API_KEY: {API_KEY[:8] if API_KEY else 'None'}...")
            logger.info(f"  环境变量 BASE_URL: {BASE_URL}")
            logger.info(f"  环境变量 MODEL_NAME: {MODEL_NAME}")
            logger.info(f"  Prompt长度: {len(prompt)}")
            
            # 检查API_KEY是否有效
            if not API_KEY:
                logger.error("API_KEY为空！")
                raise ValueError("API_KEY is empty")
            
            # 创建 OpenAI 客户端（千问支持 OpenAI 兼容模式）
            client = OpenAI(
                api_key=API_KEY,
                base_url=BASE_URL,
                timeout=200
            )
            
            # 添加重试机制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"尝试第 {attempt + 1} 次调用...")
                    
                    response = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        extra_body={"enable_search": False}  # 可选：是否启用联网搜索
                    )
                    
                    result = response.choices[0].message.content.strip()
                    logger.info(f"API调用成功，返回长度: {len(result)}")
                    print(f"API调用成功，返回长度: {len(result)}")
                    return result
                    
                except Exception as e:
                    logger.warning(f"第 {attempt + 1} 次调用失败: {e}")
                    print(f"第 {attempt + 1} 次调用失败: {e}")
                    if attempt < max_retries - 1:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)  # 指数退避
                        continue
                    else:
                        raise
            
        except ImportError as e:
            logger.error(f"openai模块导入失败: {e}")
            logger.error("请安装: pip install openai")
            raise
        except Exception as e:
            logger.error(f"千问API调用失败: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"完整错误追踪:\n{traceback.format_exc()}")
            raise

    async def extract_entities(self, document: Document, terms: List[Term]) -> List[Entity]:
        """从文档中抽取实体"""
        try:
            # 过滤出实体类型的术语
            entity_terms = [term for term in terms if term.type == "实体"]
            
            # 根据是否有术语选择不同的提示词模板
            if not entity_terms:
                # 使用通用实体识别提示词
                prompt = self.general_entity_prompt_template.format(
                    document_content=document.content or ""
                )
                logger.info("使用通用实体识别模式")
            else:
                # 使用基于术语的实体识别提示词
                entity_terms_text = self._build_entity_terms_text(entity_terms)
                prompt = self.term_based_entity_prompt_template.format(
                    entity_terms=entity_terms_text,
                    document_content=document.content or ""
                )
                logger.info(f"使用术语驱动识别模式，术语数量: {len(entity_terms)}")
            
            # 调用LLM
            response = await self._call_llm_api(prompt)
            
            # 异常16修复：记录大模型原始返回数据
            logger.info(f"大模型原始返回长度: {len(response)}")
            logger.debug(f"大模型原始返回前1000字符: {response[:1000]}")
            if len(response) > 1000:
                logger.debug(f"大模型原始返回后500字符: {response[-500:]}")
            
            # 解析响应（异常15修复：使用强健JSON解析器）
            try:
                result = self._extract_json_from_response(response, "entities")
                
                # 异常16修复：记录JSON解析结果
                entities_count = len(result.get("entities", []))
                logger.info(f"JSON解析后entities数量: {entities_count}")
                if entities_count > 0:
                    logger.debug(f"解析后的前3个实体: {result.get('entities', [])[:3]}")
                else:
                    logger.warning(f"JSON解析后entities为空，完整result: {result}")
                entities = []
                
                for entity_data in result.get("entities", []):
                    # 解析位置信息
                    positions = []
                    if entity_data.get("position"):
                        for pos_data in entity_data["position"]:
                            position = EntityPosition(
                                start=pos_data.get("start", 0),
                                end=pos_data.get("end", 0),
                                context=pos_data.get("context", "")
                            )
                            positions.append(position)
                    
                    entity = Entity(
                        entity_id=entity_data.get("entity_id") or entity_data.get("id"),
                        entity_name=entity_data.get("entity_name") or entity_data.get("name", ""),
                        type=entity_data.get("type"),
                        attributes=entity_data.get("attributes", {}),
                        description=entity_data.get("description", ""),
                        confidence=float(entity_data.get("confidence", 1.0)),
                        position=positions if positions else None,
                        occurrence_count=entity_data.get("occurrence_count", len(positions))
                    )
                    entities.append(entity)
                
                logger.info(f"成功识别 {len(entities)} 个实体")
                return entities
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"解析LLM响应失败: {e}, 响应内容: {response[:500]}...")
                return []
                
        except Exception as e:
            logger.error(f"实体抽取失败: {e}")
            return []

    async def extract_relations(self, entities: List[Entity], terms: Optional[List[Term]] = None, document_content: Optional[str] = None) -> List[Relation]:
        """从实体列表中抽取关系（异常13修复 - 支持有术语和无术语两种场景）"""
        try:
            if not entities:
                return []
            
            # 构建实体列表文本
            entities_list_text = self._build_entities_list_text(entities)
            
            # 根据是否有术语选择不同的提示词模板
            if terms and any(term.type == "关系" for term in terms):
                # 有术语场景：使用基于术语的关系抽取提示词
                relation_terms_text = self._build_relation_terms_text(terms)
                prompt = self.term_based_relation_prompt_template.format(
                    entities_list=entities_list_text,
                    relation_terms=relation_terms_text,
                    document_content=document_content or ""
                )
                logger.info("使用基于术语的关系抽取模式")
            else:
                # 无术语场景：使用通用关系抽取提示词
                prompt = self.general_relation_prompt_template.format(
                    entities_list=entities_list_text,
                    document_content=document_content or ""
                )
                logger.info("使用通用关系抽取模式")
            
            # 调用LLM
            response = await self._call_llm_api(prompt)
            
            # 异常16修复：记录大模型原始返回数据（关系抽取）
            logger.info(f"关系抽取 - 大模型原始返回长度: {len(response)}")
            logger.debug(f"关系抽取 - 大模型原始返回前1000字符: {response[:1000]}")
            if len(response) > 1000:
                logger.debug(f"关系抽取 - 大模型原始返回后500字符: {response[-500:]}")
            
            # 解析响应（异常15修复：使用强健JSON解析器）
            try:
                result = self._extract_json_from_response(response, "relations")
                
                # 异常16修复：记录JSON解析结果（关系抽取）
                relations_count = len(result.get("relations", []))
                logger.info(f"关系抽取 - JSON解析后relations数量: {relations_count}")
                if relations_count > 0:
                    logger.debug(f"关系抽取 - 解析后的前3个关系: {result.get('relations', [])[:3]}")
                else:
                    logger.warning(f"关系抽取 - JSON解析后relations为空，完整result: {result}")
                relations = []
                
                # 创建实体名称到ID的映射
                entity_name_to_id = {entity.entity_name: entity.entity_id for entity in entities}
                
                for relation_data in result.get("relations", []):
                    # 支持新格式字段（head_entity, tail_entity）和旧格式字段（head_entity_name, tail_entity_name）
                    head_name = relation_data.get("head_entity", relation_data.get("head_entity_name", ""))
                    tail_name = relation_data.get("tail_entity", relation_data.get("tail_entity_name", ""))
                    
                    # 查找实体ID
                    head_id = entity_name_to_id.get(head_name)
                    tail_id = entity_name_to_id.get(tail_name)
                    
                    relation = Relation(
                        id=relation_data.get("id"),
                        relation_id=relation_data.get("relation_id", f"rel_{str(relation_data.get('id', 0)).zfill(3)}"),
                        relation_name=relation_data.get("relation_name", relation_data.get("name", "")),
                        head_entity=head_name,
                        tail_entity=tail_name,
                        # 保持向后兼容
                        head_entity_id=head_id,
                        head_entity_name=head_name,
                        tail_entity_id=tail_id,
                        tail_entity_name=tail_name
                    )
                    relations.append(relation)
                
                logger.info(f"成功抽取 {len(relations)} 个关系")
                return relations
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"解析LLM响应失败: {e}, 响应内容: {response[:500]}...")
                return []
                
        except Exception as e:
            logger.error(f"关系抽取失败: {e}")
            return []

    async def build_entity_prompt(self, document: Document, terms: List[Term]) -> str:
        """构建实体识别提示词"""
        entity_terms_text = self._build_entity_terms_text(terms)
        return self.entity_prompt_template.format(
            entity_terms=entity_terms_text,
            document_content=document.content or ""
        )
    
    async def build_relation_prompt(self, entities: List[Entity], terms: List[Term], document_content: Optional[str] = None) -> str:
        """构建关系抽取提示词"""
        entities_list_text = self._build_entities_list_text(entities)
        relation_terms_text = self._build_relation_terms_text(terms)
        return self.relation_prompt_template.format(
            entities_list=entities_list_text,
            relation_terms=relation_terms_text,
            document_content=document_content or ""
        )

