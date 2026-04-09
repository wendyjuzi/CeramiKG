#!/usr/bin/env python3
"""
JSON数据校验和修复工具 - 异常12修复核心
解决MongoDB数据存储、后端API返回、前端数据传输的JSON格式问题
"""

import json
import re
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, date
from bson import ObjectId
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

class JSONValidator:
    """JSON数据校验和修复工具"""
    
    @staticmethod
    def is_valid_json(data: Any) -> bool:
        """检查数据是否为有效JSON格式"""
        try:
            if isinstance(data, str):
                json.loads(data)
            else:
                json.dumps(data)
            return True
        except (json.JSONDecodeError, TypeError, ValueError):
            return False
    
    @staticmethod
    def sanitize_for_json(data: Any) -> Any:
        """清理数据以确保JSON序列化兼容性"""
        if data is None:
            return None
        
        # 处理MongoDB ObjectId
        if isinstance(data, ObjectId):
            return str(data)
        
        # 处理日期时间对象
        if isinstance(data, (datetime, date)):
            return data.isoformat()
        
        # 处理字典
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # 确保键是字符串
                clean_key = str(key)
                sanitized[clean_key] = JSONValidator.sanitize_for_json(value)
            return sanitized
        
        # 处理列表
        if isinstance(data, (list, tuple)):
            return [JSONValidator.sanitize_for_json(item) for item in data]
        
        # 处理其他类型
        if isinstance(data, (int, float, bool)):
            return data
        
        # 字符串处理
        if isinstance(data, str):
            return data
        
        # 其他对象转换为字符串
        return str(data)
    
    @staticmethod
    def repair_malformed_json_string(json_str: str) -> str:
        """修复格式损坏的JSON字符串"""
        if not isinstance(json_str, str):
            return json.dumps(json_str)
        
        # 移除非JSON前缀和后缀
        json_str = json_str.strip()
        
        # 处理Python dict/list字符串表示
        if json_str.startswith("{'") or json_str.startswith('{"'):
            # 尝试使用ast.literal_eval解析Python字典
            try:
                import ast
                parsed = ast.literal_eval(json_str)
                return json.dumps(parsed, ensure_ascii=False)
            except (ValueError, SyntaxError):
                pass
        
        # 修复常见的JSON格式问题
        fixes = [
            # 将单引号替换为双引号
            (r"'([^']*)':", r'"\1":'),
            # 修复Python None -> null
            (r'\bNone\b', 'null'),
            # 修复Python True/False -> true/false
            (r'\bTrue\b', 'true'),
            (r'\bFalse\b', 'false'),
            # 移除尾随逗号
            (r',(\s*[}\]])', r'\1'),
            # 修复缺少的逗号：对象之间
            (r'}(\s*)(\{)', r'},\1\2'),
            # 修复缺少的逗号：数组中对象之间
            (r'}(\s+)(\{)', r'},\1\2'),
            # 修复缺少的逗号：数组元素之间（数字、字符串等）
            (r'(["\d\]\}])(\s+)(["\d\[\{])', r'\1,\2\3'),
        ]
        
        for pattern, replacement in fixes:
            json_str = re.sub(pattern, replacement, json_str)
        
        return json_str
    
    @staticmethod
    def safe_json_loads(json_str: str) -> Tuple[Optional[Any], Optional[str]]:
        """安全的JSON解析，返回(结果, 错误信息)"""
        if not isinstance(json_str, str):
            return None, "输入不是字符串"
        
        # 尝试直接解析
        try:
            return json.loads(json_str), None
        except json.JSONDecodeError as e:
            logger.debug(f"直接JSON解析失败: {e}")
        
        # 尝试修复后解析
        try:
            repaired = JSONValidator.repair_malformed_json_string(json_str)
            result = json.loads(repaired)
            return result, None
        except json.JSONDecodeError as e:
            return None, f"JSON格式错误: {e}"
        except Exception as e:
            return None, f"未知错误: {e}"
    
    @staticmethod
    def safe_json_dumps(data: Any, **kwargs) -> str:
        """安全的JSON序列化"""
        try:
            # 先清理数据
            sanitized = JSONValidator.sanitize_for_json(data)
            
            # 设置默认参数
            default_kwargs = {
                'ensure_ascii': False,
                'separators': (',', ':'),
                'default': str
            }
            default_kwargs.update(kwargs)
            
            return json.dumps(sanitized, **default_kwargs)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON序列化失败: {e}")
            # 最后的兜底方案
            try:
                return json.dumps(str(data), ensure_ascii=False)
            except:
                return '{"error": "数据无法序列化"}'
    
    @staticmethod
    def validate_and_fix_document_json_data(json_data: Any) -> Dict[str, Any]:
        """验证和修复文档的json_data字段"""
        result = {
            'original_type': type(json_data).__name__,
            'is_valid': False,
            'fixed_data': None,
            'error_message': None,
            'repair_actions': []
        }
        
        try:
            # 情况1: 已经是有效的Python对象
            if isinstance(json_data, (dict, list)):
                # 验证是否可以JSON序列化
                test_json = JSONValidator.safe_json_dumps(json_data)
                parsed_back, error = JSONValidator.safe_json_loads(test_json)
                
                if error is None:
                    result['is_valid'] = True
                    result['fixed_data'] = parsed_back
                    result['repair_actions'].append('数据已清理并验证')
                else:
                    result['fixed_data'] = JSONValidator.sanitize_for_json(json_data)
                    result['repair_actions'].append('数据已清理但需要进一步处理')
            
            # 情况2: 是字符串，尝试解析
            elif isinstance(json_data, str):
                parsed, error = JSONValidator.safe_json_loads(json_data)
                
                if error is None:
                    result['is_valid'] = True
                    result['fixed_data'] = parsed
                    result['repair_actions'].append('字符串成功解析为JSON')
                else:
                    result['error_message'] = error
                    result['fixed_data'] = {'content': json_data}
                    result['repair_actions'].append('字符串无法解析，包装为content字段')
            
            # 情况3: 其他类型
            else:
                result['fixed_data'] = JSONValidator.sanitize_for_json(json_data)
                result['repair_actions'].append(f'将{type(json_data).__name__}类型转换为JSON兼容格式')
        
        except Exception as e:
            result['error_message'] = f"处理过程中出现错误: {e}"
            result['fixed_data'] = {'error': '数据处理失败', 'original': str(json_data)}
            result['repair_actions'].append('使用兜底方案包装数据')
        
        return result
    
    @staticmethod
    def create_fastapi_safe_response(data: Any) -> Any:
        """创建FastAPI安全的响应数据"""
        try:
            # 使用FastAPI的jsonable_encoder进行编码
            encoded = jsonable_encoder(data)
            
            # 再次验证
            test_json = json.dumps(encoded)
            json.loads(test_json)  # 验证可以解析
            
            return encoded
        except Exception as e:
            logger.error(f"创建FastAPI响应失败: {e}")
            # 兜底方案
            return {"error": "响应数据格式化失败", "message": str(e)}
    
    @staticmethod
    def diagnose_json_error(json_str: str, error_pos: int = -1) -> Dict[str, Any]:
        """诊断JSON错误并提供修复建议"""
        diagnosis = {
            'error_position': error_pos,
            'context_before': '',
            'context_after': '',
            'likely_issues': [],
            'fix_suggestions': []
        }
        
        if not isinstance(json_str, str) or len(json_str) == 0:
            diagnosis['likely_issues'].append('空字符串或非字符串输入')
            return diagnosis
        
        # 获取错误位置上下文
        if error_pos > 0 and error_pos < len(json_str):
            start = max(0, error_pos - 50)
            end = min(len(json_str), error_pos + 50)
            diagnosis['context_before'] = json_str[start:error_pos]
            diagnosis['context_after'] = json_str[error_pos:end]
        
        # 分析常见问题
        issues = []
        fixes = []
        
        # 检查引号问题
        if "'" in json_str:
            issues.append('包含单引号')
            fixes.append('将单引号替换为双引号')
        
        # 检查Python特有的值
        if 'None' in json_str:
            issues.append('包含Python None值')
            fixes.append('将None替换为null')
        
        if 'True' in json_str or 'False' in json_str:
            issues.append('包含Python布尔值')
            fixes.append('将True/False替换为true/false')
        
        # 检查尾随逗号
        if re.search(r',\s*[}\]]', json_str):
            issues.append('包含尾随逗号')
            fixes.append('移除对象/数组末尾的多余逗号')
        
        # 检查缺少引号的键
        if re.search(r'[{,]\s*\w+\s*:', json_str):
            issues.append('对象键未加引号')
            fixes.append('为对象键添加双引号')
        
        diagnosis['likely_issues'] = issues
        diagnosis['fix_suggestions'] = fixes
        
        return diagnosis

# 工具函数
def validate_json_field(data: Any, field_name: str = 'json_data') -> Dict[str, Any]:
    """验证单个JSON字段"""
    return JSONValidator.validate_and_fix_document_json_data(data)

def safe_serialize(data: Any) -> str:
    """安全序列化数据为JSON字符串"""
    return JSONValidator.safe_json_dumps(data)

def safe_deserialize(json_str: str) -> Tuple[Any, Optional[str]]:
    """安全反序列化JSON字符串"""
    return JSONValidator.safe_json_loads(json_str)