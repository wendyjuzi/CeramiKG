import aiomysql
from app.config import settings
from app.models.schemas import (
    Term, Relation, KnowledgeGraphResponse, GraphNode, GraphEdge, Entity,
    DocumentGovernance, DocumentGovernanceCreate, DocumentGovernanceUpdate, 
    DocumentGovernanceListItem, DocumentGovernanceDetail
)
from typing import List, Optional, Dict, Any
import logging
import re
import json

logger = logging.getLogger(__name__)

class MySQLService:
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
    
    async def initialize(self):
        """初始化 MySQL 连接池和必要的表结构"""
        try:
            self.pool = await aiomysql.create_pool(
                host=settings.MYSQL_HOST,
                port=settings.MYSQL_PORT,
                user=settings.MYSQL_USER,
                password=settings.MYSQL_PASSWORD,
                db=settings.MYSQL_DATABASE,
                charset='utf8mb4',
                autocommit=True,
                maxsize=10
            )
            # 创建必要的表
            await self._create_terms_table()
            await self._create_documents_table()
            logger.info("MySQL initialized successfully with required tables")
        except Exception as e:
            logger.error(f"Failed to create MySQL pool: {e}")
            raise
    
    async def _create_terms_table(self):
        """创建terms表（如果不存在）"""
        if self.pool is None:
            return
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS terms (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    type ENUM('实体', '关系') NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_name (name),
                    INDEX idx_type (type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                await cursor.execute(create_table_sql)
                await conn.commit()
                logger.info("Terms table created/verified successfully")

    async def _create_documents_table(self):
        """创建documents表（如果不存在）- 文档治理功能"""
        if self.pool is None:
            return
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS `documents` (
                `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                `name` VARCHAR(255) NOT NULL COMMENT '文档名称',
                `file_path` VARCHAR(500) NOT NULL COMMENT '文档路径',
                `pdf_path` VARCHAR(500) DEFAULT NULL COMMENT 'PDF文件路径',
                `json_file_path` VARCHAR(500) DEFAULT NULL COMMENT 'JSON文件路径',
                `image_file_path` VARCHAR(500) DEFAULT NULL COMMENT '图片文件路径',
                `status` TINYINT DEFAULT 0 COMMENT '状态：0-待审核，1-已审核，2-已删除',
                `upload_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
                `update_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最近更新时间',
                `upload_user` VARCHAR(255) DEFAULT NULL COMMENT '上传用户',
                `es_code` VARCHAR(255) DEFAULT NULL COMMENT '文件量化索引码',
                `file_size` INT DEFAULT NULL COMMENT '文件大小(bytes)',
                `file_type` VARCHAR(255) DEFAULT NULL COMMENT '文件类型: 经验库，维修库，操作库',

                -- 索引优化（根据常用查询字段建立）
                INDEX `idx_status` (`status`),
                INDEX `idx_name` (`name`),
                INDEX `idx_file_type` (`file_type`),
                INDEX `idx_upload_time` (`upload_time`)

            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档治理表';

                """
                await cursor.execute(create_table_sql)
                await conn.commit()
                logger.info("Documents table created/verified successfully")

    async def close(self):
        """关闭 MySQL 连接池"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    def _generate_table_name(self, document_name: str) -> str:
        """
        生成安全的MySQL表名
        规则：
        1. 以 knowledge_ 为前缀
        2. 只保留字母、数字、下划线
        3. 长度限制在64字符内（MySQL表名限制）
        4. 转换为小写
        """
        # 移除特殊字符，只保留字母数字和下划线
        clean_name = re.sub(r'[^\w]', '_', document_name)
        # 移除连续的下划线
        clean_name = re.sub(r'_+', '_', clean_name)
        # 移除开头和结尾的下划线
        clean_name = clean_name.strip('_')
        # 转换为小写
        clean_name = clean_name.lower()
        # 生成表名
        table_name = f"knowledge_{clean_name}"
        # 限制长度
        if len(table_name) > 64:
            # 保留前缀，截断文档名部分
            max_doc_length = 64 - len("knowledge_")
            clean_name = clean_name[:max_doc_length]
            table_name = f"knowledge_{clean_name}"
        return table_name

    async def get_terms(self) -> List[Term]:
        """从 MySQL 获取术语库"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT id, name, type, description FROM terms")
                terms_data = await cursor.fetchall()
                return [Term(
                    id=term['id'], 
                    name=term['name'], 
                    type=term['type'],
                    description=term.get('description')
                ) for term in terms_data]

    async def create_knowledge_table(self, document_name: str):
        """为文档创建知识表"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_table_name(document_name)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '关系记录ID',
                    relation_id VARCHAR(50) COMMENT '关系类型ID（异常34修复：改为VARCHAR支持R-0001格式）',
                    relation_name VARCHAR(255) NOT NULL COMMENT '关系名称',
                    head_entity_id VARCHAR(50) COMMENT '头实体ID（异常34修复：改为VARCHAR支持E-0001格式）',
                    head_entity_name VARCHAR(255) NOT NULL COMMENT '头实体名称',
                    tail_entity_id VARCHAR(50) COMMENT '尾实体ID（异常34修复：改为VARCHAR支持E-0001格式）', 
                    tail_entity_name VARCHAR(255) NOT NULL COMMENT '尾实体名称',
                    confidence DECIMAL(3,2) DEFAULT 1.0 COMMENT '置信度(0.00-1.00)',
                    source_text TEXT COMMENT '来源文本片段',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_relation_name (relation_name),
                    INDEX idx_head_entity (head_entity_name),
                    INDEX idx_tail_entity (tail_entity_name),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档知识关系表'
                """
                await cursor.execute(create_table_sql)
                await conn.commit()

    async def save_relations(self, document_name: str, relations: List[Relation]):
        """保存关系到 MySQL"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_table_name(document_name)
        
        # 先创建表
        await self.create_knowledge_table(document_name)
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 清空现有数据
                await cursor.execute(f"DELETE FROM {table_name}")
                
                # 插入新关系
                for relation in relations:
                    insert_sql = f"""
                        INSERT INTO {table_name} 
                        (relation_id, relation_name, head_entity_id, head_entity_name, tail_entity_id, tail_entity_name)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    await cursor.execute(insert_sql, (
                        relation.id,
                        relation.name,
                        relation.head_entity_id,
                        relation.head_entity_name,
                        relation.tail_entity_id,
                        relation.tail_entity_name
                    ))
                await conn.commit()

    async def get_knowledge_graph(self, document_name: str) -> KnowledgeGraphResponse:
        """从 MySQL 获取知识图谱数据并转换为图结构"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_table_name(document_name)
        
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    # 获取所有关系数据
                    await cursor.execute(f"SELECT * FROM {table_name}")
                    relations_data = await cursor.fetchall()
                    
                    # 构建节点和边
                    nodes_dict = {}
                    edges = []
                    
                    for relation in relations_data:
                        # 添加头实体节点
                        head_id = str(relation['head_entity_id'] or relation['head_entity_name'])
                        if head_id not in nodes_dict:
                            nodes_dict[head_id] = GraphNode(
                                id=head_id,
                                name=relation['head_entity_name'],
                                type="entity",
                                properties={"entity_id": relation['head_entity_id']}
                            )
                        
                        # 添加尾实体节点
                        tail_id = str(relation['tail_entity_id'] or relation['tail_entity_name'])
                        if tail_id not in nodes_dict:
                            nodes_dict[tail_id] = GraphNode(
                                id=tail_id,
                                name=relation['tail_entity_name'],
                                type="entity",
                                properties={"entity_id": relation['tail_entity_id']}
                            )
                        
                        # 添加关系边
                        edge = GraphEdge(
                            id=f"rel_{relation['id']}",
                            source=head_id,
                            target=tail_id,
                            type=relation['relation_name'],
                            properties={
                                "relation_id": relation['relation_id'],
                                "created_at": str(relation.get('created_at', ''))
                            }
                        )
                        edges.append(edge)
                    
                    return KnowledgeGraphResponse(
                        nodes=list(nodes_dict.values()),
                        edges=edges,
                        metadata={
                            "document_name": document_name,
                            "total_nodes": len(nodes_dict),
                            "total_edges": len(edges)
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Error getting knowledge graph: {e}")
                    # 返回空图谱
                    return KnowledgeGraphResponse(
                        nodes=[],
                        edges=[],
                        metadata={
                            "document_name": document_name,
                            "error": str(e)
                        }
                    )

    async def add_term(self, name: str, term_type: str, description: str = None) -> int:
        """添加新术语"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO terms (name, type, description) VALUES (%s, %s, %s)",
                    (name, term_type, description)
                )
                await conn.commit()
                return cursor.lastrowid

    async def update_term(self, term_id: int, name: str = None, term_type: str = None, description: str = None):
        """更新术语"""
        if self.pool is None:
            await self.initialize()
        
        updates = []
        values = []
        
        if name is not None:
            updates.append("name = %s")
            values.append(name)
        if term_type is not None:
            updates.append("type = %s")
            values.append(term_type)
        if description is not None:
            updates.append("description = %s")
            values.append(description)
        
        if updates:
            values.append(term_id)
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"UPDATE terms SET {', '.join(updates)} WHERE id = %s",
                        values
                    )
                    await conn.commit()

    async def delete_term(self, term_id: int):
        """删除术语"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM terms WHERE id = %s", (term_id,))
                await conn.commit()

    async def delete_knowledge_table(self, document_name: str):
        """删除文档对应的知识表"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_table_name(document_name)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 检查表是否存在
                await cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = %s
                """, (table_name,))
                exists = await cursor.fetchone()
                
                if exists[0] > 0:
                    await cursor.execute(f"DROP TABLE {table_name}")
                    await conn.commit()
                    logger.info(f"Deleted knowledge table: {table_name}")
                else:
                    logger.warning(f"Knowledge table does not exist: {table_name}")

    async def list_knowledge_tables(self) -> List[str]:
        """列出所有可用于知识图谱查询的document_id（异常51修复）

        返回可用于调用 /knowledge-graph/{document_id} 接口的document_id列表
        支持新格式（{document_id}_relations）和旧格式（knowledge_{name}）的表
        """
        if self.pool is None:
            await self.initialize()

        document_ids = set()

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 1. 查找新格式的关系表：{document_id}_relations
                await cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_name LIKE '%_relations'
                """)
                new_tables = await cursor.fetchall()

                for table in new_tables:
                    table_name = table[0]
                    if table_name.endswith('_relations'):
                        # 提取document_id（去掉_relations后缀）
                        document_id = table_name[:-10]  # len('_relations') = 10
                        document_ids.add(document_id)

                # 2. 查找旧格式的知识表：knowledge_{name}（兼容性支持）
                await cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_name LIKE 'knowledge_%'
                """)
                old_tables = await cursor.fetchall()

                for table in old_tables:
                    table_name = table[0]
                    if table_name.startswith('knowledge_'):
                        # 提取document_name（去掉knowledge_前缀）
                        document_name = table_name[10:]  # len('knowledge_') = 10
                        # 对于旧格式，我们使用表名作为标识符，但需要特殊标记
                        document_ids.add(f"legacy_{document_name}")

                logger.info(f"找到 {len(document_ids)} 个可用的知识图谱: {list(document_ids)}")
                return sorted(list(document_ids))

    async def get_knowledge_graph_options(self) -> List:
        """异常51修复：获取知识图谱选项列表，包含显示名称"""
        from app.models.schemas import KnowledgeGraphOption

        if self.pool is None:
            await self.initialize()

        options = []

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 1. 查找新格式的关系表：{document_id}_relations
                await cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_name LIKE '%_relations'
                """)
                new_tables = await cursor.fetchall()

                for table in new_tables:
                    table_name = table[0]
                    if table_name.endswith('_relations'):
                        document_id = table_name[:-10]  # 去掉_relations后缀

                        # 检查相关表的数量
                        entity_table = f"{document_id}_entitys"
                        knowledge_table = f"{document_id}_knowledges"

                        await cursor.execute("""
                            SELECT COUNT(*) FROM information_schema.tables
                            WHERE table_schema = DATABASE()
                            AND table_name IN (%s, %s, %s)
                        """, (table_name, entity_table, knowledge_table))
                        table_count = await cursor.fetchone()

                        options.append(KnowledgeGraphOption(
                            document_id=document_id,
                            display_name=f"文档 {document_id}",
                            description=f"基于文档{document_id}构建的知识图谱",
                            table_count=table_count[0] if table_count else 0,
                            is_legacy=False
                        ))

                # 2. 查找旧格式的知识表：knowledge_{name}（兼容性支持）
                await cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_name LIKE 'knowledge_%'
                """)
                old_tables = await cursor.fetchall()

                for table in old_tables:
                    table_name = table[0]
                    if table_name.startswith('knowledge_'):
                        document_name = table_name[10:]  # 去掉knowledge_前缀
                        document_id = f"legacy_{document_name}"

                        options.append(KnowledgeGraphOption(
                            document_id=document_id,
                            display_name=f"文档 {document_name}（旧格式）",
                            description=f"旧格式知识图谱：{document_name}",
                            table_count=1,
                            is_legacy=True
                        ))

                logger.info(f"找到 {len(options)} 个知识图谱选项")
                return sorted(options, key=lambda x: (x.is_legacy, x.display_name))

    async def get_table_info(self, document_name: str) -> Dict[str, Any]:
        """获取知识表的信息"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_table_name(document_name)
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 检查表是否存在
                await cursor.execute("""
                    SELECT COUNT(*) as count FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = %s
                """, (table_name,))
                exists = await cursor.fetchone()
                
                if exists['count'] == 0:
                    return {"exists": False, "table_name": table_name}
                
                # 获取表记录数
                await cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                count_result = await cursor.fetchone()
                
                # 获取表创建时间
                await cursor.execute("""
                    SELECT create_time FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = %s
                """, (table_name,))
                create_info = await cursor.fetchone()
                
                return {
                    "exists": True,
                    "table_name": table_name,
                    "record_count": count_result['count'],
                    "created_at": create_info['create_time'].isoformat() if create_info['create_time'] else None
                }
    
    async def get_knowledge_graph_by_document_id(self, document_id: str) -> KnowledgeGraphResponse:
        """异常17+51修复：从关系表获取知识图谱数据并转换为图结构，支持新旧格式"""
        if self.pool is None:
            await self.initialize()

        # 异常51修复：处理legacy格式的document_id
        if document_id.startswith('legacy_'):
            # 使用旧的表命名规则
            document_name = document_id[7:]  # 去掉'legacy_'前缀
            table_name = self._generate_table_name(document_name)
            logger.info(f"使用旧格式查询知识图谱: {document_id} -> 表名: {table_name}")
        else:
            # 使用新的关系表命名规则
            table_name = self._generate_relation_table_name(document_id)
            logger.info(f"使用新格式查询知识图谱: {document_id} -> 表名: {table_name}")

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    # 检查表是否存在
                    await cursor.execute("""
                        SELECT COUNT(*) FROM information_schema.tables
                        WHERE table_schema = DATABASE() AND table_name = %s
                    """, (table_name,))
                    exists = await cursor.fetchone()

                    if exists['COUNT(*)'] == 0:
                        logger.warning(f"关系表不存在: {table_name}")
                        return KnowledgeGraphResponse(
                            nodes=[],
                            edges=[],
                            metadata={
                                "error": f"关系表不存在: {table_name}",
                                "document_id": document_id,
                                "table_name": table_name
                            }
                        )
                    
                    # 获取所有关系数据
                    await cursor.execute(f"SELECT * FROM {table_name}")
                    relations_data = await cursor.fetchall()
                    
                    # 构建节点和边
                    nodes_dict = {}
                    edges = []
                    
                    for relation in relations_data:
                        # 添加头实体节点
                        head_name = relation['head_entity']
                        if head_name not in nodes_dict:
                            nodes_dict[head_name] = GraphNode(
                                id=head_name,
                                name=head_name,
                                type="entity",
                                properties={}
                            )
                        
                        # 添加尾实体节点
                        tail_name = relation['tail_entity']
                        if tail_name not in nodes_dict:
                            nodes_dict[tail_name] = GraphNode(
                                id=tail_name,
                                name=tail_name,
                                type="entity",
                                properties={}
                            )
                        
                        # 添加关系边
                        edge_id = f"{head_name}_{relation['relation_name']}_{tail_name}_{relation.get('id', '')}"
                        edge = GraphEdge(
                            id=edge_id,
                            source=head_name,
                            target=tail_name,
                            type=relation['relation_name'],
                            relation_type=relation['relation_name'],  # 异常25修复：添加relation_type字段保持兼容性
                            properties={
                                "confidence": float(relation.get('confidence', 1.0)),
                                "description": relation.get('description'),
                                "evidence_text": relation.get('evidence_text')
                            }
                        )
                        edges.append(edge)
                    
                    nodes = list(nodes_dict.values())
                    metadata = {
                        "document_id": document_id,
                        "table_name": table_name,
                        "node_count": len(nodes),
                        "edge_count": len(edges)
                    }
                    
                    return KnowledgeGraphResponse(nodes=nodes, edges=edges, metadata=metadata)
                    
                except Exception as e:
                    logger.error(f"查询关系表失败: {str(e)}")
                    # 返回空图谱而不是抛出异常
                    return KnowledgeGraphResponse(
                        nodes=[],
                        edges=[],
                        metadata={
                            "document_id": document_id,
                            "error": str(e)
                        }
                    )
    
    # ==================== 异常14新增：支持 documentID_entitys/relations/knowledges 表 ====================
    
    def _generate_entity_table_name(self, document_id: str) -> str:
        """生成实体表名：documentID_entitys"""
        # 清理document_id，确保只包含字母数字和下划线
        clean_id = re.sub(r'[^\w]', '_', str(document_id))
        return f"{clean_id}_entitys"
    
    def _generate_relation_table_name(self, document_id: str) -> str:
        """生成关系表名：documentID_relations"""
        # 清理document_id，确保只包含字母数字和下划线
        clean_id = re.sub(r'[^\w]', '_', str(document_id))
        return f"{clean_id}_relations"
    
    def _generate_knowledge_table_name(self, document_id: str) -> str:
        """生成知识表名：documentID_knowledges"""
        # 清理document_id，确保只包含字母数字和下划线
        clean_id = re.sub(r'[^\w]', '_', str(document_id))
        return f"{clean_id}_knowledges"
    
    async def check_entity_table_exists(self, document_id: str) -> bool:
        """检查实体表是否存在"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_entity_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = %s
                """, (table_name,))
                result = await cursor.fetchone()
                return result[0] > 0
    
    async def check_relation_table_exists(self, document_id: str) -> bool:
        """检查关系表是否存在"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_relation_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = %s
                """, (table_name,))
                result = await cursor.fetchone()
                return result[0] > 0
    
    async def check_knowledge_table_exists(self, document_id: str) -> bool:
        """检查知识表是否存在"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_knowledge_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = %s
                """, (table_name,))
                result = await cursor.fetchone()
                return result[0] > 0
    
    async def create_entity_table(self, document_id: str):
        """创建实体表：documentID_entitys（异常35修复：支持表结构升级）"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_entity_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
                    entity_id VARCHAR(50) COMMENT '实体ID（异常34修复：改为VARCHAR支持E-0001格式）',
                    entity_name VARCHAR(255) NOT NULL COMMENT '实体名称',
                    entity_type VARCHAR(100) COMMENT '实体类型（异常41修复：添加entity_type字段）',
                    attributes JSON COMMENT '属性值',
                    description TEXT COMMENT '描述',
                    confidence DECIMAL(3,2) DEFAULT 1.0 COMMENT '置信度(0.00-1.00)',
                    position JSON COMMENT '在文档中的位置信息',
                    occurrence_count INT DEFAULT 0 COMMENT '出现次数',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_entity_name (entity_name),
                    INDEX idx_entity_type (entity_type),
                    INDEX idx_entity_id (entity_id),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档实体表'
                """
                await cursor.execute(create_table_sql)
                
                # 异常35修复：检查并升级现有表结构
                await self._upgrade_entity_table_if_needed(cursor, table_name)
                
                await conn.commit()
                logger.info(f"Created/upgraded entity table: {table_name}")
    
    async def _upgrade_entity_table_if_needed(self, cursor, table_name: str):
        """检查并升级实体表结构（异常35修复）"""
        try:
            # 检查entity_id字段类型
            await cursor.execute(f"""
                SELECT COLUMN_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = '{table_name}' 
                AND COLUMN_NAME = 'entity_id'
            """)
            result = await cursor.fetchone()
            
            if result and 'int' in result[0].lower():
                logger.info(f"发现旧版entity_id字段类型为INT，正在升级为VARCHAR(50)...")
                await cursor.execute(f"""
                    ALTER TABLE {table_name} 
                    MODIFY COLUMN entity_id VARCHAR(50) COMMENT '实体ID（异常35修复：升级为VARCHAR支持E-0001格式）'
                """)
                logger.info(f"成功升级entity_id字段类型：{table_name}")
                
        except Exception as e:
            logger.warning(f"升级实体表结构时出现问题: {e}")
            # 不抛出异常，允许继续执行
    
    async def create_relation_table(self, document_id: str):
        """创建关系表：documentID_relations（异常35修复：支持表结构升级）"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_relation_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
                    relation_id VARCHAR(50) COMMENT '关系ID（异常34修复：改为VARCHAR支持R-0001格式）',
                    relation_name VARCHAR(255) NOT NULL COMMENT '关系名称',
                    head_entity VARCHAR(255) NOT NULL COMMENT '头实体名称',
                    tail_entity VARCHAR(255) NOT NULL COMMENT '尾实体名称',
                    confidence DECIMAL(3,2) DEFAULT 1.0 COMMENT '置信度(0.00-1.00)',
                    description TEXT COMMENT '关系描述',
                    evidence_text TEXT COMMENT '证据文本',
                    head_entity_id VARCHAR(50) COMMENT '头实体ID（异常34修复：改为VARCHAR支持E-0001格式）',
                    head_entity_name VARCHAR(255) COMMENT '头实体名称（兼容字段）',
                    tail_entity_id VARCHAR(50) COMMENT '尾实体ID（异常34修复：改为VARCHAR支持E-0001格式）',
                    tail_entity_name VARCHAR(255) COMMENT '尾实体名称（兼容字段）',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_relation_name (relation_name),
                    INDEX idx_head_entity (head_entity),
                    INDEX idx_tail_entity (tail_entity),
                    INDEX idx_created_at (created_at),
                    UNIQUE KEY uniq_relation_triple (relation_id, head_entity_id, tail_entity_id) COMMENT '异常43修复：复合唯一索引'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档关系表（异常17修复：完整字段）'
                """
                await cursor.execute(create_table_sql)
                
                # 异常35修复：检查并升级现有表结构
                await self._upgrade_relation_table_if_needed(cursor, table_name)
                
                await conn.commit()
                logger.info(f"Created/upgraded relation table: {table_name}")
    
    async def _upgrade_relation_table_if_needed(self, cursor, table_name: str):
        """检查并升级关系表结构（异常35修复）"""
        try:
            # 需要升级的字段列表
            fields_to_check = [
                ('relation_id', 'VARCHAR(50)', '关系ID（异常35修复：升级为VARCHAR支持R-0001格式）'),
                ('head_entity_id', 'VARCHAR(50)', '头实体ID（异常35修复：升级为VARCHAR支持E-0001格式）'),
                ('tail_entity_id', 'VARCHAR(50)', '尾实体ID（异常35修复：升级为VARCHAR支持E-0001格式）')
            ]
            
            for field_name, target_type, comment in fields_to_check:
                await cursor.execute(f"""
                    SELECT COLUMN_TYPE 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = '{table_name}' 
                    AND COLUMN_NAME = '{field_name}'
                """)
                result = await cursor.fetchone()
                
                if result and 'int' in result[0].lower():
                    logger.info(f"发现旧版{field_name}字段类型为INT，正在升级为{target_type}...")
                    await cursor.execute(f"""
                        ALTER TABLE {table_name} 
                        MODIFY COLUMN {field_name} {target_type} COMMENT '{comment}'
                    """)
                    logger.info(f"成功升级{field_name}字段类型：{table_name}")
                    
        except Exception as e:
            logger.warning(f"升级关系表结构时出现问题: {e}")
            # 不抛出异常，允许继续执行
    
    async def create_knowledge_table_new(self, document_id: str):
        """创建知识表：documentID_knowledges（与关系表结构相同）"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_knowledge_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
                    relation_id VARCHAR(50) COMMENT '关系ID（异常34修复：改为VARCHAR支持R-0001格式）',
                    relation_name VARCHAR(255) NOT NULL COMMENT '关系名称',
                    head_entity_id VARCHAR(50) COMMENT '头实体ID（异常34修复：改为VARCHAR支持E-0001格式）',
                    head_entity_name VARCHAR(255) NOT NULL COMMENT '头实体名称',
                    tail_entity_id VARCHAR(50) COMMENT '尾实体ID（异常34修复：改为VARCHAR支持E-0001格式）',
                    tail_entity_name VARCHAR(255) NOT NULL COMMENT '尾实体名称',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_relation_name (relation_name),
                    INDEX idx_head_entity (head_entity_name),
                    INDEX idx_tail_entity (tail_entity_name),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档知识表'
                """
                await cursor.execute(create_table_sql)
                await conn.commit()
                logger.info(f"Created knowledge table: {table_name}")
    
    async def get_entities_from_table(self, document_id: str) -> List[Entity]:
        """从实体表中获取实体列表"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_entity_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    await cursor.execute(f"SELECT * FROM {table_name}")
                    entities_data = await cursor.fetchall()
                    
                    entities = []
                    for entity_data in entities_data:
                        # 异常21修复：处理JSON字段，确保正确解析字符串
                        attributes_raw = entity_data.get('attributes')
                        position_raw = entity_data.get('position')
                        
                        # 解析JSON字符串为字典
                        attributes = None
                        if attributes_raw:
                            if isinstance(attributes_raw, str):
                                try:
                                    attributes = json.loads(attributes_raw)
                                except (json.JSONDecodeError, TypeError):
                                    attributes = None
                            elif isinstance(attributes_raw, dict):
                                attributes = attributes_raw
                        
                        # 解析位置信息
                        position = None
                        if position_raw:
                            if isinstance(position_raw, str):
                                try:
                                    position = json.loads(position_raw)
                                except (json.JSONDecodeError, TypeError):
                                    position = None
                            else:
                                position = position_raw
                        
                        entity = Entity(
                            entity_id=entity_data.get('entity_id'),
                            entity_name=entity_data['entity_name'],
                            type=entity_data.get('entity_type'),  # 异常52修复：从entity_type字段获取类型
                            attributes=attributes,
                            description=entity_data.get('description'),
                            confidence=float(entity_data.get('confidence', 1.0)),
                            position=position,
                            occurrence_count=entity_data.get('occurrence_count', 0)
                        )
                        entities.append(entity)
                    
                    return entities
                except Exception as e:
                    logger.error(f"Error getting entities from table {table_name}: {e}")
                    return []
    
    async def get_relations_from_table(self, document_id: str) -> List[Relation]:
        """从关系表中获取关系列表"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_relation_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    await cursor.execute(f"SELECT * FROM {table_name}")
                    relations_data = await cursor.fetchall()
                    
                    relations = []
                    for relation_data in relations_data:
                        # 异常21修复：确保关系数据正确映射，支持完整字段
                        relation = Relation(
                            id=relation_data.get('id'),
                            relation_id=str(relation_data.get('relation_id', '')),
                            relation_name=relation_data.get('relation_name', ''),
                            head_entity=relation_data.get('head_entity', '') or relation_data.get('head_entity_name', ''),
                            tail_entity=relation_data.get('tail_entity', '') or relation_data.get('tail_entity_name', ''),
                            head_entity_id=relation_data.get('head_entity_id'),
                            head_entity_name=relation_data.get('head_entity_name', ''),
                            tail_entity_id=relation_data.get('tail_entity_id'),
                            tail_entity_name=relation_data.get('tail_entity_name', ''),
                            # 异常17新增字段支持
                            confidence=float(relation_data.get('confidence', 1.0)),
                            description=relation_data.get('description'),
                            evidence_text=relation_data.get('evidence_text')
                        )
                        relations.append(relation)
                    
                    return relations
                except Exception as e:
                    logger.error(f"Error getting relations from table {table_name}: {e}")
                    return []
    
    async def save_entities_to_table(self, document_id: str, entities: List[Entity]):
        """保存实体到实体表（异常18修复：基于ID的插入/更新逻辑）"""
        if self.pool is None:
            await self.initialize()
        
        # 异常18修复：先检查表是否存在，不存在才创建
        table_exists = await self.check_entity_table_exists(document_id)
        if not table_exists:
            await self.create_entity_table(document_id)
            logger.info(f"Created new entity table for document {document_id}")
        
        table_name = self._generate_entity_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 异常18修复：基于entity_id的插入/更新逻辑
                for entity in entities:
                    entity_id = getattr(entity, 'entity_id', None)
                    if entity_id is None:
                        continue  # 跳过没有ID的实体
                    
                    # 检查实体是否已存在
                    await cursor.execute(
                        f"SELECT id, entity_name, attributes, description, confidence, position, occurrence_count FROM {table_name} WHERE entity_id = %s", 
                        (entity_id,)
                    )
                    existing = await cursor.fetchone()
                    
                    # 准备新数据
                    attributes_json = json.dumps(entity.attributes, ensure_ascii=False) if entity.attributes else None
                    position_json = json.dumps([pos.dict() for pos in entity.position] if entity.position else None, ensure_ascii=False)
                    
                    if existing:
                        # 检查数据是否有变化（比较关键字段）
                        data_changed = (
                            existing[1] != entity.entity_name or
                            existing[2] != attributes_json or
                            existing[3] != entity.description or
                            existing[4] != entity.confidence or
                            existing[5] != position_json or
                            existing[6] != entity.occurrence_count
                        )
                        
                        if data_changed:
                            # 更新现有记录
                            update_sql = f"""
                                UPDATE {table_name} 
                                SET entity_name = %s, attributes = %s, description = %s, 
                                    confidence = %s, position = %s, occurrence_count = %s, 
                                    updated_at = NOW()
                                WHERE entity_id = %s
                            """
                            await cursor.execute(update_sql, (
                                entity.entity_name, attributes_json, entity.description,
                                entity.confidence, position_json, entity.occurrence_count, entity_id
                            ))
                            logger.debug(f"Updated entity {entity_id} in table {table_name}")
                        else:
                            logger.debug(f"Entity {entity_id} unchanged, skipping update")
                    else:
                        # 插入新记录
                        insert_sql = f"""
                            INSERT INTO {table_name} 
                            (entity_id, entity_name, attributes, description, confidence, position, occurrence_count)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """
                        await cursor.execute(insert_sql, (
                            entity_id, entity.entity_name, attributes_json,
                            entity.description, entity.confidence, position_json, entity.occurrence_count
                        ))
                        logger.debug(f"Inserted new entity {entity_id} into table {table_name}")
                
                await conn.commit()
                logger.info(f"Processed {len(entities)} entities for table {table_name}")
                logger.info(f"Saved {len(entities)} entities to table {table_name}")
    
    async def save_relations_to_table(self, document_id: str, relations: List[Relation]):
        """保存关系到关系表（异常18修复：基于ID的插入/更新逻辑）"""
        if self.pool is None:
            await self.initialize()
        
        # 异常18修复：先检查表是否存在，不存在才创建
        table_exists = await self.check_relation_table_exists(document_id)
        if not table_exists:
            await self.create_relation_table(document_id)
            logger.info(f"Created new relation table for document {document_id}")
        
        table_name = self._generate_relation_table_name(document_id)
        # 生成relation_id的计数器
        relation_counter = 1

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 获取当前最大的relation_id数字，用于生成新ID
                await cursor.execute(f"SELECT MAX(CAST(SUBSTRING(relation_id, 3) AS UNSIGNED)) as max_id FROM {table_name} WHERE relation_id REGEXP '^R-[0-9]+$'")
                max_result = await cursor.fetchone()
                if max_result and max_result['max_id']:
                    relation_counter = max_result['max_id'] + 1

                # 异常49修复：基于语义三元组的唯一性检查
                for relation in relations:
                    # 准备数据
                    head_entity_id = getattr(relation, 'head_entity_id', None) or ''
                    tail_entity_id = getattr(relation, 'tail_entity_id', None) or ''
                    relation_name = getattr(relation, 'relation_name', '')
                    head_entity = getattr(relation, 'head_entity', '')
                    tail_entity = getattr(relation, 'tail_entity', '')
                    confidence = getattr(relation, 'confidence', 1.0)
                    description = getattr(relation, 'description', None)
                    evidence_text = getattr(relation, 'evidence_text', None)
                    head_entity_name = getattr(relation, 'head_entity_name', None) or head_entity
                    tail_entity_name = getattr(relation, 'tail_entity_name', None) or tail_entity

                    # 检查语义三元组是否已存在
                    existing_relation_id = await self.check_semantic_triplet_exists(
                        document_id, relation_name, head_entity, tail_entity
                    )

                    if existing_relation_id:
                        # 如果语义三元组已存在，使用已有的relation_id进行更新
                        update_sql = f"""
                            UPDATE {table_name}
                            SET confidence = %s, description = %s, evidence_text = %s,
                                head_entity_id = %s, head_entity_name = %s,
                                tail_entity_id = %s, tail_entity_name = %s,
                                updated_at = NOW()
                            WHERE relation_id = %s
                        """
                        await cursor.execute(update_sql, (
                            confidence, description, evidence_text,
                            head_entity_id, head_entity_name, tail_entity_id, tail_entity_name,
                            existing_relation_id
                        ))
                        logger.debug(f"Updated existing relation: {existing_relation_id} for ({relation_name}, {head_entity}, {tail_entity})")
                    else:
                        # 如果语义三元组不存在，生成新的relation_id并插入
                        new_relation_id = f"R-{str(relation_counter).zfill(4)}"
                        relation_counter += 1

                        insert_sql = f"""
                            INSERT INTO {table_name}
                            (relation_id, relation_name, head_entity, tail_entity, confidence, description, evidence_text,
                             head_entity_id, head_entity_name, tail_entity_id, tail_entity_name)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cursor.execute(insert_sql, (
                            new_relation_id, relation_name, head_entity, tail_entity,
                            confidence, description, evidence_text,
                            head_entity_id, head_entity_name, tail_entity_id, tail_entity_name
                        ))
                        logger.debug(f"Inserted new relation: {new_relation_id} for ({relation_name}, {head_entity}, {tail_entity})")

                await conn.commit()
                logger.info(f"Processed {len(relations)} relations for table {table_name}")

    async def check_semantic_triplet_exists(self, document_id: str, relation_name: str, head_entity: str, tail_entity: str):
        """检查语义三元组是否已存在，返回已存在的relation_id"""
        if self.pool is None:
            await self.initialize()

        # 先检查表是否存在
        table_exists = await self.check_relation_table_exists(document_id)
        if not table_exists:
            return None  # 表不存在，肯定没有重复

        table_name = self._generate_relation_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    query = f"""
                    SELECT relation_id
                    FROM {table_name}
                    WHERE relation_name = %s AND head_entity = %s AND tail_entity = %s
                    LIMIT 1
                    """
                    await cursor.execute(query, (relation_name, head_entity, tail_entity))
                    result = await cursor.fetchone()
                    return result['relation_id'] if result else None
                except Exception as e:
                    logger.warning(f"Error checking semantic triplet: {e}")
                    return None

    async def get_knowledges_from_table(self, document_id: str) -> List[Relation]:
        """从知识表中获取知识列表（与关系表结构相同）"""
        if self.pool is None:
            await self.initialize()
        
        table_name = self._generate_knowledge_table_name(document_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    await cursor.execute(f"SELECT * FROM {table_name}")
                    knowledges_data = await cursor.fetchall()
                    
                    knowledges = []
                    for knowledge_data in knowledges_data:
                        knowledge = Relation(
                            id=knowledge_data.get('relation_id'),
                            relation_id=str(knowledge_data.get('relation_id', '')),
                            relation_name=knowledge_data['relation_name'],
                            head_entity=knowledge_data['head_entity_name'],
                            tail_entity=knowledge_data['tail_entity_name'],
                            head_entity_id=knowledge_data.get('head_entity_id'),
                            head_entity_name=knowledge_data['head_entity_name'],
                            tail_entity_id=knowledge_data.get('tail_entity_id'),
                            tail_entity_name=knowledge_data['tail_entity_name']
                        )
                        knowledges.append(knowledge)
                    
                    return knowledges
                except Exception as e:
                    logger.error(f"Error getting knowledges from table {table_name}: {e}")
                    return []
    
    async def save_knowledges_to_table(self, document_id: str, relations: List[Relation]):
        """异常42修复：保存知识到全局知识表，实现双重保存机制"""
        if self.pool is None:
            await self.initialize()

        # 异常42修复：双重保存 - 1. 先保存到文档级关系表
        await self.save_relations_to_table(document_id, relations)
        print("更新2")

        # 异常42修复：双重保存 - 2. 再保存到全局知识表
        await self._save_to_global_knowledges_table(relations)

    async def _save_to_global_knowledges_table(self, relations: List[Relation]):
        """异常42修复：保存到全局知识表（knowledges表）"""
        if self.pool is None:
            await self.initialize()
        print("更新3")
        # 检查全局知识表是否存在，不存在则创建
        table_exists = await self._check_global_knowledges_table_exists()
        print("更新4")
        if not table_exists:
            print("更新5")
            await self._create_global_knowledges_table()
            logger.info("Created global knowledges table")
        print("更新6")
        table_name = "knowledges"  # 全局知识表名
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 异常43修复：使用INSERT ... ON DUPLICATE KEY UPDATE实现upsert
                for relation in relations:
                    relation_id = getattr(relation, 'id', None) or getattr(relation, 'relation_id', None)
                    if relation_id is None:
                        continue  # 跳过没有ID的知识

                    # 准备数据
                    head_entity_id = getattr(relation, 'head_entity_id', None) or ''
                    tail_entity_id = getattr(relation, 'tail_entity_id', None) or ''
                    relation_name = getattr(relation, 'relation_name', '')
                    head_entity = getattr(relation, 'head_entity_name', None) or getattr(relation, 'head_entity', '')
                    tail_entity = getattr(relation, 'tail_entity_name', None) or getattr(relation, 'tail_entity', '')
                    description = getattr(relation, 'description', '')
                    evidence_text = getattr(relation, 'evidence_text', '')
                    confidence = getattr(relation, 'confidence', 1.0)

                    # 使用INSERT ... ON DUPLICATE KEY UPDATE实现upsert（异常43修复）
                    upsert_sql = f"""
                        INSERT INTO {table_name}
                        (relation_id, relation_name, head_entity_id, head_entity_name,
                         tail_entity_id, tail_entity_name, description, evidence_text, confidence)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            relation_name = VALUES(relation_name),
                            head_entity_name = VALUES(head_entity_name),
                            tail_entity_name = VALUES(tail_entity_name),
                            description = VALUES(description),
                            evidence_text = VALUES(evidence_text),
                            confidence = VALUES(confidence),
                            updated_at = NOW()
                    """
                    await cursor.execute(upsert_sql, (
                        relation_id, relation_name, head_entity_id, head_entity,
                        tail_entity_id, tail_entity, description, evidence_text, confidence
                    ))
                    logger.debug(f"Upserted knowledge triple: ({relation_id}, {head_entity_id}, {tail_entity_id})")

                await conn.commit()
                logger.info(f"Processed {len(relations)} relations for global knowledges table")

    async def _check_global_knowledges_table_exists(self) -> bool:
        """异常42修复：检查全局知识表是否存在"""
        if self.pool is None:
            await self.initialize()

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_name = 'knowledges'
                """)
                result = await cursor.fetchone()
                return result[0] > 0

    async def _create_global_knowledges_table(self):
        """异常42修复：创建全局知识表"""
        if self.pool is None:
            await self.initialize()

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS knowledges (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
                    relation_id VARCHAR(50) NOT NULL COMMENT '关系ID',
                    relation_name VARCHAR(255) NOT NULL COMMENT '关系名称',
                    head_entity_id VARCHAR(50) COMMENT '头实体ID',
                    head_entity_name VARCHAR(255) NOT NULL COMMENT '头实体名称',
                    tail_entity_id VARCHAR(50) COMMENT '尾实体ID',
                    tail_entity_name VARCHAR(255) NOT NULL COMMENT '尾实体名称',
                    description TEXT COMMENT '关系描述',
                    evidence_text TEXT COMMENT '证据文本',
                    confidence DECIMAL(3,2) DEFAULT 1.0 COMMENT '置信度',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_relation_id (relation_id),
                    UNIQUE INDEX idx_global_triple (relation_id, head_entity_id, tail_entity_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全局知识表'
                """
                await cursor.execute(create_table_sql)
                await conn.commit()
                logger.info("Global knowledges table created successfully")

    async def get_global_knowledges(self) -> List[Relation]:
        """异常52修复：从所有文档的关系表中聚合所有知识"""
        if self.pool is None:
            await self.initialize()

        all_relations = []

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    # 1. 获取所有关系表
                    await cursor.execute("""
                        SELECT table_name FROM information_schema.tables
                        WHERE table_schema = DATABASE() AND table_name LIKE '%_relations'
                    """)
                    relation_tables = await cursor.fetchall()

                    logger.info(f"找到 {len(relation_tables)} 个关系表用于聚合")

                    # 2. 从每个关系表中获取数据
                    for table_info in relation_tables:
                        try:
                            # 异常53修复：安全获取table_name，支持不同返回格式
                            if isinstance(table_info, dict):
                                table_name = table_info.get('table_name') or table_info.get('TABLE_NAME')
                            else:
                                table_name = table_info[0] if isinstance(table_info, (tuple, list)) else str(table_info)

                            if not table_name:
                                logger.warning(f"无法获取表名从 {table_info}")
                                continue

                            await cursor.execute(f"SELECT * FROM {table_name}")
                            table_data = await cursor.fetchall()

                            # 3. 转换为Relation对象
                            for row in table_data:
                                try:
                                    relation = Relation(
                                        id=row.get('id'),
                                        relation_id=row.get('relation_id'),
                                        relation_name=row.get('relation_name', ''),
                                        head_entity=row.get('head_entity', ''),
                                        tail_entity=row.get('tail_entity', ''),
                                        head_entity_id=row.get('head_entity_id'),
                                        tail_entity_id=row.get('tail_entity_id'),
                                        description=row.get('description', ''),
                                        evidence_text=row.get('evidence_text', ''),
                                        confidence=float(row.get('confidence', 1.0))
                                    )
                                    all_relations.append(relation)
                                except Exception as row_error:
                                    logger.warning(f"无法解析行数据 {row}: {row_error}")
                                    continue

                            logger.info(f"从表 {table_name} 获取了 {len(table_data)} 条关系")

                        except Exception as table_error:
                            logger.warning(f"无法查询表 {table_info}: {table_error}")
                            continue

                    # 4. 数据去重（基于关系名和实体对）
                    unique_relations = {}
                    for relation in all_relations:
                        key = f"{relation.head_entity}_{relation.relation_name}_{relation.tail_entity}"
                        if key not in unique_relations:
                            unique_relations[key] = relation

                    logger.info(f"聚合完成：从 {len(relation_tables)} 个表中获取了 {len(all_relations)} 条关系，去重后 {len(unique_relations)} 条")
                    return list(unique_relations.values())
                except Exception as e:
                    logger.error(f"Error getting global knowledges: {e}")
                    return []

    # ==================== 文档治理功能相关方法 ====================
    
    async def get_documents(self, status: Optional[int] = None, limit: Optional[int] = None, offset: Optional[int] = 0) -> List[DocumentGovernanceListItem]:
        """获取文档列表"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 构建查询条件
                where_clause = ""
                params = []
                if status is not None:
                    where_clause = "WHERE status = %s"
                    params.append(status)
                
                # 构建查询SQL
                sql = f"""
                    SELECT id, name, file_path, pdf_path, status, upload_time, update_time, upload_user
                    FROM documents 
                    {where_clause}
                    ORDER BY update_time DESC
                """
                
                if limit is not None:
                    sql += " LIMIT %s OFFSET %s"
                    params.extend([limit, offset])
                
                await cursor.execute(sql, params)
                documents_data = await cursor.fetchall()
                
                # 转换为响应模型
                documents = []
                for doc in documents_data:
                    status_text = self._get_status_text(doc['status'])
                    documents.append(DocumentGovernanceListItem(
                        id=doc['id'],
                        name=doc['name'],
                        file_path=doc['file_path'],
                        pdf_path=doc['pdf_path'],
                        status=doc['status'],
                        status_text=status_text,
                        upload_time=doc['upload_time'],
                        update_time=doc['update_time'],
                        upload_user=doc['upload_user'],
                        can_review=(doc['status'] == 0),  # 只有待审核状态可以审核
                        can_delete=(doc['status'] != 2)   # 已删除状态不能再删除
                    ))
                
                return documents

    async def get_document_by_id(self, document_id: int) -> Optional[DocumentGovernance]:
        """根据ID获取文档详情"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT id, name, file_path, pdf_path, status, upload_time, update_time, 
                           json_file_path, image_file_path, upload_user
                    FROM documents 
                    WHERE id = %s 
                """, (document_id,))
                
                doc_data = await cursor.fetchone()
                if doc_data:
                    return DocumentGovernance(**doc_data)
                return None

    async def create_document(self, document: DocumentGovernanceCreate) -> int:
        """创建新文档"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO documents 
                    (name, file_path, json_file_path, image_file_path, upload_user)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    document.name,
                    document.file_path,
                    document.json_file_path,
                    document.image_file_path,
                    document.upload_user
                ))
                await conn.commit()
                return cursor.lastrowid

    async def update_document(self, document_id: int, document: DocumentGovernanceUpdate) -> bool:
        """更新文档信息"""
        if self.pool is None:
            await self.initialize()
        
        # 构建动态更新SQL
        updates = []
        values = []
        
        if document.name is not None:
            updates.append("name = %s")
            values.append(document.name)
        if document.file_path is not None:
            updates.append("file_path = %s")
            values.append(document.file_path)
        if document.status is not None:
            updates.append("status = %s")
            values.append(document.status)
        if document.json_file_path is not None:
            updates.append("json_file_path = %s")
            values.append(document.json_file_path)
        if document.image_file_path is not None:
            updates.append("image_file_path = %s")
            values.append(document.image_file_path)
        if document.upload_user is not None:
            updates.append("upload_user = %s")
            values.append(document.upload_user)
        
        if not updates:
            return False
        
        values.append(document_id)
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"""
                    UPDATE documents 
                    SET {', '.join(updates)}
                    WHERE id = %s
                """, values)
                await conn.commit()
                return cursor.rowcount > 0

    async def delete_document(self, document_id: int, force_delete: bool = False) -> bool:
        """删除文档（逻辑删除或物理删除）"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if force_delete:
                    # 物理删除
                    await cursor.execute("DELETE FROM documents WHERE id = %s", (document_id,))
                else:
                    # 逻辑删除（设置status为2）
                    await cursor.execute("UPDATE documents SET status = 2 WHERE id = %s", (document_id,))
                
                await conn.commit()
                return cursor.rowcount > 0

    async def update_document_status(self, document_id: int, status: int) -> bool:
        """更新文档状态"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    UPDATE documents 
                    SET status = %s 
                    WHERE id = %s
                """, (status, document_id))
                await conn.commit()
                return cursor.rowcount > 0

    async def get_documents_count(self, status: Optional[int] = None) -> int:
        """获取文档总数"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if status is not None:
                    await cursor.execute("SELECT COUNT(*) FROM documents WHERE status = %s", (status,))
                else:
                    await cursor.execute("SELECT COUNT(*) FROM documents")
                
                result = await cursor.fetchone()
                return result[0] if result else 0

    def _get_status_text(self, status: int) -> str:
        """获取状态文本"""
        status_map = {
            0: "待审核",
            1: "已审核", 
            2: "已删除"
        }
        return status_map.get(status, "未知状态")