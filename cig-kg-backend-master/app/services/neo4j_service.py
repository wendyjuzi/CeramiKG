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
        database = os.getenv("NEO4J_DATABASE", "").strip()
        self.database = database or None
        self.driver = None
        self.pool = None  # Keep compatibility with the original MySQL service interface.

    async def initialize(self):
        """Initialize the async Neo4j driver."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri, 
                auth=(self.user, self.password),
                max_connection_pool_size=10
            )
            # 验证连接
            await self.driver.verify_connectivity()
            # Create constraints and indexes.
            await self._create_constraints_and_indexes()
            database_label = self.database or "default"
            logger.info(f"Neo4j initialized successfully (database={database_label})")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j: {e}")
            if self.driver:
                await self.driver.close()
                self.driver = None
            raise

    async def close(self):
        """异步关闭驱动程序"""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j connection closed")

    def _session(self, database_name: str = None):
        if not self.driver:
            raise Exception("Neo4j driver is not initialized. Call initialize() first.")
        database = self.database if database_name is None else database_name
        return self.driver.session(database=database)

    async def get_session(self, database_name: str = None):
        """获取指定数据库的异步会话"""
        return self._session(database_name)

    async def _create_constraints_and_indexes(self):
        """创建约束和索引以提高查询性能"""
        async with self._session() as session:
            schema_queries = [
                """
                CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity)
                REQUIRE (e.entity_id, e.document_id) IS UNIQUE
                """,
                "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.entity_name)",
                "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
                "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.document_id)",
                "CREATE INDEX IF NOT EXISTS FOR ()-[r:RELATED_TO]-() ON (r.relation_name)",
                "CREATE INDEX IF NOT EXISTS FOR ()-[r:RELATED_TO]-() ON (r.document_id)",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paper) REQUIRE p.paper_id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (e:CeramicEntity) REQUIRE e.entity_key IS UNIQUE",
                "CREATE INDEX IF NOT EXISTS FOR (p:Paper) ON (p.title)",
                "CREATE INDEX IF NOT EXISTS FOR (p:Paper) ON (p.doi)",
                "CREATE INDEX IF NOT EXISTS FOR (e:CeramicEntity) ON (e.name)",
                "CREATE INDEX IF NOT EXISTS FOR (e:CeramicEntity) ON (e.entity_type)",
                "CREATE INDEX IF NOT EXISTS FOR ()-[r:CERAMIC_RELATION]-() ON (r.paper_id)",
                "CREATE INDEX IF NOT EXISTS FOR ()-[r:CERAMIC_RELATION]-() ON (r.relation_type)",
            ]

            for query in schema_queries:
                try:
                    await session.run(query)
                except Exception as e:
                    logger.warning(f"Error creating Neo4j schema with query {query.strip()}: {e}")

            logger.info("Neo4j constraints and indexes checked successfully")

    # ==================== 实体管理功能 ====================

    async def check_entity_table_exists(self, document_id: str) -> bool:
        """
        Check whether entities exist for the document.
        Mirrors the original MySQL check_entity_table_exists method.
        """
        async with self._session() as session:
            result = await session.run("""
                MATCH (e:Entity {document_id: $document_id})
                RETURN count(e) > 0 as exists
                LIMIT 1
            """, {'document_id': document_id})
            
            record = await result.single()
            return record['exists'] if record else False

    async def check_relation_table_exists(self, document_id: str) -> bool:
        """
        Check whether relations exist for the document.
        Mirrors the original MySQL check_relation_table_exists method.
        """
        async with self._session() as session:
            result = await session.run("""
                MATCH (h:Entity {document_id: $document_id})-[r:RELATED_TO]->(t:Entity {document_id: $document_id})
                RETURN count(r) > 0 as exists
                LIMIT 1
            """, {'document_id': document_id})
            
            record = await result.single()
            return record['exists'] if record else False

    async def check_knowledge_table_exists(self, document_id: str) -> bool:
        """
        Check whether knowledge exists. This is equivalent to relation existence.
        Mirrors the original MySQL check_knowledge_table_exists method.
        """
        return await self.check_relation_table_exists(document_id)

    async def create_entity_table(self, document_id: str):
        """
        创建实体表（Neo4j中不需要显式创建，但保留方法以保持接口一致）
        Mirrors the original MySQL create_entity_table method.
        """
        logger.info(f"Neo4j doesn't require explicit table creation, entities for document {document_id} will be created on save")

    async def create_relation_table(self, document_id: str):
        """
        创建关系表（Neo4j中不需要显式创建，但保留方法以保持接口一致）
        Mirrors the original MySQL create_relation_table method.
        """
        logger.info(f"Neo4j doesn't require explicit table creation, relations for document {document_id} will be created on save")

    async def create_knowledge_table_new(self, document_id: str):
        """
        创建知识表（Neo4j中不需要显式创建，但保留方法以保持接口一致）
        Mirrors the original MySQL create_knowledge_table_new method.
        """
        logger.info(f"Neo4j doesn't require explicit table creation, knowledge for document {document_id} will be created on save")

    async def save_entities_to_table(self, document_id: str, entities: List[Any]):
        """
        保存实体到实体表
        Mirrors the original MySQL save_entities_to_table method.
        """
        if not entities:
            logger.info(f"No entities to save for document {document_id}")
            return
        
        async with self._session() as session:
            for entity in entities:
                # Serialize position in the same shape used by the MySQL implementation.
                position_json = None
                if entity.position:
                    try:
                        # Keep behavior compatible with the MySQL version.
                        if hasattr(entity.position, '__iter__') and not isinstance(entity.position, str):
                            # Convert list items to dictionaries when possible.
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
                
                # Prepare entity properties.
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
                
                # Create or update the entity with MERGE.
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
        Get entities for the document.
        Mirrors the original MySQL get_entities_from_table method.
        """
        from app.models.schemas import Entity, EntityPosition
        
        async with self._session() as session:
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
                
                # Parse position data into EntityPosition objects when possible.
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
        Mirrors the original MySQL check_semantic_triplet_exists method.
        """
        async with self._session() as session:
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
        Mirrors the original MySQL save_relations_to_table method.
        """
        if not relations:
            logger.info(f"No relations to save for document {document_id}")
            return
        
        # 生成relation_id的计数器
        relation_counter = 1
        
        async with self._session() as session:
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
                
                # Check whether the semantic triplet already exists.
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
                    # Insert a new relation.
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
        """Create a new relation."""
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
        Get relations for the document.
        Mirrors the original MySQL get_relations_from_table method.
        """
        from app.models.schemas import Relation
        
        async with self._session() as session:
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
        Get knowledge rows. The structure is the same as relations.
        Mirrors the original MySQL get_knowledges_from_table method.
        """
        return await self.get_relations_from_table(document_id)

    async def save_knowledges_to_table(self, document_id: str, relations: List[Any]):
        """
        保存知识到全局知识表，实现双重保存机制
        Mirrors the original MySQL save_knowledges_to_table method.
        """
        # 1. 先保存到文档级关系表
        await self.save_relations_to_table(document_id, relations)
        logger.info(f"Saved relations to document {document_id}")
        
        # 2. Also save to the global knowledge graph.
        await self._save_to_global_knowledges_table(relations)
        logger.info(f"Saved {len(relations)} relations to global knowledge")

    async def _save_to_global_knowledges_table(self, relations: List[Any]):
        """
        Save relations to the global knowledge graph.
        Mirrors the original MySQL _save_to_global_knowledges_table method.
        """
        if not relations:
            return
        
        async with self._session() as session:
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
                
                # Create or update global entities and relations with MERGE.
                await session.run("""
                    // Create or get the global head entity.
                    MERGE (h:GlobalEntity {entity_id: $head_entity_id})
                    ON CREATE SET 
                        h.entity_name = $head_entity,
                        h.created_at = datetime()
                    ON MATCH SET 
                        h.entity_name = $head_entity,
                        h.updated_at = datetime()
                    
                    // Create or get the global tail entity.
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
        Aggregate knowledge from all document relation graphs.
        Mirrors the original MySQL get_global_knowledges method.
        """
        from app.models.schemas import Relation
        
        async with self._session() as session:
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
            
            # Deduplicate by relation name and entity pair.
            unique_relations = {}
            for relation in all_relations:
                key = f"{relation.head_entity}_{relation.relation_name}_{relation.tail_entity}"
                if key not in unique_relations:
                    unique_relations[key] = relation
            
            logger.info(f"Retrieved {len(unique_relations)} unique relations from global knowledge")
            return list(unique_relations.values())

    async def get_knowledge_graph_by_document_id(self, document_id: str) -> Any:
        """
        Get graph data for a document and convert it to the frontend graph shape.
        Mirrors the original MySQL get_knowledge_graph_by_document_id method.
        """
        from app.models.schemas import KnowledgeGraphResponse, GraphNode, GraphEdge

        if await self.check_extracted_paper_exists(document_id):
            return await self.get_extracted_knowledge_graph_by_paper_id(document_id)
        
        async with self._session() as session:
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
                    
                    # Add relation edges.
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
        Get knowledge graph options with display names.
        Mirrors the original MySQL get_knowledge_graph_options method.
        """
        from app.models.schemas import KnowledgeGraphOption
        
        async with self._session() as session:
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
                
                # Count entities and relations.
                stats_result = await session.run("""
                    MATCH (e:Entity {document_id: $document_id})
                    OPTIONAL MATCH (e)-[r:RELATED_TO]->()
                    RETURN count(DISTINCT e) as entity_count, count(DISTINCT r) as relation_count
                """, {'document_id': document_id})
                
                stats = await stats_result.single()
                
                options.append(KnowledgeGraphOption(
                    document_id=document_id,
                    display_name=f"文档 {document_id}",
                    description=f"Knowledge graph built from document {document_id}",
                    table_count=(stats['entity_count'] if stats else 0) + (stats['relation_count'] if stats else 0),
                    is_legacy=False
                ))
            
            logger.info(f"Found {len(options)} knowledge graph options")
            
            # 2. Add papers imported from relation/**/extracted.json.
            seen_document_ids = {option.document_id for option in options}
            paper_result = await session.run("""
                MATCH (p:Paper)
                WHERE p.source = 'relation_extracted'
                OPTIONAL MATCH (p)-[:MENTIONS]->(e:CeramicEntity)
                WITH p, count(DISTINCT e) AS entity_count
                OPTIONAL MATCH (:CeramicEntity)-[r:CERAMIC_RELATION {paper_id: p.paper_id}]->(:CeramicEntity)
                RETURN p.paper_id AS document_id,
                       p.title AS title,
                       p.doi AS doi,
                       p.year AS year,
                       entity_count AS entity_count,
                       count(DISTINCT r) AS relation_count
                ORDER BY title
            """)

            async for record in paper_result:
                document_id = record["document_id"]
                if not document_id or document_id in seen_document_ids:
                    continue
                display_name = record["title"] or document_id
                meta_bits = []
                if record["year"]:
                    meta_bits.append(str(record["year"]))
                if record["doi"]:
                    meta_bits.append(str(record["doi"]))
                description_suffix = f" ({', '.join(meta_bits)})" if meta_bits else ""
                entity_count = record["entity_count"] or 0
                relation_count = record["relation_count"] or 0
                options.append(KnowledgeGraphOption(
                    document_id=document_id,
                    display_name=display_name,
                    description=f"Imported ceramic KG from relation/extracted.json{description_suffix}",
                    table_count=entity_count + relation_count,
                    is_legacy=False
                ))
                seen_document_ids.add(document_id)

            logger.info(f"Found {len(options)} knowledge graph options")
            return sorted(options, key=lambda x: (x.is_legacy, x.display_name))

    async def list_knowledge_tables(self) -> List[str]:
        """
        列出所有可用于知识图谱查询的document_id
        Mirrors the original MySQL list_knowledge_tables method.
        """
        async with self._session() as session:
            result = await session.run("""
                MATCH (e:Entity)
                WHERE e.document_id IS NOT NULL AND e.document_id <> ''
                RETURN DISTINCT e.document_id as document_id
                ORDER BY document_id
            """)
            
            document_ids = []
            async for record in result:
                document_ids.append(record['document_id'])

            paper_result = await session.run("""
                MATCH (p:Paper)
                WHERE p.source = 'relation_extracted'
                RETURN DISTINCT p.paper_id AS document_id
                ORDER BY document_id
            """)

            seen = set(document_ids)
            async for record in paper_result:
                document_id = record["document_id"]
                if document_id and document_id not in seen:
                    document_ids.append(document_id)
                    seen.add(document_id)
            
            logger.info(f"Found {len(document_ids)} available knowledge graphs")
            return document_ids

    async def get_table_info(self, document_name: str) -> Dict[str, Any]:
        """
        获取知识表的信息
        Mirrors the original MySQL get_table_info method.
        """
        async with self._session() as session:
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

            if entity_count == 0 and relation_count == 0:
                paper_result = await session.run("""
                    MATCH (p:Paper {paper_id: $paper_id})
                    OPTIONAL MATCH (p)-[:MENTIONS]->(e:CeramicEntity)
                    WITH p, count(DISTINCT e) AS entity_count
                    OPTIONAL MATCH (:CeramicEntity)-[r:CERAMIC_RELATION {paper_id: $paper_id}]->(:CeramicEntity)
                    RETURN entity_count AS entity_count,
                           count(DISTINCT r) AS relation_count,
                           p.created_at AS created_at
                """, {'paper_id': document_name})

                paper_record = await paper_result.single()
                if paper_record:
                    entity_count = paper_record["entity_count"] or 0
                    relation_count = paper_record["relation_count"] or 0
                    return {
                        'exists': entity_count > 0 or relation_count > 0,
                        'table_name': f"{document_name}_ceramic_graph",
                        'record_count': relation_count,
                        'created_at': paper_record.get("created_at"),
                    }
            
            return {
                'exists': entity_count > 0 or relation_count > 0,
                'table_name': f"{document_name}_relations",
                'record_count': relation_count,
                'created_at': None  # Neo4j does not store table creation time here.
            }

    async def delete_knowledge_table(self, document_name: str):
        """
        删除文档对应的知识表
        Mirrors the original MySQL delete_knowledge_table method.
        """
        async with self._session() as session:
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

            await self._delete_extracted_paper(session, document_name)

    # ==================== Ceramic extracted KG import ====================

    def _parse_json_property(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:
            return {"value": value}

    async def clear_extracted_kg(self) -> Dict[str, int]:
        """Delete only the graph built from relation/**/extracted.json."""
        async with self._session() as session:
            relation_result = await session.run("""
                MATCH ()-[r:CERAMIC_RELATION {source: 'relation_extracted'}]->()
                WITH count(r) AS deleted_relations, collect(r) AS relations
                FOREACH (rel IN relations | DELETE rel)
                RETURN deleted_relations
            """)
            relation_record = await relation_result.single()

            mention_result = await session.run("""
                MATCH (p:Paper {source: 'relation_extracted'})-[m:MENTIONS]->()
                WITH count(m) AS deleted_mentions, collect(m) AS mentions
                FOREACH (mention IN mentions | DELETE mention)
                RETURN deleted_mentions
            """)
            mention_record = await mention_result.single()

            paper_result = await session.run("""
                MATCH (p:Paper {source: 'relation_extracted'})
                WITH count(p) AS deleted_papers, collect(p) AS papers
                FOREACH (paper IN papers | DETACH DELETE paper)
                RETURN deleted_papers
            """)
            paper_record = await paper_result.single()

            entity_result = await session.run("""
                MATCH (e:CeramicEntity)
                WITH count(e) AS deleted_entities, collect(e) AS entities
                FOREACH (entity IN entities | DETACH DELETE entity)
                RETURN deleted_entities
            """)
            entity_record = await entity_result.single()

            return {
                "deleted_papers": paper_record["deleted_papers"] if paper_record else 0,
                "deleted_entities": entity_record["deleted_entities"] if entity_record else 0,
                "deleted_mentions": mention_record["deleted_mentions"] if mention_record else 0,
                "deleted_relations": relation_record["deleted_relations"] if relation_record else 0,
            }

    async def _delete_extracted_paper(self, session, paper_id: str) -> None:
        await session.run("""
            MATCH ()-[r:CERAMIC_RELATION {paper_id: $paper_id}]->()
            DELETE r
        """, {"paper_id": paper_id})

        await session.run("""
            MATCH (p:Paper {paper_id: $paper_id})-[m:MENTIONS]->()
            DELETE m
        """, {"paper_id": paper_id})

        await session.run("""
            MATCH (p:Paper {paper_id: $paper_id})
            DETACH DELETE p
        """, {"paper_id": paper_id})

        await session.run("""
            MATCH (e:CeramicEntity)
            WHERE NOT EXISTS { MATCH ()-[:MENTIONS]->(e) }
              AND NOT EXISTS { MATCH (e)-[:CERAMIC_RELATION]-() }
            DELETE e
        """)

    async def import_extracted_papers(self, papers: List[Dict[str, Any]], clear_existing: bool = False) -> Dict[str, Any]:
        """Create/update the Neo4j graph from parsed relation extraction results."""
        if not papers:
            return {
                "imported_papers": 0,
                "imported_entities": 0,
                "imported_relations": 0,
                "errors": [],
            }

        await self._create_constraints_and_indexes()

        deleted = {}
        if clear_existing:
            deleted = await self.clear_extracted_kg()

        summary = {
            "imported_papers": 0,
            "imported_entities": 0,
            "imported_relations": 0,
            "errors": [],
            "clear_existing": clear_existing,
            "deleted": deleted,
        }

        async with self._session() as session:
            total_papers = len(papers)
            for index, item in enumerate(papers, start=1):
                paper = item.get("paper", {})
                paper_id = paper.get("paper_id")
                if not paper_id:
                    summary["errors"].append({"paper_id": None, "error": "Missing paper_id"})
                    continue

                try:
                    await self._delete_extracted_paper(session, paper_id)
                    await self._import_extracted_paper(session, item)
                    summary["imported_papers"] += 1
                    summary["imported_entities"] += len(item.get("entities", []))
                    summary["imported_relations"] += len(item.get("relations", []))
                    if index == 1 or index % 10 == 0 or index == total_papers:
                        logger.info(
                            "Imported extracted paper %s/%s: %s",
                            index,
                            total_papers,
                            paper_id,
                        )
                except Exception as exc:
                    logger.exception("Failed to import extracted paper %s", paper_id)
                    summary["errors"].append({"paper_id": paper_id, "error": str(exc)})

        return summary

    async def _import_extracted_paper(self, session, item: Dict[str, Any]) -> None:
        paper = item["paper"]
        entities = item.get("entities", [])
        relations = item.get("relations", [])

        await session.run("""
            MERGE (p:Paper {paper_id: $paper_id})
            ON CREATE SET p.created_at = datetime()
            SET p.title = $title,
                p.extraction_title = $extraction_title,
                p.source_path = $source_path,
                p.relative_path = $relative_path,
                p.authors = $authors,
                p.journal = $journal,
                p.year = $year,
                p.doi = $doi,
                p.abstract = $abstract,
                p.keywords = $keywords,
                p.entity_count = $entity_count,
                p.relation_count = $relation_count,
                p.raw_entity_count = $raw_entity_count,
                p.raw_relation_count = $raw_relation_count,
                p.source = 'relation_extracted',
                p.updated_at = datetime()
        """, paper)

        if entities:
            await session.run("""
                MATCH (p:Paper {paper_id: $paper_id})
                UNWIND $entities AS row
                MERGE (e:CeramicEntity {entity_key: row.entity_key})
                ON CREATE SET e.created_at = datetime()
                SET e.name = row.name,
                    e.entity_type = row.type,
                    e.attributes_json = row.attributes_json,
                    e.context = row.context,
                    e.updated_at = datetime()
                MERGE (p)-[m:MENTIONS]->(e)
                ON CREATE SET m.created_at = datetime()
                SET m.context = row.context,
                    m.attributes_json = row.attributes_json,
                    m.source_index = row.source_index,
                    m.updated_at = datetime()
            """, {"paper_id": paper["paper_id"], "entities": entities})

        if relations:
            await session.run("""
                UNWIND $relations AS row
                MATCH (h:CeramicEntity {entity_key: row.head_key})
                MATCH (t:CeramicEntity {entity_key: row.tail_key})
                MERGE (h)-[r:CERAMIC_RELATION {relation_id: row.relation_id}]->(t)
                ON CREATE SET r.created_at = datetime()
                SET r.paper_id = $paper_id,
                    r.relation_type = row.relation_type,
                    r.evidence = row.evidence,
                    r.attributes_json = row.attributes_json,
                    r.source_index = row.source_index,
                    r.confidence = 1.0,
                    r.source = 'relation_extracted',
                    r.updated_at = datetime()
            """, {"paper_id": paper["paper_id"], "relations": relations})

    async def check_extracted_paper_exists(self, paper_id: str) -> bool:
        async with self._session() as session:
            result = await session.run("""
                MATCH (p:Paper {paper_id: $paper_id})
                RETURN count(p) > 0 AS exists
            """, {"paper_id": paper_id})
            record = await result.single()
            return bool(record["exists"]) if record else False

    def _add_ceramic_node(self, nodes_dict: Dict[str, Any], entity: Any, graph_node_cls) -> None:
        if not entity:
            return
        entity_key = entity.get("entity_key")
        if not entity_key or entity_key in nodes_dict:
            return
        nodes_dict[entity_key] = graph_node_cls(
            id=entity_key,
            name=entity.get("name") or entity_key,
            type=entity.get("entity_type") or "unknown",
            properties={
                "entity_type": entity.get("entity_type") or "unknown",
                "attributes": self._parse_json_property(entity.get("attributes_json")),
                "context": entity.get("context"),
                "source": "relation_extracted",
            },
        )

    async def get_extracted_knowledge_graph_by_paper_id(self, paper_id: str) -> Any:
        from app.models.schemas import KnowledgeGraphResponse, GraphNode, GraphEdge

        async with self._session() as session:
            result = await session.run("""
                MATCH (p:Paper {paper_id: $paper_id})
                OPTIONAL MATCH (p)-[:MENTIONS]->(e:CeramicEntity)
                WITH p, collect(DISTINCT e) AS mentioned_entities
                OPTIONAL MATCH (h:CeramicEntity)-[r:CERAMIC_RELATION {paper_id: $paper_id}]->(t:CeramicEntity)
                RETURN p, mentioned_entities, collect({head: h, relation: r, tail: t}) AS triples
            """, {"paper_id": paper_id})
            record = await result.single()

            if not record:
                return KnowledgeGraphResponse(
                    nodes=[],
                    edges=[],
                    metadata={"paper_id": paper_id, "source": "relation_extracted", "exists": False},
                )

            nodes_dict = {}
            edges = []
            paper = record["p"]

            for entity in record["mentioned_entities"] or []:
                self._add_ceramic_node(nodes_dict, entity, GraphNode)

            for triple in record["triples"] or []:
                relation = triple.get("relation") if triple else None
                head = triple.get("head") if triple else None
                tail = triple.get("tail") if triple else None
                if not relation or not head or not tail:
                    continue

                self._add_ceramic_node(nodes_dict, head, GraphNode)
                self._add_ceramic_node(nodes_dict, tail, GraphNode)
                relation_type = relation.get("relation_type") or "related_to"
                edges.append(GraphEdge(
                    id=relation.get("relation_id"),
                    source=head.get("entity_key"),
                    target=tail.get("entity_key"),
                    type=relation_type,
                    relation_type=relation_type,
                    properties={
                        "paper_id": relation.get("paper_id"),
                        "paper_title": paper.get("title") if paper else None,
                        "evidence": relation.get("evidence"),
                        "evidence_text": relation.get("evidence"),
                        "confidence": float(relation.get("confidence", 1.0)),
                        "attributes": self._parse_json_property(relation.get("attributes_json")),
                        "source": "relation_extracted",
                    },
                ))

            return KnowledgeGraphResponse(
                nodes=list(nodes_dict.values()),
                edges=edges,
                metadata={
                    "paper_id": paper_id,
                    "document_id": paper_id,
                    "title": paper.get("title") if paper else None,
                    "doi": paper.get("doi") if paper else None,
                    "year": paper.get("year") if paper else None,
                    "node_count": len(nodes_dict),
                    "edge_count": len(edges),
                    "source": "relation_extracted",
                    "exists": True,
                },
            )

    async def get_extracted_unified_knowledge_graph(self, limit: Optional[int] = 2000) -> Any:
        from app.models.schemas import KnowledgeGraphResponse, GraphNode, GraphEdge

        async with self._session() as session:
            total_result = await session.run("""
                MATCH (:CeramicEntity)-[r:CERAMIC_RELATION {source: 'relation_extracted'}]->(:CeramicEntity)
                RETURN count(r) AS total_relations
            """)
            total_record = await total_result.single()
            total_relations = total_record["total_relations"] if total_record else 0

            graph_query = """
                MATCH (h:CeramicEntity)-[r:CERAMIC_RELATION {source: 'relation_extracted'}]->(t:CeramicEntity)
                OPTIONAL MATCH (p:Paper {paper_id: r.paper_id})
                RETURN h, r, t, p
                ORDER BY r.paper_id, r.source_index
            """
            graph_params = {}
            if limit is not None:
                graph_query += "\n                LIMIT $limit"
                graph_params["limit"] = int(limit)

            result = await session.run(graph_query, graph_params)

            nodes_dict = {}
            edges = []

            async for record in result:
                head = record["h"]
                tail = record["t"]
                relation = record["r"]
                paper = record["p"]
                self._add_ceramic_node(nodes_dict, head, GraphNode)
                self._add_ceramic_node(nodes_dict, tail, GraphNode)

                relation_type = relation.get("relation_type") or "related_to"
                edges.append(GraphEdge(
                    id=relation.get("relation_id"),
                    source=head.get("entity_key"),
                    target=tail.get("entity_key"),
                    type=relation_type,
                    relation_type=relation_type,
                    properties={
                        "paper_id": relation.get("paper_id"),
                        "paper_title": paper.get("title") if paper else None,
                        "evidence": relation.get("evidence"),
                        "evidence_text": relation.get("evidence"),
                        "confidence": float(relation.get("confidence", 1.0)),
                        "attributes": self._parse_json_property(relation.get("attributes_json")),
                        "source": "relation_extracted",
                    },
                ))

            return KnowledgeGraphResponse(
                nodes=list(nodes_dict.values()),
                edges=edges,
                metadata={
                    "total_nodes": len(nodes_dict),
                    "total_edges": len(edges),
                    "total_relations": total_relations,
                    "limit": limit,
                    "include_all": limit is None,
                    "truncated": False if limit is None else total_relations > len(edges),
                    "source": "relation_extracted",
                },
            )

    # ==================== 辅助方法 ====================

    async def search_assistant_context(
        self,
        question: str,
        limit: int = 8,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return a small, question-related graph neighborhood for assistant context."""
        terms = self._assistant_search_terms(question)
        document_ids = [str(item) for item in (document_ids or [])]
        query = """
            MATCH (entity)
            WHERE entity:Entity OR entity:GlobalEntity OR entity:CeramicEntity
            WITH entity,
                 coalesce(entity.entity_name, entity.name, entity.label, '') AS entity_name
            WHERE entity_name <> ''
              AND size(entity_name) >= 2
              AND (
                toLower($question) CONTAINS toLower(entity_name)
                OR any(term IN $terms WHERE
                    toLower(entity_name) CONTAINS term
                    OR term CONTAINS toLower(entity_name)
                )
              )
              AND (
                size($document_ids) = 0
                OR entity:GlobalEntity
                OR toString(entity.document_id) IN $document_ids
                OR EXISTS {
                    MATCH (paper:Paper)-[:MENTIONS]->(entity)
                    WHERE paper.paper_id IN $document_ids
                }
              )
            OPTIONAL MATCH (entity)-[rel]-(neighbor)
            WHERE neighbor IS NULL
               OR neighbor:Entity
               OR neighbor:GlobalEntity
               OR neighbor:CeramicEntity
            OPTIONAL MATCH (paper:Paper {paper_id: rel.paper_id})
            WITH entity, entity_name, rel, neighbor, paper,
                 CASE
                    WHEN toLower($question) CONTAINS toLower(entity_name) THEN 2
                    ELSE 1
                 END AS relevance
            RETURN
                entity_name AS head,
                CASE
                    WHEN rel IS NULL THEN '相关实体'
                    ELSE coalesce(rel.relation_name, rel.relation_type, type(rel), '相关')
                END AS relation,
                CASE
                    WHEN neighbor IS NULL THEN ''
                    ELSE coalesce(neighbor.entity_name, neighbor.name, neighbor.label, '')
                END AS tail,
                coalesce(entity.document_id, rel.document_id, rel.paper_id) AS document_id,
                paper.title AS paper_title,
                CASE
                    WHEN rel IS NULL THEN coalesce(entity.description, '')
                    ELSE coalesce(rel.evidence_text, rel.evidence, rel.description, entity.description, entity.context, '')
                END AS evidence_text,
                relevance
            ORDER BY relevance DESC, head
            LIMIT $limit
        """

        async with self.driver.session() as session:
            result = await session.run(
                query,
                {
                    "question": question.lower(),
                    "terms": terms,
                    "document_ids": document_ids,
                    "limit": max(1, min(int(limit), 20)),
                },
            )
            rows = []
            seen = set()
            async for record in result:
                item = record.data()
                key = (item.get("head"), item.get("relation"), item.get("tail"))
                if key in seen:
                    continue
                seen.add(key)
                item.pop("relevance", None)
                rows.append(item)
            return rows

    @staticmethod
    def _assistant_search_terms(question: str) -> List[str]:
        """Create bounded Chinese/English search terms without requiring a tokenizer."""
        stopwords = {
            "什么", "哪些", "如何", "为什么", "是否", "可以", "请问", "介绍",
            "相关", "之间", "以及", "进行", "影响", "因素", "情况", "材料",
        }
        terms = []
        seen = set()
        segments = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_\-]{1,}|[\u4e00-\u9fff]{2,}", question.lower())

        for segment in segments:
            candidates = [segment]
            if re.fullmatch(r"[\u4e00-\u9fff]+", segment):
                for size in (3, 2, 4):
                    candidates.extend(
                        segment[index:index + size]
                        for index in range(max(0, len(segment) - size + 1))
                    )
            for candidate in candidates:
                if (
                    candidate in seen
                    or len(candidate) < 2
                    or any(stopword in candidate for stopword in stopwords)
                ):
                    continue
                seen.add(candidate)
                terms.append(candidate)
                if len(terms) >= 24:
                    return terms
        return terms

    async def get_entity_network(self, document_id: str, entity_id: str, depth: int = 2) -> Dict[str, Any]:
        """
        获取实体的关联网络（深度可配置）
        """
        async with self._session() as session:
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
        Find the shortest path between two entities.
        """
        async with self._session() as session:
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
