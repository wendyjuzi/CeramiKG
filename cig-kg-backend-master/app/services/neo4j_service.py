from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import os
import json
import logging
from datetime import datetime
import uuid
import re

logger = logging.getLogger(__name__)


class Neo4jService:
    def __init__(self):
        load_dotenv()

        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None
        self.pool = None  # 保持与原MySQL接口一致

    async def initialize(self):
        """异步初始化 Neo4j 驱动程序"""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri, 
                auth=(self.user, self.password),
                max_connection_pool_size=10
            )
            # 验证连接
            await self.driver.verify_connectivity()
            # 创建约束和索引
            await self._create_constraints_and_indexes()
            logger.info("Neo4j initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j: {e}")
            raise

    async def close(self):
        """异步关闭驱动程序"""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j connection closed")

    async def get_session(self, database_name: str = None):
        """获取指定数据库的异步会话"""
        if not self.driver:
            raise Exception("Neo4j driver is not initialized. Call initialize() first.")
        return self.driver.session(database=database_name)

    async def _create_constraints_and_indexes(self):
        """创建约束和索引以提高查询性能"""
        async with self.driver.session() as session:
            try:
                # 为实体创建唯一性约束
                await session.run("""
                    CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE
                """)
                
                # 为实体名称创建索引
                await session.run("""
                    CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.entity_name)
                """)
                
                # 为实体类型创建索引
                await session.run("""
                    CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)
                """)
                
                # 为文档ID创建索引（用于快速过滤）
                await session.run("""
                    CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.document_id)
                """)
                
                # 为关系创建索引
                await session.run("""
                    CREATE INDEX IF NOT EXISTS FOR ()-[r:RELATED_TO]-() ON (r.relation_name)
                """)
                await session.run("""
                    CREATE INDEX IF NOT EXISTS FOR ()-[r:RELATED_TO]-() ON (r.document_id)
                """)
                
                logger.info("Neo4j constraints and indexes created")
            except Exception as e:
                logger.warning(f"Error creating constraints/indexes: {e}")

    # ==================== 实体管理功能 ====================

    async def check_entity_table_exists(self, document_id: str) -> bool:
        """
        检查实体是否存在
        对应原MySQL的 check_entity_table_exists 方法
        """
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (e:Entity {document_id: $document_id})
                RETURN count(e) > 0 as exists
                LIMIT 1
            """, {'document_id': document_id})
            
            record = await result.single()
            return record['exists'] if record else False

    async def check_relation_table_exists(self, document_id: str) -> bool:
        """
        检查关系是否存在
        对应原MySQL的 check_relation_table_exists 方法
        """
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (h:Entity {document_id: $document_id})-[r:RELATED_TO]->(t:Entity {document_id: $document_id})
                RETURN count(r) > 0 as exists
                LIMIT 1
            """, {'document_id': document_id})
            
            record = await result.single()
            return record['exists'] if record else False

    async def check_knowledge_table_exists(self, document_id: str) -> bool:
        """
        检查知识是否存在（与关系表相同）
        对应原MySQL的 check_knowledge_table_exists 方法
        """
        return await self.check_relation_table_exists(document_id)

    async def create_entity_table(self, document_id: str):
        """
        创建实体表（Neo4j中不需要显式创建，但保留方法以保持接口一致）
        对应原MySQL的 create_entity_table 方法
        """
        logger.info(f"Neo4j doesn't require explicit table creation, entities for document {document_id} will be created on save")

    async def create_relation_table(self, document_id: str):
        """
        创建关系表（Neo4j中不需要显式创建，但保留方法以保持接口一致）
        对应原MySQL的 create_relation_table 方法
        """
        logger.info(f"Neo4j doesn't require explicit table creation, relations for document {document_id} will be created on save")

    async def create_knowledge_table_new(self, document_id: str):
        """
        创建知识表（Neo4j中不需要显式创建，但保留方法以保持接口一致）
        对应原MySQL的 create_knowledge_table_new 方法
        """
        logger.info(f"Neo4j doesn't require explicit table creation, knowledge for document {document_id} will be created on save")

    async def save_entities_to_table(self, document_id: str, entities: List[Any]):
        """
        保存实体到实体表
        对应原MySQL的 save_entities_to_table 方法
        """
        if not entities:
            logger.info(f"No entities to save for document {document_id}")
            return
        
        async with self.driver.session() as session:
            for entity in entities:
                # 处理 position 字段 - 使用与 MySQL 相同的方式
                position_json = None
                if entity.position:
                    try:
                        # 与 MySQL 版本保持一致的处理方式
                        if hasattr(entity.position, '__iter__') and not isinstance(entity.position, str):
                            # 如果是列表，转换每个元素为字典
                            position_list = []
                            for pos in entity.position:
                                if hasattr(pos, 'dict'):
                                    position_list.append(pos.dict())
                                elif hasattr(pos, '__dict__'):
                                    position_list.append({k: v for k, v in pos.__dict__.items() if not k.startswith('_')})
                                else:
                                    position_list.append(pos)
                            position_json = json.dumps(position_list, ensure_ascii=False)
                        elif hasattr(entity.position, 'dict'):
                            # 单个对象
                            position_json = json.dumps(entity.position.dict(), ensure_ascii=False)
                        else:
                            position_json = json.dumps(entity.position, ensure_ascii=False, default=str)
                    except Exception as e:
                        logger.warning(f"Failed to serialize position: {e}")
                        position_json = None
                else:
                    position_json = None
                
                # 处理 attributes 字段
                attributes_json = None
                if entity.attributes:
                    try:
                        attributes_json = json.dumps(entity.attributes, ensure_ascii=False)
                    except Exception as e:
                        logger.warning(f"Failed to serialize attributes: {e}")
                        attributes_json = None
                
                # 准备实体属性
                entity_props = {
                    'entity_id': entity.entity_id,
                    'entity_name': entity.entity_name,
                    'entity_type': entity.type if hasattr(entity, 'type') else getattr(entity, 'entity_type', None),
                    'attributes': attributes_json,
                    'description': entity.description,
                    'confidence': float(entity.confidence) if entity.confidence else 1.0,
                    'position': position_json,
                    'occurrence_count': entity.occurrence_count if entity.occurrence_count else 0,
                    'document_id': document_id,
                }
                
                # 使用MERGE创建或更新实体
                await session.run("""
                    MERGE (e:Entity {entity_id: $entity_id, document_id: $document_id})
                    ON CREATE SET 
                        e.entity_name = $entity_name,
                        e.entity_type = $entity_type,
                        e.attributes = $attributes,
                        e.description = $description,
                        e.confidence = $confidence,
                        e.position = $position,
                        e.occurrence_count = $occurrence_count,
                        e.created_at = datetime()
                    ON MATCH SET 
                        e.entity_name = $entity_name,
                        e.entity_type = $entity_type,
                        e.attributes = $attributes,
                        e.description = $description,
                        e.confidence = $confidence,
                        e.position = $position,
                        e.occurrence_count = $occurrence_count,
                        e.updated_at = datetime()
                    RETURN e
                """, {
                    'entity_id': entity_props['entity_id'],
                    'document_id': document_id,
                    'entity_name': entity_props['entity_name'],
                    'entity_type': entity_props['entity_type'],
                    'attributes': entity_props['attributes'],
                    'description': entity_props['description'],
                    'confidence': entity_props['confidence'],
                    'position': entity_props['position'],
                    'occurrence_count': entity_props['occurrence_count']
                })
            
            logger.info(f"Saved {len(entities)} entities for document {document_id}")

            
    async def get_entities_from_table(self, document_id: str) -> List[Any]:
        """
        从实体表中获取实体列表
        对应原MySQL的 get_entities_from_table 方法
        """
        from app.models.schemas import Entity, EntityPosition
        
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (e:Entity {document_id: $document_id})
                RETURN e
                ORDER BY e.entity_name
            """, {'document_id': document_id})
            
            entities = []
            async for record in result:
                e = record['e']
                # 解析JSON字段
                attributes = None
                if e.get('attributes'):
                    try:
                        attributes = json.loads(e.get('attributes'))
                    except:
                        attributes = e.get('attributes')
                
                # 解析位置信息 - 反序列化为 EntityPosition 对象列表
                position = None
                if e.get('position'):
                    try:
                        position_data = json.loads(e.get('position'))
                        # 将字典列表转换为 EntityPosition 对象列表
                        if isinstance(position_data, list):
                            position = []
                            for pos_dict in position_data:
                                if isinstance(pos_dict, dict):
                                    position.append(EntityPosition(
                                        start=pos_dict.get('start', 0),
                                        end=pos_dict.get('end', 0),
                                        context=pos_dict.get('context', '')
                                    ))
                                else:
                                    position.append(pos_dict)
                        else:
                            position = position_data
                    except Exception as ex:
                        logger.warning(f"Failed to parse position: {ex}")
                        position = e.get('position')
                
                entity = Entity(
                    entity_id=e.get('entity_id'),
                    entity_name=e.get('entity_name'),
                    type=e.get('entity_type'),
                    attributes=attributes,
                    description=e.get('description'),
                    confidence=float(e.get('confidence', 1.0)),
                    position=position,
                    occurrence_count=e.get('occurrence_count', 0)
                )
                entities.append(entity)
            
            return entities

    async def check_semantic_triplet_exists(self, document_id: str, relation_name: str, head_entity: str, tail_entity: str) -> Optional[str]:
        """
        检查语义三元组是否已存在，返回已存在的relation_id
        对应原MySQL的 check_semantic_triplet_exists 方法
        """
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (h:Entity {document_id: $document_id, entity_name: $head_entity})
                MATCH (t:Entity {document_id: $document_id, entity_name: $tail_entity})
                MATCH (h)-[r:RELATED_TO {relation_name: $relation_name}]->(t)
                RETURN r.relation_id as relation_id
                LIMIT 1
            """, {
                'document_id': document_id,
                'head_entity': head_entity,
                'tail_entity': tail_entity,
                'relation_name': relation_name
            })
            
            record = await result.single()
            return record['relation_id'] if record else None

    async def save_relations_to_table(self, document_id: str, relations: List[Any]):
        """
        保存关系到关系表
        对应原MySQL的 save_relations_to_table 方法
        """
        if not relations:
            logger.info(f"No relations to save for document {document_id}")
            return
        
        # 生成relation_id的计数器
        relation_counter = 1
        
        async with self.driver.session() as session:
            # 获取当前最大的relation_id数字
            result = await session.run("""
                MATCH (h:Entity {document_id: $document_id})-[r:RELATED_TO]->(t:Entity {document_id: $document_id})
                WHERE r.relation_id =~ 'R-\\\\d+'
                RETURN max(toInteger(substring(r.relation_id, 2))) as max_id
            """, {'document_id': document_id})
            
            record = await result.single()
            if record and record['max_id']:
                relation_counter = record['max_id'] + 1
            
            for relation in relations:
                # 获取关系数据
                relation_id = getattr(relation, 'relation_id', None)
                relation_name = getattr(relation, 'relation_name', '')
                head_entity = getattr(relation, 'head_entity', '') or getattr(relation, 'head_entity_name', '')
                tail_entity = getattr(relation, 'tail_entity', '') or getattr(relation, 'tail_entity_name', '')
                head_entity_id = getattr(relation, 'head_entity_id', None)
                tail_entity_id = getattr(relation, 'tail_entity_id', None)
                confidence = getattr(relation, 'confidence', 1.0)
                description = getattr(relation, 'description', None)
                evidence_text = getattr(relation, 'evidence_text', None)
                
                # 检查语义三元组是否已存在
                existing_relation_id = await self.check_semantic_triplet_exists(
                    document_id, relation_name, head_entity, tail_entity
                )
                
                if existing_relation_id:
                    # 更新现有关系
                    await self._update_relation(
                        session, document_id, relation_name, head_entity, tail_entity,
                        confidence, description, evidence_text, existing_relation_id
                    )
                    logger.debug(f"Updated existing relation {existing_relation_id}")
                else:
                    # 插入新关系
                    if not relation_id:
                        relation_id = f"R-{str(relation_counter).zfill(4)}"
                        relation_counter += 1
                    
                    await self._create_relation(
                        session, document_id, relation_id, relation_name,
                        head_entity, tail_entity, head_entity_id, tail_entity_id,
                        confidence, description, evidence_text
                    )
                    logger.debug(f"Inserted new relation {relation_id}")
            
            logger.info(f"Processed {len(relations)} relations for document {document_id}")

    async def _create_relation(self, session, document_id: str, relation_id: str, relation_name: str,
                               head_entity: str, tail_entity: str, head_entity_id: Optional[str],
                               tail_entity_id: Optional[str], confidence: float, description: Optional[str],
                               evidence_text: Optional[str]):
        """创建新关系（内部方法）"""
        await session.run("""
            // 创建或获取头实体
            MERGE (h:Entity {entity_id: $head_entity_id, document_id: $document_id})
            ON CREATE SET 
                h.entity_name = $head_entity,
                h.created_at = datetime()
            ON MATCH SET 
                h.entity_name = $head_entity,
                h.updated_at = datetime()
            
            // 创建或获取尾实体
            MERGE (t:Entity {entity_id: $tail_entity_id, document_id: $document_id})
            ON CREATE SET 
                t.entity_name = $tail_entity,
                t.created_at = datetime()
            ON MATCH SET 
                t.entity_name = $tail_entity,
                t.updated_at = datetime()
            
            // 创建关系
            MERGE (h)-[r:RELATED_TO {
                relation_id: $relation_id,
                document_id: $document_id
            }]->(t)
            ON CREATE SET 
                r.relation_name = $relation_name,
                r.confidence = $confidence,
                r.description = $description,
                r.evidence_text = $evidence_text,
                r.created_at = datetime()
            ON MATCH SET 
                r.relation_name = $relation_name,
                r.confidence = $confidence,
                r.description = $description,
                r.evidence_text = $evidence_text,
                r.updated_at = datetime()
            
            RETURN r
        """, {
            'head_entity_id': head_entity_id or head_entity,
            'head_entity': head_entity,
            'tail_entity_id': tail_entity_id or tail_entity,
            'tail_entity': tail_entity,
            'relation_id': relation_id,
            'document_id': document_id,
            'relation_name': relation_name,
            'confidence': confidence,
            'description': description,
            'evidence_text': evidence_text
        })

    async def _update_relation(self, session, document_id: str, relation_name: str,
                               head_entity: str, tail_entity: str, confidence: float,
                               description: Optional[str], evidence_text: Optional[str],
                               existing_relation_id: str):
        """更新现有关系（内部方法）"""
        await session.run("""
            MATCH (h:Entity {document_id: $document_id, entity_name: $head_entity})
            MATCH (t:Entity {document_id: $document_id, entity_name: $tail_entity})
            MATCH (h)-[r:RELATED_TO {relation_id: $existing_relation_id}]->(t)
            SET r.confidence = $confidence,
                r.description = $description,
                r.evidence_text = $evidence_text,
                r.updated_at = datetime()
            RETURN r
        """, {
            'document_id': document_id,
            'head_entity': head_entity,
            'tail_entity': tail_entity,
            'existing_relation_id': existing_relation_id,
            'confidence': confidence,
            'description': description,
            'evidence_text': evidence_text
        })

    async def get_relations_from_table(self, document_id: str) -> List[Any]:
        """
        从关系表中获取关系列表
        对应原MySQL的 get_relations_from_table 方法
        """
        from app.models.schemas import Relation
        
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (h:Entity {document_id: $document_id})-[r:RELATED_TO]->(t:Entity {document_id: $document_id})
                RETURN h, r, t
                ORDER BY r.created_at DESC
            """, {'document_id': document_id})
            
            relations = []
            async for record in result:
                h = record['h']
                r = record['r']
                t = record['t']
                
                relation = Relation(
                    id=r.get('relation_id'),
                    relation_id=r.get('relation_id'),
                    relation_name=r.get('relation_name'),
                    head_entity=h.get('entity_name'),
                    tail_entity=t.get('entity_name'),
                    head_entity_id=h.get('entity_id'),
                    head_entity_name=h.get('entity_name'),
                    tail_entity_id=t.get('entity_id'),
                    tail_entity_name=t.get('entity_name'),
                    confidence=float(r.get('confidence', 1.0)),
                    description=r.get('description'),
                    evidence_text=r.get('evidence_text')
                )
                relations.append(relation)
            
            return relations

    async def get_knowledges_from_table(self, document_id: str) -> List[Any]:
        """
        从知识表中获取知识列表（与关系表结构相同）
        对应原MySQL的 get_knowledges_from_table 方法
        """
        return await self.get_relations_from_table(document_id)

    async def save_knowledges_to_table(self, document_id: str, relations: List[Any]):
        """
        保存知识到全局知识表，实现双重保存机制
        对应原MySQL的 save_knowledges_to_table 方法
        """
        # 1. 先保存到文档级关系表
        await self.save_relations_to_table(document_id, relations)
        logger.info(f"Saved relations to document {document_id}")
        
        # 2. 再保存到全局知识表
        await self._save_to_global_knowledges_table(relations)
        logger.info(f"Saved {len(relations)} relations to global knowledge")

    async def _save_to_global_knowledges_table(self, relations: List[Any]):
        """
        保存到全局知识表
        对应原MySQL的 _save_to_global_knowledges_table 方法
        """
        if not relations:
            return
        
        async with self.driver.session() as session:
            for relation in relations:
                # 准备数据
                relation_id = getattr(relation, 'relation_id', None) or getattr(relation, 'id', None)
                relation_name = getattr(relation, 'relation_name', '')
                head_entity = getattr(relation, 'head_entity_name', None) or getattr(relation, 'head_entity', '')
                tail_entity = getattr(relation, 'tail_entity_name', None) or getattr(relation, 'tail_entity', '')
                head_entity_id = getattr(relation, 'head_entity_id', None)
                tail_entity_id = getattr(relation, 'tail_entity_id', None)
                description = getattr(relation, 'description', '')
                evidence_text = getattr(relation, 'evidence_text', '')
                confidence = getattr(relation, 'confidence', 1.0)
                
                if not relation_id:
                    continue
                
                # 使用MERGE创建或更新全局实体和关系
                await session.run("""
                    // 创建或获取全局头实体
                    MERGE (h:GlobalEntity {entity_id: $head_entity_id})
                    ON CREATE SET 
                        h.entity_name = $head_entity,
                        h.created_at = datetime()
                    ON MATCH SET 
                        h.entity_name = $head_entity,
                        h.updated_at = datetime()
                    
                    // 创建或获取全局尾实体
                    MERGE (t:GlobalEntity {entity_id: $tail_entity_id})
                    ON CREATE SET 
                        t.entity_name = $tail_entity,
                        t.created_at = datetime()
                    ON MATCH SET 
                        t.entity_name = $tail_entity,
                        t.updated_at = datetime()
                    
                    // 创建或更新全局关系
                    MERGE (h)-[r:GLOBAL_RELATED_TO {relation_id: $relation_id}]->(t)
                    ON CREATE SET 
                        r.relation_name = $relation_name,
                        r.confidence = $confidence,
                        r.description = $description,
                        r.evidence_text = $evidence_text,
                        r.created_at = datetime()
                    ON MATCH SET 
                        r.relation_name = $relation_name,
                        r.confidence = $confidence,
                        r.description = $description,
                        r.evidence_text = $evidence_text,
                        r.updated_at = datetime()
                """, {
                    'head_entity_id': head_entity_id or head_entity,
                    'head_entity': head_entity,
                    'tail_entity_id': tail_entity_id or tail_entity,
                    'tail_entity': tail_entity,
                    'relation_id': relation_id,
                    'relation_name': relation_name,
                    'confidence': confidence,
                    'description': description,
                    'evidence_text': evidence_text
                })
            
            logger.info(f"Processed {len(relations)} relations for global knowledge")

    async def get_global_knowledges(self) -> List[Any]:
        """
        从所有文档的关系表中聚合所有知识
        对应原MySQL的 get_global_knowledges 方法
        """
        from app.models.schemas import Relation
        
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (h:GlobalEntity)-[r:GLOBAL_RELATED_TO]->(t:GlobalEntity)
                RETURN h, r, t
                ORDER BY r.created_at DESC
            """)
            
            all_relations = []
            async for record in result:
                h = record['h']
                r = record['r']
                t = record['t']
                
                relation = Relation(
                    id=r.get('relation_id'),
                    relation_id=r.get('relation_id'),
                    relation_name=r.get('relation_name'),
                    head_entity=h.get('entity_name'),
                    tail_entity=t.get('entity_name'),
                    head_entity_id=h.get('entity_id'),
                    head_entity_name=h.get('entity_name'),
                    tail_entity_id=t.get('entity_id'),
                    tail_entity_name=t.get('entity_name'),
                    description=r.get('description'),
                    evidence_text=r.get('evidence_text'),
                    confidence=float(r.get('confidence', 1.0))
                )
                all_relations.append(relation)
            
            # 数据去重（基于关系名和实体对）
            unique_relations = {}
            for relation in all_relations:
                key = f"{relation.head_entity}_{relation.relation_name}_{relation.tail_entity}"
                if key not in unique_relations:
                    unique_relations[key] = relation
            
            logger.info(f"Retrieved {len(unique_relations)} unique relations from global knowledge")
            return list(unique_relations.values())

    async def get_knowledge_graph_by_document_id(self, document_id: str) -> Any:
        """
        从关系表获取知识图谱数据并转换为图结构
        对应原MySQL的 get_knowledge_graph_by_document_id 方法
        """
        from app.models.schemas import KnowledgeGraphResponse, GraphNode, GraphEdge
        
        async with self.driver.session() as session:
            try:
                # 处理legacy格式的document_id
                if document_id.startswith('legacy_'):
                    # 使用旧格式的document_name
                    document_name = document_id[7:]  # 去掉'legacy_'前缀
                    logger.info(f"Using legacy format for document {document_id}")
                else:
                    document_name = document_id
                
                # 查询所有实体和关系
                result = await session.run("""
                    MATCH (e:Entity {document_id: $document_id})
                    OPTIONAL MATCH (e)-[r:RELATED_TO]->(t:Entity {document_id: $document_id})
                    RETURN e, collect(DISTINCT r) as relations, collect(DISTINCT t) as targets
                """, {'document_id': document_id})
                
                nodes_dict = {}
                edges = []
                
                async for record in result:
                    # 添加实体节点
                    entity = record['e']
                    entity_id = entity.get('entity_id') or entity.get('entity_name')
                    entity_name = entity.get('entity_name')
                    
                    if entity_id not in nodes_dict:
                        nodes_dict[entity_id] = GraphNode(
                            id=entity_id,
                            name=entity_name,
                            type='entity',
                            properties={
                                'entity_type': entity.get('entity_type'),
                                'confidence': entity.get('confidence'),
                                'occurrence_count': entity.get('occurrence_count', 0)
                            }
                        )
                    
                    # 添加关系边
                    relations = record['relations']
                    targets = record['targets']
                    
                    for idx, r in enumerate(relations):
                        if idx < len(targets):
                            t = targets[idx]
                            if t:
                                edge_id = f"{entity_id}_{r.get('relation_name')}_{t.get('entity_id')}_{r.get('relation_id', '')}"
                                edge = GraphEdge(
                                    id=edge_id,
                                    source=entity_id,
                                    target=t.get('entity_id') or t.get('entity_name'),
                                    type=r.get('relation_name'),
                                    relation_type=r.get('relation_name'),
                                    properties={
                                        'confidence': float(r.get('confidence', 1.0)),
                                        'description': r.get('description'),
                                        'evidence_text': r.get('evidence_text')
                                    }
                                )
                                edges.append(edge)
                
                nodes = list(nodes_dict.values())
                metadata = {
                    'document_id': document_id,
                    'table_name': f"{document_id}_relations",
                    'node_count': len(nodes),
                    'edge_count': len(edges)
                }
                
                return KnowledgeGraphResponse(
                    nodes=nodes,
                    edges=edges,
                    metadata=metadata
                )
                
            except Exception as e:
                logger.error(f"Query relation table failed: {str(e)}")
                return KnowledgeGraphResponse(
                    nodes=[],
                    edges=[],
                    metadata={
                        'document_id': document_id,
                        'error': str(e)
                    }
                )

    async def get_knowledge_graph_options(self) -> List[Any]:
        """
        获取知识图谱选项列表，包含显示名称
        对应原MySQL的 get_knowledge_graph_options 方法
        """
        from app.models.schemas import KnowledgeGraphOption
        
        async with self.driver.session() as session:
            options = []
            
            # 1. 查找新格式的文档（有Entity节点且document_id不为空）
            result = await session.run("""
                MATCH (e:Entity)
                WHERE e.document_id IS NOT NULL AND e.document_id <> ''
                RETURN DISTINCT e.document_id as document_id
                ORDER BY document_id
            """)
            
            async for record in result:
                document_id = record['document_id']
                
                # 统计实体、关系数量
                stats_result = await session.run("""
                    MATCH (e:Entity {document_id: $document_id})
                    OPTIONAL MATCH (e)-[r:RELATED_TO]->()
                    RETURN count(DISTINCT e) as entity_count, count(DISTINCT r) as relation_count
                """, {'document_id': document_id})
                
                stats = await stats_result.single()
                
                options.append(KnowledgeGraphOption(
                    document_id=document_id,
                    display_name=f"文档 {document_id}",
                    description=f"基于文档{document_id}构建的知识图谱",
                    table_count=(stats['entity_count'] if stats else 0) + (stats['relation_count'] if stats else 0),
                    is_legacy=False
                ))
            
            logger.info(f"Found {len(options)} knowledge graph options")
            return sorted(options, key=lambda x: (x.is_legacy, x.display_name))

    async def list_knowledge_tables(self) -> List[str]:
        """
        列出所有可用于知识图谱查询的document_id
        对应原MySQL的 list_knowledge_tables 方法
        """
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (e:Entity)
                WHERE e.document_id IS NOT NULL AND e.document_id <> ''
                RETURN DISTINCT e.document_id as document_id
                ORDER BY document_id
            """)
            
            document_ids = []
            async for record in result:
                document_ids.append(record['document_id'])
            
            logger.info(f"Found {len(document_ids)} available knowledge graphs")
            return document_ids

    async def get_table_info(self, document_name: str) -> Dict[str, Any]:
        """
        获取知识表的信息
        对应原MySQL的 get_table_info 方法
        """
        async with self.driver.session() as session:
            # 统计实体数量
            entity_result = await session.run("""
                MATCH (e:Entity {document_id: $document_id})
                RETURN count(e) as count
            """, {'document_id': document_name})
            
            entity_record = await entity_result.single()
            entity_count = entity_record['count'] if entity_record else 0
            
            # 统计关系数量
            relation_result = await session.run("""
                MATCH (h:Entity {document_id: $document_id})-[r:RELATED_TO]->(t:Entity {document_id: $document_id})
                RETURN count(r) as count
            """, {'document_id': document_name})
            
            relation_record = await relation_result.single()
            relation_count = relation_record['count'] if relation_record else 0
            
            return {
                'exists': entity_count > 0 or relation_count > 0,
                'table_name': f"{document_name}_relations",
                'record_count': relation_count,
                'created_at': None  # Neo4j中不存储表创建时间
            }

    async def delete_knowledge_table(self, document_name: str):
        """
        删除文档对应的知识表
        对应原MySQL的 delete_knowledge_table 方法
        """
        async with self.driver.session() as session:
            # 删除文档相关的所有关系和实体
            result = await session.run("""
                MATCH (e:Entity {document_id: $document_id})
                OPTIONAL MATCH (e)-[r:RELATED_TO]-()
                DELETE r, e
                RETURN count(e) as deleted_entities, count(r) as deleted_relations
            """, {'document_id': document_name})
            
            record = await result.single()
            if record:
                logger.info(f"Deleted knowledge for document {document_name}: "
                          f"{record['deleted_entities']} entities, {record['deleted_relations']} relations")
            else:
                logger.warning(f"Knowledge table does not exist for document {document_name}")

    # ==================== 辅助方法 ====================

    async def get_entity_network(self, document_id: str, entity_id: str, depth: int = 2) -> Dict[str, Any]:
        """
        获取实体的关联网络（深度可配置）
        """
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH path = (e:Entity {document_id: $document_id, entity_id: $entity_id})-[r:RELATED_TO*1..$depth]-(connected)
                RETURN 
                    collect(DISTINCT e) as start_entity,
                    collect(DISTINCT connected) as connected_entities,
                    collect(DISTINCT r) as relations
            """, {'document_id': document_id, 'entity_id': entity_id, 'depth': depth})
            
            record = await result.single()
            if record:
                return {
                    'start_entity': record['start_entity'],
                    'connected_entities': record['connected_entities'],
                    'relations': record['relations'],
                    'total_nodes': len(record['connected_entities']) + 1
                }
            return {}

    async def find_path_between_entities(self, document_id: str, entity1_id: str, entity2_id: str) -> List[Dict]:
        """
        查找两个实体之间的最短路径
        """
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH path = shortestPath(
                    (e1:Entity {document_id: $document_id, entity_id: $entity1_id})-[*]-(e2:Entity {document_id: $document_id, entity_id: $entity2_id})
                )
                RETURN [node in nodes(path) | node.entity_name] as entity_path,
                       [rel in relationships(path) | rel.relation_name] as relation_path
            """, {'document_id': document_id, 'entity1_id': entity1_id, 'entity2_id': entity2_id})
            
            paths = []
            async for record in result:
                paths.append({
                    'entities': record['entity_path'],
                    'relations': record['relation_path']
                })
            return paths