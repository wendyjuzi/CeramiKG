#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分块知识抽取服务 (Chunked Information Extraction)

按 page_idx 将文档分 chunk 逐个调用大模型进行实体识别与关系抽取，
并正确处理跨 chunk 被截断的实体与关系。

异常31修复 - 全面改造大模型调用与解析逻辑
"""

import json
import re
import uuid
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
from difflib import SequenceMatcher
import logging
from dataclasses import dataclass, field

from app.models.schemas import Document, Term, Entity, Relation, EntityPosition
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """文档分块"""
    page_idx: int
    text: str
    raw_data: List[Dict[str, Any]]  # 原始json_data中该页的所有项
    cleaned_text: str = ""  # 去除页眉页脚后的文本


@dataclass 
class EntityCandidate:
    """实体候选项（在合并前）"""
    entity_id: Optional[str] = None
    entity_name: str = ""
    entity_type: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    positions: List[Dict[str, Any]] = field(default_factory=list)
    occurrence_count: int = 0
    confidence: float = 1.0
    incomplete: bool = False
    source_page: int = -1
    normalized_name: str = ""


@dataclass
class RelationCandidate:
    """关系候选项（在合并前）"""
    relation_id: Optional[str] = None
    relation_name: str = ""
    head_entity_id: Optional[str] = None
    head_entity_name: str = ""
    tail_entity_id: Optional[str] = None
    tail_entity_name: str = ""
    description: Optional[str] = None
    evidence_text: Optional[str] = None
    positions: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    incomplete: bool = False
    source_page: int = -1


class EntityRegistry:
    """实体注册表 - 用于跨chunk合并"""
    
    def __init__(self):
        self.entities: Dict[str, EntityCandidate] = {}
        self.name_to_id: Dict[str, str] = {}
        self.id_counter = 1
        
    def _normalize_name(self, name: str) -> str:
        """标准化实体名称用于匹配"""
        if not name:
            return ""
        # 去除空格、统一小写、去除标点
        normalized = re.sub(r'\s+', '', name.strip().lower())
        normalized = re.sub(r'[^\w\u4e00-\u9fff]', '', normalized)
        return normalized
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """计算两个名称的相似度"""
        if not name1 or not name2:
            return 0.0
        
        # 精确匹配
        if name1 == name2:
            return 1.0
            
        # 标准化匹配
        norm1 = self._normalize_name(name1)
        norm2 = self._normalize_name(name2)
        if norm1 == norm2:
            return 0.95
            
        # 编辑距离相似度
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def find_matching_entity(self, candidate: EntityCandidate) -> Optional[str]:
        """查找匹配的已有实体ID"""
        best_match_id = None
        best_score = 0.0
        similarity_threshold = 0.8
        
        for entity_id, existing_entity in self.entities.items():
            # 名称相似度
            name_score = self._calculate_similarity(
                candidate.entity_name, existing_entity.entity_name
            )
            
            # 类型匹配加分
            type_bonus = 0.0
            if candidate.entity_type and existing_entity.entity_type:
                if candidate.entity_type == existing_entity.entity_type:
                    type_bonus = 0.1
            
            total_score = name_score + type_bonus
            
            if total_score > best_score and total_score >= similarity_threshold:
                best_score = total_score
                best_match_id = entity_id
                
        logger.debug(f"实体匹配结果 '{candidate.entity_name}': 最佳匹配 {best_match_id}, 分数 {best_score}")
        return best_match_id
    
    def add_or_merge_entity(self, candidate: EntityCandidate) -> str:
        """添加或合并实体，返回实体ID"""
        # 查找是否有匹配的实体
        existing_id = self.find_matching_entity(candidate)
        
        if existing_id:
            # 合并到现有实体
            existing = self.entities[existing_id]
            
            # 合并positions
            existing.positions.extend(candidate.positions)
            
            # 合并attributes（优先更高置信度的值）
            if candidate.attributes:
                if not existing.attributes:
                    existing.attributes = candidate.attributes.copy()
                else:
                    for key, value in candidate.attributes.items():
                        if (key not in existing.attributes or 
                            candidate.confidence > existing.confidence):
                            existing.attributes[key] = value
            
            # 更新其他字段（优先更高置信度或更完整的信息）
            if candidate.confidence > existing.confidence:
                if candidate.description:
                    existing.description = candidate.description
                if candidate.entity_type:
                    existing.entity_type = candidate.entity_type
            
            # 更新统计信息
            existing.occurrence_count += candidate.occurrence_count
            existing.confidence = max(existing.confidence, candidate.confidence)
            existing.incomplete = existing.incomplete and candidate.incomplete
            
            logger.debug(f"合并实体 '{candidate.entity_name}' 到 {existing_id}")
            return existing_id
        else:
            # 创建新实体
            entity_id = f"E-{str(self.id_counter).zfill(4)}"
            self.id_counter += 1
            
            candidate.entity_id = entity_id
            candidate.normalized_name = self._normalize_name(candidate.entity_name)
            
            self.entities[entity_id] = candidate
            self.name_to_id[candidate.normalized_name] = entity_id
            
            logger.debug(f"创建新实体 '{candidate.entity_name}' ID: {entity_id}")
            return entity_id


class RelationRegistry:
    """关系注册表 - 用于跨chunk合并"""

    def __init__(self, mysql_service=None, document_id=None):
        self.relations: Dict[str, RelationCandidate] = {}
        self.id_counter = 1
        self.mysql_service = mysql_service
        self.document_id = document_id
        
    def _create_relation_key(self, head_entity_id: Optional[str], tail_entity_id: Optional[str], relation_name: str) -> str:
        """创建关系的唯一键（异常37修复：处理None值）"""
        head_key = head_entity_id or "MISSING_HEAD"
        tail_key = tail_entity_id or "MISSING_TAIL"
        return f"{head_key}|{relation_name}|{tail_key}"
    
    def _find_entity_id_by_name(self, entity_name: str, entity_registry: EntityRegistry) -> Optional[str]:
        """通过实体名称查找实体ID（异常37修复：增强匹配逻辑）"""
        if not entity_name:
            return None
        
        # 1. 精确匹配（标准化后）
        norm_name = entity_registry._normalize_name(entity_name)
        if norm_name in entity_registry.name_to_id:
            return entity_registry.name_to_id[norm_name]
        
        # 2. 模糊匹配：查找包含关系
        entity_name_lower = entity_name.lower().strip()
        
        for existing_name, entity_id in entity_registry.name_to_id.items():
            existing_lower = existing_name.lower()
            
            # 检查是否存在包含关系
            if (entity_name_lower in existing_lower or 
                existing_lower in entity_name_lower):
                logger.debug(f"通过模糊匹配找到实体: '{entity_name}' -> '{existing_name}' (ID: {entity_id})")
                return entity_id
        
        # 3. 部分匹配：检查是否有相似的词汇
        entity_words = set(entity_name_lower.split())
        
        for existing_name, entity_id in entity_registry.name_to_id.items():
            existing_words = set(existing_name.lower().split())
            
            # 如果有共同词汇且相似度较高
            common_words = entity_words & existing_words
            if common_words and len(common_words) >= min(len(entity_words), len(existing_words)) * 0.5:
                logger.debug(f"通过部分匹配找到实体: '{entity_name}' -> '{existing_name}' (ID: {entity_id})")
                return entity_id
        
        logger.debug(f"无法找到实体名称 '{entity_name}' 对应的ID，注册表中的实体：{list(entity_registry.name_to_id.keys())[:5]}...")
        return None
    
    def add_or_merge_relation(self, candidate: RelationCandidate, entity_registry: EntityRegistry) -> Optional[str]:
        """添加或合并关系，返回关系ID（异常37修复：增强实体ID解析逻辑）"""
        # 解析实体ID
        head_id = candidate.head_entity_id
        tail_id = candidate.tail_entity_id
        
        # 如果没有实体ID，尝试通过名称查找
        if not head_id and candidate.head_entity_name:
            head_id = self._find_entity_id_by_name(candidate.head_entity_name, entity_registry)
            
        if not tail_id and candidate.tail_entity_name:
            tail_id = self._find_entity_id_by_name(candidate.tail_entity_name, entity_registry)
        
        # 异常37修复：更详细的实体ID解析日志
        if not head_id and candidate.head_entity_name:
            logger.warning(f"关系 '{candidate.relation_name}' 无法解析头实体名称 '{candidate.head_entity_name}' 到ID，注册表中有 {len(entity_registry.entities)} 个实体")
            
        if not tail_id and candidate.tail_entity_name:
            logger.warning(f"关系 '{candidate.relation_name}' 无法解析尾实体名称 '{candidate.tail_entity_name}' 到ID，注册表中有 {len(entity_registry.entities)} 个实体")
        
        # 如果仍然找不到实体ID，标记为incomplete但仍然处理
        if not head_id or not tail_id:
            candidate.incomplete = True
            logger.warning(f"关系 '{candidate.relation_name}' 缺少实体ID: head_id={head_id} (name={candidate.head_entity_name}), tail_id={tail_id} (name={candidate.tail_entity_name})")
            # 异常37修复：不直接返回None，而是继续处理，但标记为不完整
        
        # 异常37修复：即使部分信息缺失，也更新可用的实体ID
        if head_id:
            candidate.head_entity_id = head_id
        if tail_id:
            candidate.tail_entity_id = tail_id
        
        # 创建关系键
        relation_key = self._create_relation_key(head_id, tail_id, candidate.relation_name)
        
        if relation_key in self.relations:
            # 合并到现有关系
            existing = self.relations[relation_key]
            
            # 合并positions和证据文本
            existing.positions.extend(candidate.positions)
            if candidate.evidence_text:
                if existing.evidence_text:
                    existing.evidence_text += "; " + candidate.evidence_text
                else:
                    existing.evidence_text = candidate.evidence_text
                    
            # 更新描述（优先更高置信度）
            if candidate.confidence > existing.confidence and candidate.description:
                existing.description = candidate.description
                
            existing.confidence = max(existing.confidence, candidate.confidence)
            existing.incomplete = existing.incomplete and candidate.incomplete
            
            logger.debug(f"合并关系 '{candidate.relation_name}' key: {relation_key}")
            return existing.relation_id
        else:
            # 创建新关系
            # 注意：数据库层面已有UNIQUE约束(relation_id, head_entity_id, tail_entity_id)
            # 在save_relations_to_table时会使用ON DUPLICATE KEY UPDATE处理重复
            relation_id = f"R-{str(self.id_counter).zfill(4)}"
            self.id_counter += 1

            candidate.relation_id = relation_id
            self.relations[relation_key] = candidate

            logger.debug(f"创建新关系 '{candidate.relation_name}' ID: {relation_id}")
            return relation_id


class ChunkedIEService:
    """分块知识抽取服务"""

    def __init__(self, mysql_service=None):
        self.prompt_service = PromptService()
        self.mysql_service = mysql_service
        # 页眉页脚过滤规则
        self.header_footer_patterns = [
            r'^第\s*\d+\s*页',  # 第x页
            r'Page\s+\d+',     # Page x
            r'^\d+\s*$',       # 单独的页码
            r'^目录\s*$',      # 目录
            r'^.*\d{4}年\d{1,2}月.*$',  # 日期格式
        ]
        
    async def extract_chunked_knowledge(
        self, 
        document_id: str,
        json_data: List[Dict[str, Any]], 
        terms: Optional[List[Term]] = None
    ) -> Dict[str, Any]:
        """
        主要入口函数：按chunk提取知识
        
        Args:
            document_id: 文档ID
            json_data: MongoDB中的json_data字段
            terms: 可选的术语列表
            
        Returns:
            标准化的JSON格式: {"entities": [...], "relations": [...], "meta": {...}}
        """
        try:
            logger.info(f"开始分块知识抽取，文档ID: {document_id}")
            
            # 1. 文档分块
            chunks = self.get_chunks_from_json_data(json_data)
            logger.info(f"文档分块完成，共 {len(chunks)} 个chunk")
            
            # 2. 初始化注册表
            entity_registry = EntityRegistry()
            relation_registry = RelationRegistry(mysql_service=self.mysql_service, document_id=document_id)
            
            # 3. 逐chunk处理
            for i, chunk in enumerate(chunks):
                logger.info(f"处理chunk {i+1}/{len(chunks)}, page_idx: {chunk.page_idx}")
                
                # 3.1 实体抽取
                entities_result = await self.extract_entities_from_chunk(chunk, terms)
                
                # 3.2 处理实体结果
                chunk_entities = self._parse_entities_from_result(entities_result, chunk.page_idx)
                for entity_candidate in chunk_entities:
                    entity_registry.add_or_merge_entity(entity_candidate)
                
                # 3.3 关系抽取
                if chunk_entities:  # 只有当有实体时才进行关系抽取
                    relations_result = await self.extract_relations_from_chunk(
                        chunk, chunk_entities, terms
                    )
                    
                    # 3.4 处理关系结果
                    chunk_relations = self._parse_relations_from_result(relations_result, chunk.page_idx)
                    for relation_candidate in chunk_relations:
                        relation_registry.add_or_merge_relation(relation_candidate, entity_registry)
            
            # 4. 生成最终输出
            final_output = self.finalize_registry_and_generate_output(
                entity_registry, relation_registry, document_id
            )
            
            logger.info(f"分块知识抽取完成，最终实体数: {len(final_output['entities'])}, 关系数: {len(final_output['relations'])}")
            return final_output
            
        except Exception as e:
            logger.error(f"分块知识抽取失败: {e}")
            raise
    
    async def extract_entities_chunked(
        self, 
        document_id: str,
        json_data: List[Dict[str, Any]], 
        terms: Optional[List[Term]] = None
    ) -> Dict[str, Any]:
        """
        独立的实体识别函数（异常32新增）
        
        Args:
            document_id: 文档ID
            json_data: MongoDB中的json_data字段
            terms: 可选的术语列表（仅实体类型）
            
        Returns:
            实体识别结果: {"entities": [...], "meta": {...}}
        """
        try:
            logger.info(f"开始分块实体识别，文档ID: {document_id}")
            
            # 1. 文档分块
            chunks = self.get_chunks_from_json_data(json_data)
            logger.info(f"文档分块完成，共 {len(chunks)} 个chunk")
            
            # 2. 初始化实体注册表
            entity_registry = EntityRegistry()
            
            # 3. 过滤出实体类型的术语
            entity_terms = None
            if terms:
                entity_terms = [term for term in terms if term.type == "实体"]
                logger.info(f"使用 {len(entity_terms)} 个实体术语进行识别")
            
            # 4. 逐chunk处理实体识别（异常37优化：改进超时控制）
            successful_chunks = 0
            timeout_chunks = 0  
            failed_chunks = 0
            
            for i, chunk in enumerate(chunks):
                logger.info(f"处理chunk {i+1}/{len(chunks)}, page_idx: {chunk.page_idx}")
                
                # 异常37修复：根据chunk大小动态调整超时时间
                chunk_text_length = len(chunk.text) if chunk.text else 0
                term_count = len(entity_terms) if entity_terms else 0
                
                # 基础超时40秒，根据文本长度和术语数量调整
                base_timeout = 120.0
                text_factor = min(chunk_text_length / 1000, 2.0)  # 每1500字符增加最多2秒
                term_factor = min(term_count / 20, 1.5)          # 每20个术语增加最多1.5秒
                chunk_timeout = base_timeout + text_factor + term_factor
                
                logger.info(f"chunk {i+1} 动态超时设置: {chunk_timeout:.1f}秒 (文本长度: {chunk_text_length}, 术语数: {term_count})")
                
                try:
                    # 4.1 实体抽取（异常37优化：动态超时控制）
                    import time
                    start_time = time.time()
                    
                    entities_result = await asyncio.wait_for(
                        self.extract_entities_from_chunk(chunk, entity_terms),
                        timeout=chunk_timeout
                    )
                    
                    processing_time = time.time() - start_time
                    logger.info(f"chunk {i+1} 实体识别完成，耗时: {processing_time:.1f}秒")
                    
                    # 4.2 处理实体结果
                    chunk_entities = self._parse_entities_from_result(entities_result, chunk.page_idx)
                    entities_added = 0
                    for entity_candidate in chunk_entities:
                        entity_id = entity_registry.add_or_merge_entity(entity_candidate)
                        if entity_id:
                            entities_added += 1
                    
                    logger.info(f"chunk {i+1} 添加了 {entities_added} 个实体")
                    successful_chunks += 1
                        
                except asyncio.TimeoutError:
                    logger.warning(f"chunk {i+1} 处理超时 ({chunk_timeout:.1f}秒)，跳过该chunk")
                    timeout_chunks += 1
                    continue
                except Exception as e:
                    logger.error(f"chunk {i+1} 处理失败: {e}")
                    failed_chunks += 1
                    continue
            
            logger.info(f"实体识别处理完成 - 成功: {successful_chunks}, 超时: {timeout_chunks}, 失败: {failed_chunks}")
            
            # 异常37修复：如果超时太多，记录警告
            if timeout_chunks > successful_chunks:
                logger.warning(f"超时chunk数量({timeout_chunks})超过成功chunk数量({successful_chunks})，建议检查系统性能或调整超时设置")
            
            # 5. 生成实体输出
            entities = []
            for entity_id, entity_candidate in entity_registry.entities.items():
                entity_output = {
                    "entity_id": entity_id,
                    "entity_name": entity_candidate.entity_name,
                    "entity_type": entity_candidate.entity_type,
                    "attributes": entity_candidate.attributes or {},
                    "description": entity_candidate.description or "",
                    "positions": entity_candidate.positions,
                    "occurrence_count": entity_candidate.occurrence_count,
                    "confidence": entity_candidate.confidence
                }
                entities.append(entity_output)
            
            # 6. 生成元信息
            meta = {
                "document_id": document_id,
                "total_entities": len(entities),
                "processing_method": "chunked_entity_extraction",
                "chunks_processed": len(chunks)
            }
            
            final_output = {
                "entities": entities,
                "meta": meta
            }
            
            logger.info(f"分块实体识别完成，最终实体数: {len(entities)}")
            print("分块实体识别:", final_output)
            return final_output
            
        except Exception as e:
            logger.error(f"分块实体识别失败: {e}")
            raise

    # async def extract_entities_chunked(
    #         self, 
    #         document_id: str,
    #         json_data: List[Dict[str, Any]], 
    #         terms: Optional[List[Term]] = None,
    #         max_concurrent: int = 25  # 新增：最大并发数
    #     ) -> Dict[str, Any]:
    #         """
    #         独立的实体识别函数（异常32新增）- 支持并发调用大模型
            
    #         Args:
    #             document_id: 文档ID
    #             json_data: MongoDB中的json_data字段
    #             terms: 可选的术语列表（仅实体类型）
    #             max_concurrent: 最大并发处理数量
                
    #         Returns:
    #             实体识别结果: {"entities": [...], "meta": {...}}
    #         """
    #         try:
    #             logger.info(f"开始分块实体识别（并发模式），文档ID: {document_id}，最大并发: {max_concurrent}")
                
    #             # 1. 文档分块
    #             chunks = self.get_chunks_from_json_data(json_data)
    #             logger.info(f"文档分块完成，共 {len(chunks)} 个chunk")
                
    #             # 2. 初始化实体注册表
    #             entity_registry = EntityRegistry()
                
    #             # 3. 过滤出实体类型的术语
    #             entity_terms = None
    #             if terms:
    #                 entity_terms = [term for term in terms if term.type == "实体"]
    #                 logger.info(f"使用 {len(entity_terms)} 个实体术语进行识别")
                
    #             # 4. 并发处理chunk
    #             successful_chunks = 0
    #             timeout_chunks = 0  
    #             failed_chunks = 0
                
    #             # 创建信号量控制并发数
    #             semaphore = asyncio.Semaphore(max_concurrent)
                
    #             async def process_single_chunk(chunk, index):
    #                 """处理单个chunk的异步函数"""
    #                 async with semaphore:  # 使用信号量控制并发
    #                     logger.info(f"开始处理chunk {index+1}/{len(chunks)}, page_idx: {chunk.page_idx}")
                        
    #                     # 根据chunk大小动态调整超时时间
    #                     chunk_text_length = len(chunk.text) if chunk.text else 0
    #                     term_count = len(entity_terms) if entity_terms else 0
                        
    #                     # 基础超时40秒，根据文本长度和术语数量调整
    #                     base_timeout = 120.0
    #                     text_factor = min(chunk_text_length / 1000, 2.0)
    #                     term_factor = min(term_count / 20, 1.5)
    #                     chunk_timeout = base_timeout + text_factor + term_factor
                        
    #                     logger.info(f"chunk {index+1} 动态超时设置: {chunk_timeout:.1f}秒")
                        
    #                     try:
    #                         import time
    #                         start_time = time.time()
                            
    #                         # 调用大模型进行实体识别
    #                         entities_result = await asyncio.wait_for(
    #                             self.extract_entities_from_chunk(chunk, entity_terms),
    #                             timeout=chunk_timeout
    #                         )
                            
    #                         processing_time = time.time() - start_time
    #                         logger.info(f"chunk {index+1} 实体识别完成，耗时: {processing_time:.1f}秒")
                            
    #                         # 解析实体结果
    #                         chunk_entities = self._parse_entities_from_result(entities_result, chunk.page_idx)
                            
    #                         return {
    #                             "success": True,
    #                             "index": index,
    #                             "page_idx": chunk.page_idx,
    #                             "entities": chunk_entities,
    #                             "processing_time": processing_time
    #                         }
                            
    #                     except asyncio.TimeoutError:
    #                         logger.warning(f"chunk {index+1} 处理超时 ({chunk_timeout:.1f}秒)")
    #                         return {
    #                             "success": False,
    #                             "index": index,
    #                             "page_idx": chunk.page_idx,
    #                             "error": "timeout",
    #                             "processing_time": chunk_timeout
    #                         }
    #                     except Exception as e:
    #                         logger.error(f"chunk {index+1} 处理失败: {e}")
    #                         return {
    #                             "success": False,
    #                             "index": index,
    #                             "page_idx": chunk.page_idx,
    #                             "error": str(e),
    #                             "processing_time": 0
    #                         }
                
    #             # 创建所有chunk的处理任务
    #             tasks = []
    #             for i, chunk in enumerate(chunks):
    #                 task = process_single_chunk(chunk, i)
    #                 tasks.append(task)
                
    #             # 并发执行所有任务
    #             logger.info(f"开始并发处理 {len(tasks)} 个chunk...")
    #             results = await asyncio.gather(*tasks, return_exceptions=True)
                
    #             # 处理结果
    #             chunk_entities_list = []
    #             for result in results:
    #                 # 处理异常情况
    #                 if isinstance(result, Exception):
    #                     logger.error(f"任务执行异常: {result}")
    #                     failed_chunks += 1
    #                     continue
                    
    #                 if result["success"]:
    #                     chunk_entities_list.append(result["entities"])
    #                     successful_chunks += 1
    #                 else:
    #                     if result["error"] == "timeout":
    #                         timeout_chunks += 1
    #                     else:
    #                         failed_chunks += 1
                
    #             # 按原始顺序合并实体（保持一致性）
    #             logger.info(f"开始合并 {len(chunk_entities_list)} 个chunk的实体...")
                
    #             for chunk_entities in chunk_entities_list:
    #                 entities_added = 0
    #                 for entity_candidate in chunk_entities:
    #                     entity_id = entity_registry.add_or_merge_entity(entity_candidate)
    #                     if entity_id:
    #                         entities_added += 1
    #                 logger.info(f"chunk 添加了 {entities_added} 个实体")
                
    #             logger.info(f"实体识别处理完成 - 成功: {successful_chunks}, 超时: {timeout_chunks}, 失败: {failed_chunks}")
                
    #             # 如果超时太多，记录警告
    #             if timeout_chunks > successful_chunks:
    #                 logger.warning(f"超时chunk数量({timeup_chunks})超过成功chunk数量({successful_chunks})，建议检查系统性能或调整超时设置")
                
    #             # 5. 生成实体输出
    #             entities = []
    #             for entity_id, entity_candidate in entity_registry.entities.items():
    #                 entity_output = {
    #                     "entity_id": entity_id,
    #                     "entity_name": entity_candidate.entity_name,
    #                     "entity_type": entity_candidate.entity_type,
    #                     "attributes": entity_candidate.attributes or {},
    #                     "description": entity_candidate.description or "",
    #                     "positions": entity_candidate.positions,
    #                     "occurrence_count": entity_candidate.occurrence_count,
    #                     "confidence": entity_candidate.confidence
    #                 }
    #                 entities.append(entity_output)
                
    #             # 6. 生成元信息
    #             meta = {
    #                 "document_id": document_id,
    #                 "total_entities": len(entities),
    #                 "processing_method": "concurrent_chunked_entity_extraction",
    #                 "chunks_total": len(chunks),
    #                 "chunks_successful": successful_chunks,
    #                 "chunks_timeout": timeout_chunks,
    #                 "chunks_failed": failed_chunks,
    #                 "max_concurrent": max_concurrent
    #             }
                
    #             final_output = {
    #                 "entities": entities,
    #                 "meta": meta
    #             }
                
    #             logger.info(f"分块实体识别完成，最终实体数: {len(entities)}")
    #             print("分块实体识别:", final_output)
    #             return final_output
                
    #         except Exception as e:
    #             logger.error(f"分块实体识别失败: {e}")
    #             raise
   
    async def extract_relations_chunked(
        self, 
        document_id: str,
        entities: List[Entity],
        json_data: List[Dict[str, Any]], 
        terms: Optional[List[Term]] = None
    ) -> Dict[str, Any]:
        """
        独立的关系抽取函数（异常32新增）
        
        基于已确认的实体列表进行关系抽取
        
        Args:
            document_id: 文档ID
            entities: 已确认的实体列表（从MySQL读取）
            json_data: MongoDB中的json_data字段
            terms: 可选的术语列表（仅关系类型）
            
        Returns:
            关系抽取结果: {"relations": [...], "meta": {...}}
        """
        try:
            logger.info(f"开始分块关系抽取，文档ID: {document_id}, 实体数: {len(entities)}")
            
            if not entities:
                logger.warning("实体列表为空，无法进行关系抽取")
                return {
                    "relations": [],
                    "meta": {
                        "document_id": document_id,
                        "total_relations": 0,
                        "processing_method": "chunked_relation_extraction",
                        "error": "实体列表为空"
                    }
                }
            
            # 1. 文档分块
            chunks = self.get_chunks_from_json_data(json_data)
            logger.info(f"文档分块完成，共 {len(chunks)} 个chunk")
            
            # 2. 初始化关系注册表和实体注册表
            relation_registry = RelationRegistry(mysql_service=self.mysql_service, document_id=document_id)
            entity_registry = EntityRegistry()
            
            # 3. 将已确认的实体添加到注册表中（用于关系端点验证）
            for entity in entities:
                entity_candidate = EntityCandidate(
                    entity_id=getattr(entity, 'entity_id', None) or str(getattr(entity, 'id', '')),
                    entity_name=entity.entity_name,
                    entity_type=getattr(entity, 'type', None),
                    attributes=entity.attributes,
                    description=entity.description,
                    confidence=entity.confidence,
                    occurrence_count=entity.occurrence_count
                )
                # 直接设置ID，不使用add_or_merge（避免重复合并）
                if entity_candidate.entity_id:
                    entity_registry.entities[entity_candidate.entity_id] = entity_candidate
                    entity_registry.name_to_id[entity_registry._normalize_name(entity_candidate.entity_name)] = entity_candidate.entity_id
            
            logger.info(f"已加载 {len(entity_registry.entities)} 个实体到注册表")
            
            # 4. 过滤出关系类型的术语
            relation_terms = None
            if terms:
                relation_terms = [term for term in terms if term.type == "关系"]
                logger.info(f"使用 {len(relation_terms)} 个关系术语进行抽取")
            
            # 5. 逐chunk处理关系抽取（异常37优化：改进超时控制和错误处理）
            successful_chunks = 0
            timeout_chunks = 0
            failed_chunks = 0
            
            for i, chunk in enumerate(chunks):
                logger.info(f"处理chunk {i+1}/{len(chunks)}, page_idx: {chunk.page_idx}")
                
                # 异常37修复：根据chunk大小和实体数量动态调整超时时间
                chunk_text_length = len(chunk.text) if chunk.text else 0
                entity_count = len(entity_registry.entities)
                
                # 基础超时60秒，根据文本长度和实体数量调整
                base_timeout = 120.0
                text_factor = min(chunk_text_length / 1000, 3.0)  # 每1000字符增加最多3秒
                entity_factor = min(entity_count / 10, 2.0)      # 每10个实体增加最多2秒
                chunk_timeout = base_timeout + text_factor + entity_factor
                
                logger.info(f"chunk {i+1} 动态超时设置: {chunk_timeout:.1f}秒 (文本长度: {chunk_text_length}, 实体数: {entity_count})")
                
                try:
                    # 5.1 生成该chunk对应的实体候选列表（用于关系抽取）
                    chunk_entities = []
                    for entity_id, entity_candidate in entity_registry.entities.items():
                        chunk_entities.append(entity_candidate)
                    
                    # 5.2 关系抽取（异常37优化：动态超时控制）
                    import time
                    start_time = time.time()
                    
                    relations_result = await asyncio.wait_for(
                        self.extract_relations_from_chunk(
                            chunk, chunk_entities, relation_terms
                        ),
                        timeout=chunk_timeout
                    )
                    
                    processing_time = time.time() - start_time
                    logger.info(f"chunk {i+1} 关系抽取完成，耗时: {processing_time:.1f}秒")
                    
                    # 5.3 处理关系结果
                    chunk_relations = self._parse_relations_from_result(relations_result, chunk.page_idx)
                    relations_added = 0
                    for relation_candidate in chunk_relations:
                        relation_id = relation_registry.add_or_merge_relation(relation_candidate, entity_registry)
                        if relation_id:
                            relations_added += 1
                    
                    logger.info(f"chunk {i+1} 添加了 {relations_added} 个关系")
                    successful_chunks += 1
                        
                except asyncio.TimeoutError:
                    logger.warning(f"关系抽取chunk {i+1} 处理超时 ({chunk_timeout:.1f}秒)，跳过该chunk")
                    timeout_chunks += 1
                    continue
                except Exception as e:
                    logger.error(f"关系抽取chunk {i+1} 处理失败: {e}")
                    failed_chunks += 1
                    continue
            
            logger.info(f"关系抽取处理完成 - 成功: {successful_chunks}, 超时: {timeout_chunks}, 失败: {failed_chunks}")
            
            # 异常37修复：如果超时太多，记录警告
            if timeout_chunks > successful_chunks:
                logger.warning(f"超时chunk数量({timeout_chunks})超过成功chunk数量({successful_chunks})，建议检查系统性能或调整超时设置")
            
            # 6. 生成关系输出（只包含完整的关系）（异常37修复：添加实体名称解析）
            relations = []
            incomplete_relations_count = 0
            
            for relation_candidate in relation_registry.relations.values():
                # 异常42修复：支持部分匹配的关系，不再仅限于完整关系
                if relation_candidate.relation_id:
                    # 异常37修复：解析实体ID到实体名称
                    head_entity_name = "未知实体"
                    tail_entity_name = "未知实体"
                    
                    # 从实体注册表中查找头实体名称
                    if relation_candidate.head_entity_id and relation_candidate.head_entity_id in entity_registry.entities:
                        head_entity_name = entity_registry.entities[relation_candidate.head_entity_id].entity_name
                    elif relation_candidate.head_entity_name:
                        # 如果直接有实体名称，使用它
                        head_entity_name = relation_candidate.head_entity_name
                    
                    # 从实体注册表中查找尾实体名称
                    if relation_candidate.tail_entity_id and relation_candidate.tail_entity_id in entity_registry.entities:
                        tail_entity_name = entity_registry.entities[relation_candidate.tail_entity_id].entity_name
                    elif relation_candidate.tail_entity_name:
                        # 如果直接有实体名称，使用它
                        tail_entity_name = relation_candidate.tail_entity_name
                    
                    # 异常42修复：允许部分匹配的关系，只要有关系名称和至少一个有效实体名称
                    if (not relation_candidate.relation_name or
                        (head_entity_name == "未知实体" and tail_entity_name == "未知实体")):
                        logger.warning(f"关系 '{relation_candidate.relation_name}' 缺少关键信息: head_name={head_entity_name}, tail_name={tail_entity_name}")
                        incomplete_relations_count += 1
                        continue

                    # 记录部分匹配的关系
                    if (relation_candidate.head_entity_id is None or
                        relation_candidate.tail_entity_id is None):
                        logger.info(f"保存部分匹配关系 '{relation_candidate.relation_name}': head_id={relation_candidate.head_entity_id}, tail_id={relation_candidate.tail_entity_id}, head_name={head_entity_name}, tail_name={tail_entity_name}")
                    
                    relation_output = {
                        "relation_id": relation_candidate.relation_id,
                        "relation_name": relation_candidate.relation_name,
                        "head_entity": head_entity_name,  # 异常37修复：必需字段
                        "tail_entity": tail_entity_name,  # 异常37修复：必需字段
                        "head_entity_id": relation_candidate.head_entity_id,
                        "tail_entity_id": relation_candidate.tail_entity_id,
                        "description": relation_candidate.description or "",
                        "evidence_text": relation_candidate.evidence_text or "",
                        "positions": relation_candidate.positions,
                        "confidence": relation_candidate.confidence
                    }
                    relations.append(relation_output)
                else:
                    incomplete_relations_count += 1
            
            # 7. 生成元信息
            meta = {
                "document_id": document_id,
                "total_relations": len(relations),
                "incomplete_relations_count": incomplete_relations_count,
                "processing_method": "chunked_relation_extraction",
                "chunks_processed": len(chunks),
                "input_entities_count": len(entities)
            }
            
            final_output = {
                "relations": relations,
                "meta": meta
            }
            
            logger.info(f"分块关系抽取完成，最终关系数: {len(relations)}, 不完整关系数: {incomplete_relations_count}")
            return final_output
            
        except Exception as e:
            logger.error(f"分块关系抽取失败: {e}")
            raise
    
    # async def extract_relations_chunked(
    #     self, 
    #     document_id: str,
    #     entities: List[Entity],
    #     json_data: List[Dict[str, Any]], 
    #     terms: Optional[List[Term]] = None,
    #     max_concurrent: int = 25  # 新增：最大并发数
    # ) -> Dict[str, Any]:
    #     """
    #     独立的关系抽取函数（异常32新增）- 支持并发调用大模型
        
    #     基于已确认的实体列表进行关系抽取
        
    #     Args:
    #         document_id: 文档ID
    #         entities: 已确认的实体列表（从MySQL读取）
    #         json_data: MongoDB中的json_data字段
    #         terms: 可选的术语列表（仅关系类型）
    #         max_concurrent: 最大并发处理数量
            
    #     Returns:
    #         关系抽取结果: {"relations": [...], "meta": {...}}
    #     """
    #     try:
    #         logger.info(f"开始分块关系抽取（并发模式），文档ID: {document_id}, 实体数: {len(entities)}, 最大并发: {max_concurrent}")
            
    #         if not entities:
    #             logger.warning("实体列表为空，无法进行关系抽取")
    #             return {
    #                 "relations": [],
    #                 "meta": {
    #                     "document_id": document_id,
    #                     "total_relations": 0,
    #                     "processing_method": "chunked_relation_extraction",
    #                     "error": "实体列表为空"
    #                 }
    #             }
            
    #         # 1. 文档分块
    #         chunks = self.get_chunks_from_json_data(json_data)
    #         logger.info(f"文档分块完成，共 {len(chunks)} 个chunk")
            
    #         # 2. 初始化关系注册表和实体注册表
    #         relation_registry = RelationRegistry(mysql_service=self.mysql_service, document_id=document_id)
    #         entity_registry = EntityRegistry()
            
    #         # 3. 将已确认的实体添加到注册表中（用于关系端点验证）
    #         for entity in entities:
    #             entity_candidate = EntityCandidate(
    #                 entity_id=getattr(entity, 'entity_id', None) or str(getattr(entity, 'id', '')),
    #                 entity_name=entity.entity_name,
    #                 entity_type=getattr(entity, 'type', None),
    #                 attributes=entity.attributes,
    #                 description=entity.description,
    #                 confidence=entity.confidence,
    #                 occurrence_count=entity.occurrence_count
    #             )
    #             # 直接设置ID，不使用add_or_merge（避免重复合并）
    #             if entity_candidate.entity_id:
    #                 entity_registry.entities[entity_candidate.entity_id] = entity_candidate
    #                 entity_registry.name_to_id[entity_registry._normalize_name(entity_candidate.entity_name)] = entity_candidate.entity_id
            
    #         logger.info(f"已加载 {len(entity_registry.entities)} 个实体到注册表")
            
    #         # 4. 过滤出关系类型的术语
    #         relation_terms = None
    #         if terms:
    #             relation_terms = [term for term in terms if term.type == "关系"]
    #             logger.info(f"使用 {len(relation_terms)} 个关系术语进行抽取")
            
    #         # 5. 并发处理chunk
    #         successful_chunks = 0
    #         timeout_chunks = 0
    #         failed_chunks = 0
            
    #         # 创建信号量控制并发数
    #         semaphore = asyncio.Semaphore(max_concurrent)
            
    #         # 预生成chunk对应的实体候选列表（所有chunk共享同一个实体列表）
    #         chunk_entities = []
    #         for entity_id, entity_candidate in entity_registry.entities.items():
    #             chunk_entities.append(entity_candidate)
            
    #         async def process_single_chunk(chunk, index):
    #             """处理单个chunk的异步函数"""
    #             async with semaphore:  # 使用信号量控制并发
    #                 logger.info(f"开始处理chunk {index+1}/{len(chunks)}, page_idx: {chunk.page_idx}")
                    
    #                 # 根据chunk大小和实体数量动态调整超时时间
    #                 chunk_text_length = len(chunk.text) if chunk.text else 0
    #                 entity_count = len(entity_registry.entities)
                    
    #                 # 基础超时60秒，根据文本长度和实体数量调整
    #                 base_timeout = 120.0
    #                 text_factor = min(chunk_text_length / 1000, 3.0)  # 每1000字符增加最多3秒
    #                 entity_factor = min(entity_count / 10, 2.0)      # 每10个实体增加最多2秒
    #                 chunk_timeout = base_timeout + text_factor + entity_factor
                    
    #                 logger.info(f"chunk {index+1} 动态超时设置: {chunk_timeout:.1f}秒 (文本长度: {chunk_text_length}, 实体数: {entity_count})")
                    
    #                 try:
    #                     import time
    #                     start_time = time.time()
                        
    #                     # 关系抽取
    #                     relations_result = await asyncio.wait_for(
    #                         self.extract_relations_from_chunk(
    #                             chunk, chunk_entities, relation_terms
    #                         ),
    #                         timeout=chunk_timeout
    #                     )
                        
    #                     processing_time = time.time() - start_time
    #                     logger.info(f"chunk {index+1} 关系抽取完成，耗时: {processing_time:.1f}秒")
                        
    #                     # 解析关系结果
    #                     chunk_relations = self._parse_relations_from_result(relations_result, chunk.page_idx)
                        
    #                     return {
    #                         "success": True,
    #                         "index": index,
    #                         "page_idx": chunk.page_idx,
    #                         "relations": chunk_relations,
    #                         "processing_time": processing_time
    #                     }
                        
    #                 except asyncio.TimeoutError:
    #                     logger.warning(f"chunk {index+1} 关系抽取超时 ({chunk_timeout:.1f}秒)")
    #                     return {
    #                         "success": False,
    #                         "index": index,
    #                         "page_idx": chunk.page_idx,
    #                         "error": "timeout",
    #                         "processing_time": chunk_timeout
    #                     }
    #                 except Exception as e:
    #                     logger.error(f"chunk {index+1} 关系抽取失败: {e}")
    #                     return {
    #                         "success": False,
    #                         "index": index,
    #                         "page_idx": chunk.page_idx,
    #                         "error": str(e),
    #                         "processing_time": 0
    #                     }
            
    #         # 创建所有chunk的处理任务
    #         tasks = []
    #         for i, chunk in enumerate(chunks):
    #             task = process_single_chunk(chunk, i)
    #             tasks.append(task)
            
    #         # 并发执行所有任务
    #         logger.info(f"开始并发处理 {len(tasks)} 个chunk的关系抽取...")
    #         results = await asyncio.gather(*tasks, return_exceptions=True)
            
    #         # 按原始顺序收集结果
    #         chunk_relations_list = []
    #         for result in results:
    #             # 处理异常情况
    #             if isinstance(result, Exception):
    #                 logger.error(f"任务执行异常: {result}")
    #                 failed_chunks += 1
    #                 continue
                
    #             if result["success"]:
    #                 chunk_relations_list.append({
    #                     "index": result["index"],
    #                     "relations": result["relations"]
    #                 })
    #                 successful_chunks += 1
    #             else:
    #                 if result["error"] == "timeout":
    #                     timeout_chunks += 1
    #                 else:
    #                     failed_chunks += 1
            
    #         # 按原始顺序排序（保持一致性）
    #         chunk_relations_list.sort(key=lambda x: x["index"])
            
    #         # 合并所有关系
    #         logger.info(f"开始合并 {len(chunk_relations_list)} 个chunk的关系...")
            
    #         for chunk_data in chunk_relations_list:
    #             relations_added = 0
    #             for relation_candidate in chunk_data["relations"]:
    #                 relation_id = relation_registry.add_or_merge_relation(relation_candidate, entity_registry)
    #                 if relation_id:
    #                     relations_added += 1
    #             logger.info(f"chunk 添加了 {relations_added} 个关系")
            
    #         logger.info(f"关系抽取处理完成 - 成功: {successful_chunks}, 超时: {timeout_chunks}, 失败: {failed_chunks}")
            
    #         # 如果超时太多，记录警告
    #         if timeout_chunks > successful_chunks:
    #             logger.warning(f"超时chunk数量({timeout_chunks})超过成功chunk数量({successful_chunks})，建议检查系统性能或调整超时设置")
            
    #         # 6. 生成关系输出（只包含完整的关系）
    #         relations = []
    #         incomplete_relations_count = 0
            
    #         for relation_candidate in relation_registry.relations.values():
    #             # 异常42修复：支持部分匹配的关系，不再仅限于完整关系
    #             if relation_candidate.relation_id:
    #                 # 异常37修复：解析实体ID到实体名称
    #                 head_entity_name = "未知实体"
    #                 tail_entity_name = "未知实体"
                    
    #                 # 从实体注册表中查找头实体名称
    #                 if relation_candidate.head_entity_id and relation_candidate.head_entity_id in entity_registry.entities:
    #                     head_entity_name = entity_registry.entities[relation_candidate.head_entity_id].entity_name
    #                 elif relation_candidate.head_entity_name:
    #                     # 如果直接有实体名称，使用它
    #                     head_entity_name = relation_candidate.head_entity_name
                    
    #                 # 从实体注册表中查找尾实体名称
    #                 if relation_candidate.tail_entity_id and relation_candidate.tail_entity_id in entity_registry.entities:
    #                     tail_entity_name = entity_registry.entities[relation_candidate.tail_entity_id].entity_name
    #                 elif relation_candidate.tail_entity_name:
    #                     # 如果直接有实体名称，使用它
    #                     tail_entity_name = relation_candidate.tail_entity_name
                    
    #                 # 异常42修复：允许部分匹配的关系，只要有关系名称和至少一个有效实体名称
    #                 if (not relation_candidate.relation_name or
    #                     (head_entity_name == "未知实体" and tail_entity_name == "未知实体")):
    #                     logger.warning(f"关系 '{relation_candidate.relation_name}' 缺少关键信息: head_name={head_entity_name}, tail_name={tail_entity_name}")
    #                     incomplete_relations_count += 1
    #                     continue

    #                 # 记录部分匹配的关系
    #                 if (relation_candidate.head_entity_id is None or
    #                     relation_candidate.tail_entity_id is None):
    #                     logger.info(f"保存部分匹配关系 '{relation_candidate.relation_name}': head_id={relation_candidate.head_entity_id}, tail_id={relation_candidate.tail_entity_id}, head_name={head_entity_name}, tail_name={tail_entity_name}")
                    
    #                 relation_output = {
    #                     "relation_id": relation_candidate.relation_id,
    #                     "relation_name": relation_candidate.relation_name,
    #                     "head_entity": head_entity_name,
    #                     "tail_entity": tail_entity_name,
    #                     "head_entity_id": relation_candidate.head_entity_id,
    #                     "tail_entity_id": relation_candidate.tail_entity_id,
    #                     "description": relation_candidate.description or "",
    #                     "evidence_text": relation_candidate.evidence_text or "",
    #                     "positions": relation_candidate.positions,
    #                     "confidence": relation_candidate.confidence
    #                 }
    #                 relations.append(relation_output)
    #             else:
    #                 incomplete_relations_count += 1
            
    #         # 7. 生成元信息
    #         meta = {
    #             "document_id": document_id,
    #             "total_relations": len(relations),
    #             "incomplete_relations_count": incomplete_relations_count,
    #             "processing_method": "concurrent_chunked_relation_extraction",
    #             "chunks_total": len(chunks),
    #             "chunks_successful": successful_chunks,
    #             "chunks_timeout": timeout_chunks,
    #             "chunks_failed": failed_chunks,
    #             "max_concurrent": max_concurrent,
    #             "input_entities_count": len(entities)
    #         }
            
    #         final_output = {
    #             "relations": relations,
    #             "meta": meta
    #         }
            
    #         logger.info(f"分块关系抽取完成，最终关系数: {len(relations)}, 不完整关系数: {incomplete_relations_count}")
    #         return final_output
            
    #     except Exception as e:
    #         logger.error(f"分块关系抽取失败: {e}")
    #         raise
   
   
    def get_chunks_from_json_data(self, json_data: List[Dict[str, Any]]) -> List[DocumentChunk]:
        """从json_data创建文档分块"""
        if not json_data:
            return []
            
        # 按page_idx分组
        page_groups = {}
        for item in json_data:
            if not isinstance(item, dict):
                continue
                
            page_idx = item.get("page_idx", 0)
            if page_idx not in page_groups:
                page_groups[page_idx] = []
            page_groups[page_idx].append(item)
        
        # 创建chunk列表
        chunks = []
        for page_idx in sorted(page_groups.keys()):
            page_items = page_groups[page_idx]
            
            # 提取该页的文本内容
            page_texts = []
            for item in page_items:
                if item.get("type") == "text" and item.get("text"):
                    text = item["text"].strip()
                    if text:
                        page_texts.append(text)
            
            # 创建chunk
            if page_texts:
                chunk_text = " ".join(page_texts)
                cleaned_text = self._filter_header_footer(chunk_text)
                
                chunk = DocumentChunk(
                    page_idx=page_idx,
                    text=chunk_text,
                    raw_data=page_items,
                    cleaned_text=cleaned_text
                )
                chunks.append(chunk)
                
                logger.debug(f"创建chunk page_idx={page_idx}, 原始长度={len(chunk_text)}, 清理后长度={len(cleaned_text)}")
        
        return chunks
    
    def _filter_header_footer(self, text: str) -> str:
        """过滤页眉页脚"""
        if not text:
            return text
            
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 检查是否匹配页眉页脚模式
            is_header_footer = False
            for pattern in self.header_footer_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    is_header_footer = True
                    break
            
            # 检查短行（可能是页眉页脚）
            if len(line) < 10 and re.search(r'\d+', line):
                is_header_footer = True
                
            if not is_header_footer:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    async def extract_entities_from_chunk(
        self, 
        chunk: DocumentChunk, 
        terms: Optional[List[Term]] = None
    ) -> str:
        """从单个chunk中抽取实体"""
        try:
            # 构造针对chunk的提示词
            entity_terms = [term for term in (terms or []) if term.type == "实体"]
            
            if not entity_terms:
                # 使用通用实体识别
                prompt = f"""以下是文档第 {chunk.page_idx} 页的文本（已去除页眉页脚）。请识别文本中的实体。

输出要求：严格返回 JSON 对象，顶层包含 "entities" 键，entities 为数组，每个实体包含：
- entity_name: 实体名称
- entity_type: 实体类型
- attributes: 属性字典（可选）
- description: 描述信息
- positions: 位置信息数组，包含 page_idx, start, end, context
- occurrence_count: 在当前chunk中出现次数
- confidence: 置信度 (0.0-1.0)
- incomplete: 如果实体在当前chunk中不完整（跨页），设为true

注意：当前只处理本 chunk 的文本；若实体或关系在上下文中被截断（未完整出现），请在 incomplete 字段标记为 true。

文档文本：
{chunk.cleaned_text}

仅输出 JSON，无任何额外文字："""
            else:
                # 基于术语的实体识别
                terms_text = "\n".join([f"- {term.name}: {term.description or '无描述'}" for term in entity_terms])
                prompt = f"""以下是文档第 {chunk.page_idx} 页的文本（已去除页眉页脚）。请基于给定的术语库识别文本中的实体。

术语库（实体类型）：
{terms_text}

输出要求：严格返回 JSON 对象，顶层包含 "entities" 键，entities 为数组，每个实体包含：
- entity_name: 实体名称
- entity_type: 实体类型（优先使用术语库中的类型）
- attributes: 属性字典（可选）
- description: 描述信息
- positions: 位置信息数组，包含 page_idx, start, end, context
- occurrence_count: 在当前chunk中出现次数
- confidence: 置信度 (0.0-1.0)
- incomplete: 如果实体在当前chunk中不完整（跨页），设为true

注意：当前只处理本 chunk 的文本；若实体在上下文中被截断（未完整出现），请在 incomplete 字段标记为 true。

文档文本：
{chunk.cleaned_text}

仅输出 JSON，无任何额外文字："""
                
            # 调用大模型
            response = await self.prompt_service._call_llm_api(prompt)
            logger.debug(f"Chunk {chunk.page_idx} 实体抽取原始响应长度: {len(response)}")
            
            return response
            
        except Exception as e:
            logger.error(f"Chunk {chunk.page_idx} 实体抽取失败: {e}")
            return '{"entities": []}'
    
    async def extract_relations_from_chunk(
        self,
        chunk: DocumentChunk,
        chunk_entities: List[EntityCandidate],
        terms: Optional[List[Term]] = None
    ) -> str:
        """从单个chunk中抽取关系"""
        try:
            if not chunk_entities:
                return '{"relations": []}'
                
            # 构建实体列表文本
            entities_text = "\n".join([
                f"- {entity.entity_name} ({entity.entity_type or '未知类型'})"
                for entity in chunk_entities
            ])
            
            # 构造提示词
            relation_terms = [term for term in (terms or []) if term.type == "关系"]
            
            if not relation_terms:
                # 通用关系抽取
                prompt = f"""以下是文档第 {chunk.page_idx} 页已识别的实体。请从文本中抽取实体之间的关系。

已识别的实体：
{entities_text}

输出要求：严格返回 JSON 对象，顶层包含 "relations" 键，relations 为数组，每个关系包含：
- relation_name: 关系名称
- head_entity_name: 头实体名称（必须在上述实体列表中）
- tail_entity_name: 尾实体名称（必须在上述实体列表中）
- description: 关系描述
- evidence_text: 证据文本片段
- positions: 位置信息数组，包含 page_idx, context
- confidence: 置信度 (0.0-1.0)
- incomplete: 如果关系在当前chunk中不完整（跨页），设为true

文档文本：
{chunk.cleaned_text}

仅输出 JSON，无任何额外文字："""
            else:
                # 基于术语的关系抽取
                relation_terms_text = "\n".join([
                    f"- {term.name}: {term.description or '无描述'}" 
                    for term in relation_terms
                ])
                prompt = f"""以下是文档第 {chunk.page_idx} 页已识别的实体。请基于给定的关系术语库从文本中抽取关系。

已识别的实体：
{entities_text}

关系术语库：
{relation_terms_text}

输出要求：严格返回 JSON 对象，顶层包含 "relations" 键，relations 为数组，每个关系包含：
- relation_name: 关系名称（优先使用术语库中的关系）
- head_entity_name: 头实体名称（必须在上述实体列表中）
- tail_entity_name: 尾实体名称（必须在上述实体列表中）
- description: 关系描述
- evidence_text: 证据文本片段
- positions: 位置信息数组，包含 page_idx, context
- confidence: 置信度 (0.0-1.0)
- incomplete: 如果关系在当前chunk中不完整（跨页），设为true

文档文本：
{chunk.cleaned_text}

仅输出 JSON，无任何额外文字："""
                
            # 调用大模型
            response = await self.prompt_service._call_llm_api(prompt)
            logger.debug(f"Chunk {chunk.page_idx} 关系抽取原始响应长度: {len(response)}")
            
            return response
            
        except Exception as e:
            logger.error(f"Chunk {chunk.page_idx} 关系抽取失败: {e}")
            return '{"relations": []}'
    
    def _parse_entities_from_result(self, raw_response: str, page_idx: int) -> List[EntityCandidate]:
        """解析实体抽取结果"""
        try:
            # 使用现有的JSON解析函数
            result = self.prompt_service._extract_json_from_response(raw_response, "entities")
            
            entities = []
            for entity_data in result.get("entities", []):
                # 处理位置信息
                positions = []
                if entity_data.get("positions"):
                    for pos in entity_data["positions"]:
                        position = {
                            "page_idx": pos.get("page_idx", page_idx),
                            "start": pos.get("start", 0),
                            "end": pos.get("end", 0),
                            "context": pos.get("context", "")
                        }
                        positions.append(position)
                
                entity = EntityCandidate(
                    entity_name=entity_data.get("entity_name", ""),
                    entity_type=entity_data.get("entity_type"),
                    attributes=entity_data.get("attributes"),
                    description=entity_data.get("description"),
                    positions=positions,
                    occurrence_count=entity_data.get("occurrence_count", 1),
                    confidence=float(entity_data.get("confidence", 1.0)),
                    incomplete=entity_data.get("incomplete", False),
                    source_page=page_idx
                )
                
                if entity.entity_name:  # 只添加有名称的实体
                    entities.append(entity)
            
            logger.debug(f"Page {page_idx} 解析到 {len(entities)} 个实体")
            return entities
            
        except Exception as e:
            logger.error(f"Page {page_idx} 实体解析失败: {e}")
            return []
    
    def _parse_relations_from_result(self, raw_response: str, page_idx: int) -> List[RelationCandidate]:
        """解析关系抽取结果"""
        try:
            # 使用现有的JSON解析函数
            result = self.prompt_service._extract_json_from_response(raw_response, "relations")
            
            relations = []
            for relation_data in result.get("relations", []):
                # 处理位置信息
                positions = []
                if relation_data.get("positions"):
                    for pos in relation_data["positions"]:
                        position = {
                            "page_idx": pos.get("page_idx", page_idx),
                            "context": pos.get("context", "")
                        }
                        positions.append(position)
                
                relation = RelationCandidate(
                    relation_name=relation_data.get("relation_name", ""),
                    head_entity_name=relation_data.get("head_entity_name", ""),
                    tail_entity_name=relation_data.get("tail_entity_name", ""),
                    description=relation_data.get("description"),
                    evidence_text=relation_data.get("evidence_text"),
                    positions=positions,
                    confidence=float(relation_data.get("confidence", 1.0)),
                    incomplete=relation_data.get("incomplete", False),
                    source_page=page_idx
                )
                
                if (relation.relation_name and 
                    relation.head_entity_name and 
                    relation.tail_entity_name):  # 确保关系完整
                    relations.append(relation)
            
            logger.debug(f"Page {page_idx} 解析到 {len(relations)} 个关系")
            return relations
            
        except Exception as e:
            logger.error(f"Page {page_idx} 关系解析失败: {e}")
            return []
    
    def finalize_registry_and_generate_output(
        self, 
        entity_registry: EntityRegistry, 
        relation_registry: RelationRegistry,
        document_id: str
    ) -> Dict[str, Any]:
        """生成最终的标准化JSON输出"""
        
        # 生成实体列表
        entities = []
        for entity_id, entity_candidate in entity_registry.entities.items():
            entity_output = {
                "entity_id": entity_id,
                "entity_name": entity_candidate.entity_name,
                "entity_type": entity_candidate.entity_type,
                "attributes": entity_candidate.attributes or {},
                "description": entity_candidate.description or "",
                "positions": entity_candidate.positions,
                "occurrence_count": entity_candidate.occurrence_count,
                "confidence": entity_candidate.confidence
            }
            entities.append(entity_output)
        
        # 生成关系列表（异常42修复：支持部分匹配的关系）
        relations = []
        incomplete_relations_count = 0

        for relation_candidate in relation_registry.relations.values():
            # 异常42修复：支持部分匹配的关系，不再仅限于完整关系
            if relation_candidate.relation_id and relation_candidate.relation_name:
                # 异常42修复：解析实体名称，支持部分匹配
                head_entity_name = relation_candidate.head_entity_name or "未知实体"
                tail_entity_name = relation_candidate.tail_entity_name or "未知实体"

                relation_output = {
                    "relation_id": relation_candidate.relation_id,
                    "relation_name": relation_candidate.relation_name,
                    "head_entity": head_entity_name,  # 异常42修复：添加实体名称字段
                    "tail_entity": tail_entity_name,  # 异常42修复：添加实体名称字段
                    "head_entity_id": relation_candidate.head_entity_id,
                    "tail_entity_id": relation_candidate.tail_entity_id,
                    "description": relation_candidate.description or "",
                    "evidence_text": relation_candidate.evidence_text or "",
                    "positions": relation_candidate.positions,
                    "confidence": relation_candidate.confidence
                }
                relations.append(relation_output)
            else:
                incomplete_relations_count += 1
        
        # 元信息
        meta = {
            "document_id": document_id,
            "total_entities": len(entities),
            "total_relations": len(relations),
            "incomplete_relations_count": incomplete_relations_count,
            "processing_method": "chunked_extraction",
            "timestamp": json.loads(json.dumps({"timestamp": "now"}, default=str))["timestamp"]
        }
        
        final_output = {
            "entities": entities,
            "relations": relations,
            "meta": meta
        }
        
        logger.info(f"最终输出生成完成: {len(entities)} 实体, {len(relations)} 关系, {incomplete_relations_count} 不完整关系")
        return final_output