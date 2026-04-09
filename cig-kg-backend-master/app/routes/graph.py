from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List, Optional
import logging
from app.dependencies.dependencies import get_mongo_service, get_mongo_service_extended, get_mysql_service, get_prompt_service
from app.utils.json_validator import JSONValidator
from app.services.mongo_service import MongoService
from app.services.mongo_service_extended import MongoServiceExtended
from app.services.mysql_service import MySQLService
from app.services.prompt_service import PromptService
from app.services.chunked_ie import ChunkedIEService
from app.models.schemas import (
    Document, DocumentSummary, DocumentDetail, Term, Entity, Relation,
    EntityExtractionRequest, RelationExtractionRequest,
    EntityStorageRequest, RelationStorageRequest,
    KnowledgeStorageRequest, KnowledgeStorageRequestNew, KnowledgeGraphResponse, KnowledgeGraphOption, APIResponse, TermFilterRequest,
    TermCreateRequest, TermUpdateRequest, GraphNode, GraphEdge
)

router = APIRouter()
logger = logging.getLogger(__name__)

# 3.1 文档管理接口

@router.get("/documents", response_model=List[DocumentSummary])
async def get_documents(
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended)
):
    """从 cigarette_kg.documents 获取文档列表"""
    try:
        # 强制使用cigarette_kg.documents数据库
        documents_data = await mongo_service_extended.get_documents_from_juanyan()
        return [
            DocumentSummary(
                document_id=doc["document_id"],
                name=doc["name"],
                created_at=doc.get("created_at"),
                _id=doc.get("_id")
            ) for doc in documents_data
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档失败: {str(e)}")

@router.get("/documents/{document_id}")
async def get_document_detail(
    document_id: str,
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended)
):
    """根据document_id获取文档详情，包含json_data字段内容 (异常12修复)"""
    try:
        # 强制使用cigarette_kg.documents数据库
        doc_data = await mongo_service_extended.get_document_by_document_id(document_id)
        if not doc_data:
            raise HTTPException(status_code=404, detail=f"文档 {document_id} 不存在")
        
        # 异常12修复：创建安全的JSON响应
        safe_response = JSONValidator.create_fastapi_safe_response(doc_data)
        
        return JSONResponse(
            content=safe_response,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
    except HTTPException:
        raise
    except Exception as e:
        error_response = {
            "error": "获取文档详情失败",
            "detail": str(e),
            "document_id": document_id
        }
        return JSONResponse(
            content=error_response,
            status_code=500,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )

# 3.2 术语库管理接口

@router.get("/terms", response_model=List[Term])
async def get_terms(
    term_type: Optional[str] = Query(None, description="术语类型筛选: 实体/关系"),
    search: Optional[str] = Query(None, description="搜索关键字"),
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """从 MySQL 获取术语库，支持按类型筛选和关键字搜索"""
    try:
        all_terms = await mysql_service.get_terms()
        
        # 应用筛选条件
        filtered_terms = all_terms
        
        if term_type:
            filtered_terms = [term for term in filtered_terms if term.type == term_type]
        
        if search:
            search_lower = search.lower()
            filtered_terms = [
                term for term in filtered_terms 
                if search_lower in term.name.lower() or 
                (term.description and search_lower in term.description.lower())
            ]
        
        return filtered_terms
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取术语库失败: {str(e)}")

# 异常41修复：术语管理接口
@router.post("/terms", response_model=Term)
async def create_term(
    request: TermCreateRequest,
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """新增术语"""
    try:
        if not request.name.strip():
            raise HTTPException(status_code=400, detail="术语名称不能为空")

        if request.type not in ['实体', '关系']:
            raise HTTPException(status_code=400, detail="术语类型必须是'实体'或'关系'")

        term_id = await mysql_service.add_term(
            name=request.name.strip(),
            term_type=request.type,
            description=request.description
        )

        return Term(
            id=term_id,
            name=request.name.strip(),
            type=request.type,
            description=request.description
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建术语失败: {str(e)}")

@router.put("/terms/{term_id}", response_model=APIResponse)
async def update_term(
    term_id: int,
    request: TermUpdateRequest,
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """修改术语"""
    try:
        if term_id <= 0:
            raise HTTPException(status_code=400, detail="无效的术语ID")

        # 验证术语类型
        if request.type and request.type not in ['实体', '关系']:
            raise HTTPException(status_code=400, detail="术语类型必须是'实体'或'关系'")

        # 验证术语名称
        name = request.name.strip() if request.name else None
        if name == "":
            raise HTTPException(status_code=400, detail="术语名称不能为空")

        await mysql_service.update_term(
            term_id=term_id,
            name=name,
            term_type=request.type,
            description=request.description
        )

        return APIResponse(
            success=True,
            message="术语更新成功",
            data={"term_id": term_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新术语失败: {str(e)}")

@router.delete("/terms/{term_id}", response_model=APIResponse)
async def delete_term(
    term_id: int,
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """删除术语"""
    try:
        if term_id <= 0:
            raise HTTPException(status_code=400, detail="无效的术语ID")

        await mysql_service.delete_term(term_id)

        return APIResponse(
            success=True,
            message="术语删除成功",
            data={"term_id": term_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除术语失败: {str(e)}")

# 异常41修复：统一知识图谱接口
@router.get("/unified-knowledge-graph", response_model=KnowledgeGraphResponse)
async def get_unified_knowledge_graph(mysql_service: MySQLService = Depends(get_mysql_service)):
    """获取全局统一知识图谱数据（异常41修复：支持所有知识选项）"""
    try:
        # 从全局知识表获取所有知识
        global_knowledges = await mysql_service.get_global_knowledges()

        if not global_knowledges:
            return KnowledgeGraphResponse(
                nodes=[],
                edges=[],
                metadata={
                    "source": "global_knowledges",
                    "total_nodes": 0,
                    "total_edges": 0,
                    "message": "暂无全局知识数据"
                }
            )

        # 构建节点和边
        nodes_dict = {}
        edges = []

        for relation in global_knowledges:
            # 添加头实体节点
            head_name = relation.head_entity or relation.head_entity_name
            if head_name and head_name not in nodes_dict:
                nodes_dict[head_name] = GraphNode(
                    id=head_name,
                    name=head_name,
                    type="entity",
                    properties={
                        "entity_id": relation.head_entity_id,
                        "source": "global_knowledge"
                    }
                )

            # 添加尾实体节点
            tail_name = relation.tail_entity or relation.tail_entity_name
            if tail_name and tail_name not in nodes_dict:
                nodes_dict[tail_name] = GraphNode(
                    id=tail_name,
                    name=tail_name,
                    type="entity",
                    properties={
                        "entity_id": relation.tail_entity_id,
                        "source": "global_knowledge"
                    }
                )

            # 添加关系边
            if head_name and tail_name:
                edge_id = f"global_{relation.relation_id}_{relation.id}"
                edge = GraphEdge(
                    id=edge_id,
                    source=head_name,
                    target=tail_name,
                    type=relation.relation_name,
                    relation_type=relation.relation_name,
                    properties={
                        "relation_id": relation.relation_id,
                        "confidence": relation.confidence,
                        "description": relation.description,
                        "evidence_text": relation.evidence_text,
                        "source": "global_knowledge"
                    }
                )
                edges.append(edge)

        nodes = list(nodes_dict.values())
        metadata = {
            "source": "global_knowledges",
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "total_relations": len(global_knowledges),
            "message": f"成功加载全局知识图谱：{len(nodes)} 个实体，{len(edges)} 个关系"
        }

        return KnowledgeGraphResponse(nodes=nodes, edges=edges, metadata=metadata)

    except Exception as e:
        logger.error(f"获取统一知识图谱失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取统一知识图谱失败: {str(e)}")

# 3.3 知识抽取接口

@router.get("/documents/{document_id}/entities")
async def get_document_entities(
    document_id: str,
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """获取文档的实体数据（异常21新增）
    
    逻辑：
    1. 检查文档的实体表是否存在
    2. 如果存在，直接返回表中的实体数据
    3. 如果不存在，返回 exists: false
    """
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 检查实体表是否存在
        table_exists = await mysql_service.check_entity_table_exists(document_id)
        table_name = mysql_service._generate_entity_table_name(document_id)
        
        if table_exists:
            # 从表中读取实体数据
            entities = await mysql_service.get_entities_from_table(document_id)
            # 异常22要求：清晰日志输出
            logger.info(f"检测到表 {table_name} 已存在，返回 {len(entities)} 条数据")
            return {
                "exists": True,
                "entities": entities,
                "count": len(entities),
                "table_name": table_name
            }
        else:
            # 异常22要求：清晰日志输出
            logger.info(f"未检测到表 {table_name}，等待用户选择自动抽取或手动添加")
            return {
                "exists": False,
                "entities": [],
                "count": 0,
                "table_name": table_name
            }
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "exists": False,
            "entities": [],
            "count": 0,
            "error": f"获取实体数据失败: {str(e)}"
        }

@router.post("/entity-extraction", response_model=List[Entity])
async def extract_entities(
    request: EntityExtractionRequest, 
    prompt_service: PromptService = Depends(get_prompt_service),
    mysql_service: MySQLService = Depends(get_mysql_service),
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended)
):
    """实体识别（异常36优化：改进性能和缓存逻辑）
    
    优化逻辑：
    1. 统一缓存检查，避免重复查询
    2. 添加处理超时控制
    3. 优先使用分块抽取逻辑（基于json_data）
    4. 如果没有json_data，回退到原有逻辑
    """
    try:
        # 检查文档是否存在
        if not request.document:
            raise HTTPException(status_code=400, detail="文档信息不能为空")
        
        # 异常36优化：统一缓存检查逻辑，避免重复查询
        cached_entities = None
        if request.document_id:
            table_exists = await mysql_service.check_entity_table_exists(request.document_id)
            if table_exists:
                cached_entities = await mysql_service.get_entities_from_table(request.document_id)
                if cached_entities:
                    logger.info(f"从缓存返回 {len(cached_entities)} 个实体")
                    return cached_entities
        
        # 尝试使用分块抽取逻辑
        if request.document_id:
            logger.info(f"开始分块实体识别，文档ID: {request.document_id}")
            
            try:
                # 异常36优化：直接获取json_data，减少数据库查询
                json_data = await mongo_service_extended.get_json_data(request.document_id)
                if json_data:
                    logger.info("使用分块抽取逻辑")
                    
                    # 执行分块实体识别
                    chunked_service = ChunkedIEService()
                    result = await chunked_service.extract_entities_chunked(
                        document_id=request.document_id,
                        json_data=json_data,
                        terms=request.terms if request.terms else None
                    )
                    
                    # 转换并保存结果
                    if result.get("entities"):
                        entities_to_save = []
                        entities_to_return = []
                        
                        for entity_data in result["entities"]:
                            # 处理位置信息
                            positions = []
                            for pos in entity_data.get("positions", []):
                                from app.models.schemas import EntityPosition
                                position = EntityPosition(
                                    start=pos.get("start", 0),
                                    end=pos.get("end", 0),
                                    context=pos.get("context", "")
                                )
                                positions.append(position)
                            
                            entity = Entity(
                                entity_id=entity_data.get("entity_id"),
                                entity_name=entity_data["entity_name"],
                                type=entity_data.get("entity_type"),
                                attributes=entity_data.get("attributes"),
                                description=entity_data.get("description"),
                                confidence=entity_data.get("confidence", 1.0),
                                position=positions if positions else None,
                                occurrence_count=entity_data.get("occurrence_count", 0)
                            )
                            entities_to_save.append(entity)
                            entities_to_return.append(entity)
                        
                        # 保存到数据库
                        await mysql_service.save_entities_to_table(request.document_id, entities_to_save)
                        logger.info(f"分块实体识别完成，保存了 {len(entities_to_save)} 个实体")
                        
                        return entities_to_return
                    else:
                        return []
                        
            except Exception as e:
                logger.warning(f"分块抽取失败，回退到原有逻辑: {e}")
        
        # 回退到原有逻辑
        logger.info("使用原有实体识别逻辑")
        
        # 异常36优化：此处已经检查过缓存，无需重复检查
        
        # 获取文档内容，允许为空
        document_content = request.document.content or ""
        
        # 如果文档内容为空，返回空的实体列表
        if not document_content.strip():
            return []
        
        # 调用原有的大模型实体识别
        entities = await prompt_service.extract_entities(request.document, request.terms or [])
        return entities
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"实体识别失败: {str(e)}")

@router.post("/save-entities", response_model=APIResponse)
async def save_entities(
    request: EntityStorageRequest,
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """保存用户确认的实体到MySQL（异常14新增）
    
    用户在前端确认实体信息后，调用此接口保存到 documentID_entitys 表
    """
    try:
        if not request.document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        if not request.entities:
            raise HTTPException(status_code=400, detail="实体列表不能为空")
        
        # 保存实体到表
        await mysql_service.save_entities_to_table(request.document_id, request.entities)
        
        return APIResponse(
            success=True,
            message="实体保存成功",
            data={
                "document_id": request.document_id,
                "entities_count": len(request.entities),
                "table_name": mysql_service._generate_entity_table_name(request.document_id)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"实体保存失败: {str(e)}")

@router.get("/documents/{document_id}/relations")
async def get_document_relations(
    document_id: str,
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """获取文档的关系数据（异常21新增）
    
    逻辑：
    1. 检查文档的关系表是否存在
    2. 如果存在，直接返回表中的关系数据
    3. 如果不存在，返回 exists: false
    """
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 检查关系表是否存在
        table_exists = await mysql_service.check_relation_table_exists(document_id)
        table_name = mysql_service._generate_relation_table_name(document_id)
        
        if table_exists:
            # 从表中读取关系数据
            relations = await mysql_service.get_relations_from_table(document_id)
            # 异常22要求：清晰日志输出
            logger.info(f"检测到表 {table_name} 已存在，返回 {len(relations)} 条数据")
            return {
                "exists": True,
                "relations": relations,
                "count": len(relations),
                "table_name": table_name
            }
        else:
            # 异常22要求：清晰日志输出
            logger.info(f"未检测到表 {table_name}，等待用户选择自动抽取或手动添加")
            return {
                "exists": False,
                "relations": [],
                "count": 0,
                "table_name": table_name
            }
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "exists": False,
            "relations": [],
            "count": 0,
            "error": f"获取关系数据失败: {str(e)}"
        }

@router.post("/relation-extraction", response_model=List[Relation])
async def extract_relations(
    request: RelationExtractionRequest, 
    prompt_service: PromptService = Depends(get_prompt_service),
    mysql_service: MySQLService = Depends(get_mysql_service),
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended)
):
    """关系抽取（异常36优化：改进性能和缓存逻辑）
    
    优化逻辑：
    1. 统一缓存检查，避免重复查询
    2. 优先使用分块关系抽取逻辑
    3. 改进错误处理和回退机制
    4. 支持缓存机制和强制重新抽取
    """
    try:
        if not request.entities:
            raise HTTPException(status_code=400, detail="实体列表不能为空")
        
        # 异常36优化：统一缓存检查逻辑，避免重复查询
        cached_relations = None
        if request.document_id:
            table_exists = await mysql_service.check_relation_table_exists(request.document_id)
            if table_exists:
                cached_relations = await mysql_service.get_relations_from_table(request.document_id)
                if cached_relations:
                    logger.info(f"从缓存返回 {len(cached_relations)} 个关系")
                    return cached_relations
        
        # 尝试使用分块抽取逻辑
        if request.document_id:
            logger.info(f"开始分块关系抽取，文档ID: {request.document_id}")
            
            try:
                # 异常36优化：直接获取json_data，减少查询开销
                json_data = await mongo_service_extended.get_json_data(request.document_id)
                if json_data:
                    logger.info("使用分块关系抽取逻辑")
                    
                    # 获取ChunkedIEService实例并执行分块关系抽取
                    chunked_service = ChunkedIEService()
                    chunked_result = await chunked_service.extract_relations_chunked(
                        document_id=request.document_id,
                        entities=request.entities,
                        json_data=json_data,
                        terms=request.terms
                    )
                
                # 提取relations并转换格式
                if "relations" in chunked_result:
                    relations = chunked_result["relations"]
                    logger.info(f"分块关系抽取完成，文档ID: {request.document_id}，抽取到关系数量: {len(relations)}")
                    return relations
                else:
                    logger.warning(f"分块关系抽取未返回relations，回退到原有逻辑")
                    raise ValueError("No relations in chunked result")
                
            except Exception as e:
                logger.warning(f"分块关系抽取失败，回退到原有逻辑: {str(e)}")
        
        # 回退到原有的关系抽取逻辑
        logger.info("使用原有关系抽取逻辑")
        
        # 异常36优化：此处已经检查过缓存，无需重复检查
        
        # 支持无术语的通用关系抽取和有术语的重点关系抽取
        relations = await prompt_service.extract_relations(
            entities=request.entities, 
            terms=request.terms,  # terms为可选，None时使用通用模式
            document_content=request.document_content
        )
        return relations
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关系抽取失败: {str(e)}")

@router.post("/save-relations", response_model=APIResponse)
async def save_relations(
    request: RelationStorageRequest,
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """保存用户确认的关系到MySQL（异常14新增）
    
    用户在前端确认关系信息后，调用此接口保存到 documentID_relations 表
    """
    try:
        if not request.document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        if not request.relations:
            raise HTTPException(status_code=400, detail="关系列表不能为空")
        
        # 保存关系到表
        await mysql_service.save_relations_to_table(request.document_id, request.relations)
        
        return APIResponse(
            success=True,
            message="关系保存成功",
            data={
                "document_id": request.document_id,
                "relations_count": len(request.relations),
                "table_name": mysql_service._generate_relation_table_name(request.document_id)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关系保存失败: {str(e)}")

@router.post("/documents/{document_id}/extract_chunked")
async def extract_chunked_knowledge(
    document_id: str,
    terms: List[Term] = [],
    force: bool = Query(False, description="是否强制重新抽取，覆盖现有数据"),
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended),
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """
    分块知识抽取接口 (异常31新增)
    
    按 page_idx 将文档分 chunk 逐个调用大模型进行实体识别与关系抽取，
    并正确处理跨 chunk 被截断的实体与关系。
    
    Args:
        document_id: 文档ID
        terms: 术语列表（可选）
        force: 是否强制重新抽取
        
    Returns:
        标准化的JSON格式: {"entities": [...], "relations": [...], "meta": {...}}
    """
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
            
        logger.info(f"开始分块知识抽取，文档ID: {document_id}, 术语数量: {len(terms)}, 强制模式: {force}")
        
        # 1. 检查是否已有缓存（如果不是强制模式）
        if not force:
            entity_exists = await mysql_service.check_entity_table_exists(document_id)
            relation_exists = await mysql_service.check_relation_table_exists(document_id)
            
            if entity_exists and relation_exists:
                # 从缓存返回结果
                entities = await mysql_service.get_entities_from_table(document_id)
                relations = await mysql_service.get_relations_from_table(document_id)
                
                logger.info(f"从缓存返回结果: {len(entities)} 实体, {len(relations)} 关系")
                return {
                    "entities": [entity.dict() for entity in entities],
                    "relations": [relation.dict() for relation in relations],
                    "meta": {
                        "document_id": document_id,
                        "total_entities": len(entities),
                        "total_relations": len(relations),
                        "source": "cache",
                        "processing_method": "chunked_extraction"
                    }
                }
        
        # 2. 获取文档的json_data
        doc_data = await mongo_service_extended.get_document_by_document_id(document_id)
        if not doc_data:
            raise HTTPException(status_code=404, detail=f"文档 {document_id} 不存在")
            
        json_data = doc_data.get("json_data", [])
        if not json_data:
            raise HTTPException(status_code=400, detail=f"文档 {document_id} 没有json_data内容")
        
        # 3. 执行分块知识抽取
        chunked_service = ChunkedIEService()
        result = await chunked_service.extract_chunked_knowledge(
            document_id=document_id,
            json_data=json_data,
            terms=terms if terms else None
        )
        
        # 4. 将结果保存到数据库（如果有实体和关系）
        if result.get("entities"):
            # 转换为Entity对象
            entities_to_save = []
            for entity_data in result["entities"]:
                # 处理位置信息
                positions = []
                for pos in entity_data.get("positions", []):
                    from app.models.schemas import EntityPosition
                    position = EntityPosition(
                        start=pos.get("start", 0),
                        end=pos.get("end", 0),
                        context=pos.get("context", "")
                    )
                    positions.append(position)
                
                entity = Entity(
                    entity_id=entity_data.get("entity_id"),
                    entity_name=entity_data["entity_name"],
                    type=entity_data.get("entity_type"),
                    attributes=entity_data.get("attributes"),
                    description=entity_data.get("description"),
                    confidence=entity_data.get("confidence", 1.0),
                    position=positions if positions else None,
                    occurrence_count=entity_data.get("occurrence_count", 0)
                )
                entities_to_save.append(entity)
            
            # 保存实体
            await mysql_service.save_entities_to_table(document_id, entities_to_save)
            logger.info(f"保存了 {len(entities_to_save)} 个实体到数据库")
        
        if result.get("relations"):
            # 转换为Relation对象
            relations_to_save = []
            for relation_data in result["relations"]:
                relation = Relation(
                    id=relation_data.get("id"),
                    relation_id=relation_data.get("relation_id"),
                    relation_name=relation_data["relation_name"],
                    head_entity=relation_data.get("head_entity_name", ""),
                    tail_entity=relation_data.get("tail_entity_name", ""),
                    description=relation_data.get("description"),
                    evidence_text=relation_data.get("evidence_text"),
                    confidence=relation_data.get("confidence", 1.0),
                    head_entity_id=relation_data.get("head_entity_id"),
                    tail_entity_id=relation_data.get("tail_entity_id")
                )
                relations_to_save.append(relation)
            
            # 保存关系
            await mysql_service.save_relations_to_table(document_id, relations_to_save)
            logger.info(f"保存了 {len(relations_to_save)} 个关系到数据库")
        
        # 5. 返回结果
        logger.info(f"分块知识抽取完成: {len(result.get('entities', []))} 实体, {len(result.get('relations', []))} 关系")
        return JSONResponse(
            content=result,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分块知识抽取失败: {e}")
        raise HTTPException(status_code=500, detail=f"分块知识抽取失败: {str(e)}")

@router.post("/entities/extract_chunked")
async def extract_entities_chunked(
    document_id: str,
    terms: List[Term] = [],
    force: bool = Query(False, description="是否强制重新抽取，覆盖现有数据"),
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended),
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """
    分块实体识别接口 (异常32新增)
    
    独立的实体识别阶段，按 page_idx 分 chunk 逐个调用大模型进行实体识别，
    并正确处理跨 chunk 被截断的实体。
    
    Args:
        document_id: 文档ID
        terms: 术语列表（仅使用实体类型的术语）
        force: 是否强制重新抽取
        
    Returns:
        实体识别结果: {"entities": [...], "meta": {...}}
    """
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
            
        logger.info(f"开始分块实体识别，文档ID: {document_id}, 术语数量: {len(terms)}, 强制模式: {force}")
        
        # 1. 检查是否已有缓存（如果不是强制模式）
        if not force:
            entity_exists = await mysql_service.check_entity_table_exists(document_id)
            
            if entity_exists:
                # 从缓存返回结果
                entities = await mysql_service.get_entities_from_table(document_id)
                
                logger.info(f"从缓存返回实体结果: {len(entities)} 个实体")
                return {
                    "entities": [entity.dict() for entity in entities],
                    "meta": {
                        "document_id": document_id,
                        "total_entities": len(entities),
                        "source": "cache",
                        "processing_method": "chunked_entity_extraction"
                    }
                }
        
        # 2. 获取文档的json_data
        doc_data = await mongo_service_extended.get_document_by_document_id(document_id)
        if not doc_data:
            raise HTTPException(status_code=404, detail=f"文档 {document_id} 不存在")
            
        json_data = doc_data.get("json_data", [])
        if not json_data:
            raise HTTPException(status_code=400, detail=f"文档 {document_id} 没有json_data内容")
        
        # 3. 执行分块实体识别
        chunked_service = ChunkedIEService()
        result = await chunked_service.extract_entities_chunked(
            document_id=document_id,
            json_data=json_data,
            terms=terms if terms else None
        )
        
        # 4. 将结果保存到数据库（如果有实体）
        if result.get("entities"):
            # 转换为Entity对象
            entities_to_save = []
            for entity_data in result["entities"]:
                # 处理位置信息
                positions = []
                for pos in entity_data.get("positions", []):
                    from app.models.schemas import EntityPosition
                    position = EntityPosition(
                        start=pos.get("start", 0),
                        end=pos.get("end", 0),
                        context=pos.get("context", "")
                    )
                    positions.append(position)
                
                entity = Entity(
                    entity_id=entity_data.get("entity_id"),
                    entity_name=entity_data["entity_name"],
                    type=entity_data.get("entity_type"),
                    attributes=entity_data.get("attributes"),
                    description=entity_data.get("description"),
                    confidence=entity_data.get("confidence", 1.0),
                    position=positions if positions else None,
                    occurrence_count=entity_data.get("occurrence_count", 0)
                )
                entities_to_save.append(entity)
            
            # 保存实体
            await mysql_service.save_entities_to_table(document_id, entities_to_save)
            logger.info(f"保存了 {len(entities_to_save)} 个实体到数据库")
        
        # 5. 返回结果
        logger.info(f"分块实体识别完成: {len(result.get('entities', []))} 个实体")
        return JSONResponse(
            content=result,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分块实体识别失败: {e}")
        raise HTTPException(status_code=500, detail=f"分块实体识别失败: {str(e)}")

@router.post("/relations/extract_chunked")
async def extract_relations_chunked(
    document_id: str,
    terms: List[Term] = [],
    force: bool = Query(False, description="是否强制重新抽取，覆盖现有数据"),
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended),
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """
    分块关系抽取接口 (异常32新增)
    
    独立的关系抽取阶段，基于已确认的实体进行关系抽取。
    按 page_idx 分 chunk 逐个调用大模型进行关系抽取，
    并正确处理跨 chunk 被截断的关系。
    
    Args:
        document_id: 文档ID
        terms: 术语列表（仅使用关系类型的术语）
        force: 是否强制重新抽取
        
    Returns:
        关系抽取结果: {"relations": [...], "meta": {...}}
    """
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
            
        logger.info(f"开始分块关系抽取，文档ID: {document_id}, 术语数量: {len(terms)}, 强制模式: {force}")
        
        # 1. 检查是否已有缓存（如果不是强制模式）
        if not force:
            relation_exists = await mysql_service.check_relation_table_exists(document_id)
            
            if relation_exists:
                # 从缓存返回结果
                relations = await mysql_service.get_relations_from_table(document_id)
                
                logger.info(f"从缓存返回关系结果: {len(relations)} 个关系")
                return {
                    "relations": [relation.dict() for relation in relations],
                    "meta": {
                        "document_id": document_id,
                        "total_relations": len(relations),
                        "source": "cache",
                        "processing_method": "chunked_relation_extraction"
                    }
                }
        
        # 2. 检查实体表是否存在
        entity_exists = await mysql_service.check_entity_table_exists(document_id)
        if not entity_exists:
            raise HTTPException(
                status_code=400, 
                detail=f"文档 {document_id} 的实体表不存在，请先进行实体识别"
            )
        
        # 3. 从MySQL读取已确认的实体
        confirmed_entities = await mysql_service.get_entities_from_table(document_id)
        if not confirmed_entities:
            raise HTTPException(
                status_code=400, 
                detail=f"文档 {document_id} 没有已确认的实体，请先进行实体识别"
            )
        
        logger.info(f"从MySQL读取了 {len(confirmed_entities)} 个已确认实体")
        
        # 4. 获取文档的json_data
        doc_data = await mongo_service_extended.get_document_by_document_id(document_id)
        if not doc_data:
            raise HTTPException(status_code=404, detail=f"文档 {document_id} 不存在")
            
        json_data = doc_data.get("json_data", [])
        if not json_data:
            raise HTTPException(status_code=400, detail=f"文档 {document_id} 没有json_data内容")
        
        # 5. 执行分块关系抽取
        chunked_service = ChunkedIEService()
        result = await chunked_service.extract_relations_chunked(
            document_id=document_id,
            entities=confirmed_entities,
            json_data=json_data,
            terms=terms if terms else None
        )
        
        # 6. 将结果保存到数据库（如果有关系）
        if result.get("relations"):
            # 转换为Relation对象
            relations_to_save = []
            for relation_data in result["relations"]:
                relation = Relation(
                    id=relation_data.get("id"),
                    relation_id=relation_data.get("relation_id"),
                    relation_name=relation_data["relation_name"],
                    head_entity=relation_data.get("head_entity_name", ""),
                    tail_entity=relation_data.get("tail_entity_name", ""),
                    description=relation_data.get("description"),
                    evidence_text=relation_data.get("evidence_text"),
                    confidence=relation_data.get("confidence", 1.0),
                    head_entity_id=relation_data.get("head_entity_id"),
                    tail_entity_id=relation_data.get("tail_entity_id")
                )
                relations_to_save.append(relation)
            
            # 保存关系
            await mysql_service.save_relations_to_table(document_id, relations_to_save)
            logger.info(f"保存了 {len(relations_to_save)} 个关系到数据库")
        
        # 7. 返回结果
        logger.info(f"分块关系抽取完成: {len(result.get('relations', []))} 个关系")
        return JSONResponse(
            content=result,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分块关系抽取失败: {e}")
        raise HTTPException(status_code=500, detail=f"分块关系抽取失败: {str(e)}")

# 3.4 知识存储接口

@router.get("/knowledge/{document_id}", response_model=List[Relation])
async def get_knowledge(
    document_id: str,
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """获取文档的知识（异常14新增：支持缓存机制）
    
    逻辑：
    1. 检查对应的知识表是否存在
    2. 如果表存在，直接从表中读取并返回知识信息
    3. 如果表不存在，返回空列表
    """
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 检查知识表是否存在
        table_exists = await mysql_service.check_knowledge_table_exists(document_id)
        
        if table_exists:
            # 从表中读取已有知识
            cached_knowledges = await mysql_service.get_knowledges_from_table(document_id)
            return cached_knowledges
        else:
            # 表不存在，返回空列表
            return []
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识失败: {str(e)}")

@router.post("/save-knowledge-new", response_model=APIResponse)
async def save_knowledge_new(
    request: KnowledgeStorageRequestNew,
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """保存最终确认的知识到MySQL（异常14新增）
    
    用户在前端最终确认知识信息后，调用此接口保存到 documentID_knowledges 表
    """
    try:
        if not request.document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        if not request.relations:
            raise HTTPException(status_code=400, detail="知识列表不能为空")
        
        # 保存知识到表
        print("已更新")
        await mysql_service.save_knowledges_to_table(request.document_id, request.relations)
        
        return APIResponse(
            success=True,
            message="知识保存成功",
            data={
                "document_id": request.document_id,
                "knowledges_count": len(request.relations),
                "table_name": mysql_service._generate_knowledge_table_name(request.document_id)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识保存失败: {str(e)}")

@router.post("/save-knowledge", response_model=APIResponse)
async def save_knowledge(
    request: KnowledgeStorageRequest, 
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """保存关系到 MySQL（异常22修复：兼容旧接口但使用新的基于document_id的逻辑）
    
    根据前端确认的知识，保存到MySQL表（表名=document_id格式）
    注意：此接口为兼容性保留，建议使用 /save-knowledge-new
    """
    try:
        if not request.document_name:
            raise HTTPException(status_code=400, detail="文档名称不能为空")
            
        if not request.relations:
            raise HTTPException(status_code=400, detail="关系列表不能为空")
        
        # 异常22修复：警告使用了旧接口
        logger.warning(f"使用了旧的save-knowledge接口，document_name: {request.document_name}")
        logger.warning("建议前端迁移到save-knowledge-new接口使用document_id")
        
        # 兼容性处理：尝试从document_name提取document_id
        # 假设document_name格式为"文档{id}"，如"文档1"
        import re
        match = re.search(r'(\d+)', request.document_name)
        if match:
            document_id = match.group(1)
            logger.info(f"从文档名 {request.document_name} 提取document_id: {document_id}")
            
            # 使用新的基于document_id的保存逻辑
            await mysql_service.save_relations_to_table(document_id, request.relations)
            
            return APIResponse(
                success=True, 
                message="知识保存成功（已转换为document_id格式）", 
                data={
                    "document_name": request.document_name,
                    "document_id": document_id,
                    "table_name": mysql_service._generate_relation_table_name(document_id),
                    "relations_count": len(request.relations)
                }
            )
        else:
            # 如果无法提取document_id，继续使用旧逻辑但记录警告
            logger.error(f"无法从文档名 {request.document_name} 提取document_id，使用旧逻辑")
            await mysql_service.save_relations(request.document_name, request.relations)
            table_info = await mysql_service.get_table_info(request.document_name)
            
            return APIResponse(
                success=True, 
                message="知识保存成功（使用旧表名格式）", 
                data={
                    "document_name": request.document_name,
                    "table_info": table_info,
                    "relations_count": len(request.relations)
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识保存失败: {str(e)}")

# 3.5 知识图谱数据接口

@router.get("/knowledge-graph/{document_id}", response_model=KnowledgeGraphResponse)
async def get_knowledge_graph(
    document_id: str, 
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """从 MySQL 获取知识图谱数据并转换为前端可用的图谱格式（异常24修复：增强参数验证和日志记录）"""
    try:
        # 异常24修复：参数类型验证
        if not document_id:
            logger.error("知识图谱查询失败: document_id为空")
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 检查是否传入了文档名而不是document_id
        if not document_id.isdigit() and len(document_id) > 10:
            logger.error(f"参数错误: 期望 document_id(int)，实际接收到 document_name(str): {document_id}")
            raise HTTPException(
                status_code=400, 
                detail=f"参数错误: 期望 document_id(int)，实际接收到 document_name(str): {document_id}"
            )
        
        logger.info(f"正在查询知识图谱，document_id: {document_id}")
        
        # 异常17修复：使用新的关系表查询方法
        graph_data = await mysql_service.get_knowledge_graph_by_document_id(document_id)
        
        # 记录查询结果
        if graph_data and graph_data.nodes:
            logger.info(f"知识图谱查询成功，document_id: {document_id}，节点数: {len(graph_data.nodes)}，边数: {len(graph_data.edges)}")
        else:
            logger.warning(f"知识图谱查询结果为空，document_id: {document_id}")
        
        return graph_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"知识图谱查询异常，document_id: {document_id}，错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱失败: {str(e)}")

@router.get("/unified-knowledge-graph", response_model=KnowledgeGraphResponse)
async def get_unified_knowledge_graph(mysql_service: MySQLService = Depends(get_mysql_service)):
    """异常42修复：获取全局统一知识图谱数据"""
    try:
        logger.info("正在查询全局统一知识图谱")

        # 从全局知识表获取所有关系数据
        relations = await mysql_service.get_global_knowledges()

        if not relations:
            logger.warning("全局知识表中没有数据")
            return KnowledgeGraphResponse(
                nodes=[],
                edges=[],
                metadata={"message": "全局知识表为空", "total_relations": 0}
            )

        # 构建节点和边
        nodes_dict = {}
        edges = []

        for relation in relations:
            # 创建头实体节点
            if relation.head_entity and relation.head_entity != "未知实体":
                head_id = relation.head_entity_id or f"entity_{hash(relation.head_entity) % 10000}"
                if head_id not in nodes_dict:
                    nodes_dict[head_id] = GraphNode(
                        id=head_id,
                        name=relation.head_entity,
                        type="entity",
                        properties={"entity_type": "extracted", "source": "global"}
                    )

            # 创建尾实体节点
            if relation.tail_entity and relation.tail_entity != "未知实体":
                tail_id = relation.tail_entity_id or f"entity_{hash(relation.tail_entity) % 10000}"
                if tail_id not in nodes_dict:
                    nodes_dict[tail_id] = GraphNode(
                        id=tail_id,
                        name=relation.tail_entity,
                        type="entity",
                        properties={"entity_type": "extracted", "source": "global"}
                    )

            # 创建关系边（只有当两个实体都存在时才创建）
            if (relation.head_entity and relation.head_entity != "未知实体" and
                relation.tail_entity and relation.tail_entity != "未知实体"):

                head_id = relation.head_entity_id or f"entity_{hash(relation.head_entity) % 10000}"
                tail_id = relation.tail_entity_id or f"entity_{hash(relation.tail_entity) % 10000}"

                edge = GraphEdge(
                    id=f"edge_{relation.relation_id}",
                    source=head_id,
                    target=tail_id,
                    type=relation.relation_name,
                    relation_type=relation.relation_name,
                    properties={
                        "confidence": relation.confidence,
                        "description": relation.description or "",
                        "evidence_text": relation.evidence_text or ""
                    }
                )
                edges.append(edge)

        # 转换为列表
        nodes = list(nodes_dict.values())

        logger.info(f"全局知识图谱构建完成，节点数: {len(nodes)}，边数: {len(edges)}")

        return KnowledgeGraphResponse(
            nodes=nodes,
            edges=edges,
            metadata={
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "total_relations": len(relations),
                "source": "global_knowledges_table"
            }
        )

    except Exception as e:
        logger.error(f"全局知识图谱查询异常，错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取全局知识图谱失败: {str(e)}")

# 3.6 知识表管理接口

@router.get("/knowledge-tables", response_model=List[str])
async def list_knowledge_tables(mysql_service: MySQLService = Depends(get_mysql_service)):
    """列出所有知识表（旧接口，建议使用 /knowledge-graph-options）"""
    try:
        tables = await mysql_service.list_knowledge_tables()
        return tables
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识表列表失败: {str(e)}")

@router.get("/knowledge-graph-options", response_model=List[KnowledgeGraphOption])
async def get_knowledge_graph_options(mysql_service: MySQLService = Depends(get_mysql_service)):
    """异常51修复：获取知识图谱选项列表，包含显示名称和document_id"""
    try:
        options = await mysql_service.get_knowledge_graph_options()
        return options
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识图谱选项失败: {str(e)}")

@router.delete("/knowledge-tables/{document_id}", response_model=APIResponse)
async def delete_knowledge_table(
    document_id: str, 
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """删除指定文档的知识表（异常22修复：使用document_id）"""
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 删除所有相关表
        deleted_tables = []
        
        # 删除实体表
        if await mysql_service.check_entity_table_exists(document_id):
            table_name = mysql_service._generate_entity_table_name(document_id)
            async with mysql_service.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"DROP TABLE `{table_name}`")
                    await conn.commit()
            deleted_tables.append(table_name)
        
        # 删除关系表
        if await mysql_service.check_relation_table_exists(document_id):
            table_name = mysql_service._generate_relation_table_name(document_id)
            async with mysql_service.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"DROP TABLE `{table_name}`")
                    await conn.commit()
            deleted_tables.append(table_name)
        
        # 删除知识表
        if await mysql_service.check_knowledge_table_exists(document_id):
            table_name = mysql_service._generate_knowledge_table_name(document_id)
            async with mysql_service.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"DROP TABLE `{table_name}`")
                    await conn.commit()
            deleted_tables.append(table_name)
        
        logger.info(f"删除文档{document_id}的表: {deleted_tables}")
        return APIResponse(
            success=True, 
            message=f"文档{document_id}相关表删除成功", 
            data={"deleted_tables": deleted_tables}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除知识表失败: {str(e)}")

@router.get("/knowledge-tables/{document_id}/info")
async def get_knowledge_table_info(
    document_id: str, 
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """获取知识表的详细信息（异常22修复：使用document_id）"""
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 获取所有相关表的信息
        table_info = {
            "document_id": document_id,
            "tables": {}
        }
        
        # 检查实体表
        if await mysql_service.check_entity_table_exists(document_id):
            entities = await mysql_service.get_entities_from_table(document_id)
            table_info["tables"]["entities"] = {
                "table_name": mysql_service._generate_entity_table_name(document_id),
                "exists": True,
                "count": len(entities)
            }
        else:
            table_info["tables"]["entities"] = {
                "table_name": mysql_service._generate_entity_table_name(document_id),
                "exists": False,
                "count": 0
            }
        
        # 检查关系表
        if await mysql_service.check_relation_table_exists(document_id):
            relations = await mysql_service.get_relations_from_table(document_id)
            table_info["tables"]["relations"] = {
                "table_name": mysql_service._generate_relation_table_name(document_id),
                "exists": True,
                "count": len(relations)
            }
        else:
            table_info["tables"]["relations"] = {
                "table_name": mysql_service._generate_relation_table_name(document_id),
                "exists": False,
                "count": 0
            }
        
        # 检查知识表
        if await mysql_service.check_knowledge_table_exists(document_id):
            knowledges = await mysql_service.get_knowledges_from_table(document_id)
            table_info["tables"]["knowledges"] = {
                "table_name": mysql_service._generate_knowledge_table_name(document_id),
                "exists": True,
                "count": len(knowledges)
            }
        else:
            table_info["tables"]["knowledges"] = {
                "table_name": mysql_service._generate_knowledge_table_name(document_id),
                "exists": False,
                "count": 0
            }
            
        return table_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识表信息失败: {str(e)}")