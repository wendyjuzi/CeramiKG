from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List, Optional
import logging
from app.dependencies.dependencies import get_mongo_service_extended, get_mysql_service, get_prompt_service, get_neo4j_service
from app.utils.json_validator import JSONValidator

from app.services.mongo_service_extended import MongoServiceExtended
from app.services.mysql_service import MySQLService
from app.services.neo4j_service import Neo4jService
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
    """根据document_id获取文档详情，包含json_data字段内容"""
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

# 3.3 知识抽取接口（使用Neo4j）

@router.get("/documents/{document_id}/entities")
async def get_document_entities(
    document_id: str,
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """获取文档的实体数据（使用Neo4j）
    
    逻辑：
    1. 检查文档的实体是否存在
    2. 如果存在，直接返回实体数据
    3. 如果不存在，返回 exists: false
    """
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 检查实体是否存在
        entity_exists = await neo4j_service.check_entity_table_exists(document_id)
        
        if entity_exists:
            # 从Neo4j中读取实体数据
            entities = await neo4j_service.get_entities_from_table(document_id)
            logger.info(f"文档 {document_id} 存在实体数据，返回 {len(entities)} 条数据")
            return {
                "exists": True,
                "entities": entities,
                "count": len(entities),
                "table_name": f"{document_id}_entitys"
            }
        else:
            logger.info(f"文档 {document_id} 不存在实体数据")
            return {
                "exists": False,
                "entities": [],
                "count": 0,
                "table_name": f"{document_id}_entitys"
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
    neo4j_service: Neo4jService = Depends(get_neo4j_service),
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended)
):
    """实体识别（使用Neo4j缓存）
    
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
        
        # 统一缓存检查逻辑，避免重复查询
        cached_entities = None
        if request.document_id:
            entity_exists = await neo4j_service.check_entity_table_exists(request.document_id)
            if entity_exists:
                cached_entities = await neo4j_service.get_entities_from_table(request.document_id)
                if cached_entities:
                    logger.info(f"从Neo4j缓存返回 {len(cached_entities)} 个实体")
                    return cached_entities
        
        # 尝试使用分块抽取逻辑
        if request.document_id:
            logger.info(f"开始分块实体识别，文档ID: {request.document_id}")
            
            try:
                # 直接获取json_data，减少数据库查询
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
                        
                        # 保存到Neo4j
                        await neo4j_service.save_entities_to_table(request.document_id, entities_to_save)
                        logger.info(f"分块实体识别完成，保存了 {len(entities_to_save)} 个实体到Neo4j")
                        
                        return entities_to_return
                    else:
                        return []
                        
            except Exception as e:
                logger.warning(f"分块抽取失败，回退到原有逻辑: {e}")
        
        # 回退到原有逻辑
        logger.info("使用原有实体识别逻辑")
        
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
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """保存用户确认的实体到Neo4j
    
    用户在前端确认实体信息后，调用此接口保存到Neo4j图数据库
    """
    try:
        if not request.document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        if not request.entities:
            raise HTTPException(status_code=400, detail="实体列表不能为空")
        
        # 保存实体到Neo4j
        await neo4j_service.save_entities_to_table(request.document_id, request.entities)
        
        return APIResponse(
            success=True,
            message="实体保存成功",
            data={
                "document_id": request.document_id,
                "entities_count": len(request.entities),
                "storage_type": "neo4j"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"实体保存失败: {str(e)}")

@router.get("/documents/{document_id}/relations")
async def get_document_relations(
    document_id: str,
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """获取文档的关系数据（使用Neo4j）
    
    逻辑：
    1. 检查文档的关系是否存在
    2. 如果存在，直接返回关系数据
    3. 如果不存在，返回 exists: false
    """
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 检查关系是否存在
        relation_exists = await neo4j_service.check_relation_table_exists(document_id)
        
        if relation_exists:
            # 从Neo4j中读取关系数据
            relations = await neo4j_service.get_relations_from_table(document_id)
            logger.info(f"文档 {document_id} 存在关系数据，返回 {len(relations)} 条数据")
            return {
                "exists": True,
                "relations": relations,
                "count": len(relations),
                "table_name": f"{document_id}_relations"
            }
        else:
            logger.info(f"文档 {document_id} 不存在关系数据")
            return {
                "exists": False,
                "relations": [],
                "count": 0,
                "table_name": f"{document_id}_relations"
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
    neo4j_service: Neo4jService = Depends(get_neo4j_service),
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended)
):
    """关系抽取（使用Neo4j缓存）
    
    优化逻辑：
    1. 统一缓存检查，避免重复查询
    2. 优先使用分块关系抽取逻辑
    3. 改进错误处理和回退机制
    4. 支持缓存机制和强制重新抽取
    """
    try:
        if not request.entities:
            raise HTTPException(status_code=400, detail="实体列表不能为空")
        
        # 统一缓存检查逻辑，避免重复查询
        cached_relations = None
        if request.document_id:
            relation_exists = await neo4j_service.check_relation_table_exists(request.document_id)
            if relation_exists:
                cached_relations = await neo4j_service.get_relations_from_table(request.document_id)
                if cached_relations:
                    logger.info(f"从Neo4j缓存返回 {len(cached_relations)} 个关系")
                    return cached_relations
        
        # 尝试使用分块抽取逻辑
        if request.document_id:
            logger.info(f"开始分块关系抽取，文档ID: {request.document_id}")
            
            try:
                # 直接获取json_data，减少查询开销
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
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """保存用户确认的关系到Neo4j
    
    用户在前端确认关系信息后，调用此接口保存到Neo4j图数据库
    """
    try:
        if not request.document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        if not request.relations:
            raise HTTPException(status_code=400, detail="关系列表不能为空")
        
        # 保存关系到Neo4j
        await neo4j_service.save_relations_to_table(request.document_id, request.relations)
        
        return APIResponse(
            success=True,
            message="关系保存成功",
            data={
                "document_id": request.document_id,
                "relations_count": len(request.relations),
                "storage_type": "neo4j"
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
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """
    分块知识抽取接口（使用Neo4j）
    
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
            entity_exists = await neo4j_service.check_entity_table_exists(document_id)
            relation_exists = await neo4j_service.check_relation_table_exists(document_id)
            
            if entity_exists and relation_exists:
                # 从缓存返回结果
                entities = await neo4j_service.get_entities_from_table(document_id)
                relations = await neo4j_service.get_relations_from_table(document_id)
                
                logger.info(f"从Neo4j缓存返回结果: {len(entities)} 实体, {len(relations)} 关系")
                return {
                    "entities": [entity.dict() for entity in entities],
                    "relations": [relation.dict() for relation in relations],
                    "meta": {
                        "document_id": document_id,
                        "total_entities": len(entities),
                        "total_relations": len(relations),
                        "source": "neo4j_cache",
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
        
        # 4. 将结果保存到Neo4j（如果有实体和关系）
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
            
            # 保存实体到Neo4j
            await neo4j_service.save_entities_to_table(document_id, entities_to_save)
            logger.info(f"保存了 {len(entities_to_save)} 个实体到Neo4j")
        
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
            
            # 保存关系到Neo4j
            await neo4j_service.save_relations_to_table(document_id, relations_to_save)
            logger.info(f"保存了 {len(relations_to_save)} 个关系到Neo4j")
        
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

# 3.4 知识存储接口（使用Neo4j）

@router.get("/knowledge/{document_id}", response_model=List[Relation])
async def get_knowledge(
    document_id: str,
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """获取文档的知识（使用Neo4j）
    
    逻辑：
    1. 检查对应的知识是否存在
    2. 如果存在，直接从Neo4j中读取并返回知识信息
    3. 如果不存在，返回空列表
    """
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 检查知识是否存在
        knowledge_exists = await neo4j_service.check_knowledge_table_exists(document_id)
        
        if knowledge_exists:
            # 从Neo4j中读取已有知识
            cached_knowledges = await neo4j_service.get_knowledges_from_table(document_id)
            return cached_knowledges
        else:
            # 不存在，返回空列表
            return []
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识失败: {str(e)}")

@router.post("/save-knowledge-new", response_model=APIResponse)
async def save_knowledge_new(
    request: KnowledgeStorageRequestNew,
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """保存最终确认的知识到Neo4j
    
    用户在前端最终确认知识信息后，调用此接口保存到Neo4j图数据库
    """
    try:
        if not request.document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        if not request.relations:
            raise HTTPException(status_code=400, detail="知识列表不能为空")
        
        # 保存知识到Neo4j（双重保存：文档级+全局级）
        await neo4j_service.save_knowledges_to_table(request.document_id, request.relations)
        
        return APIResponse(
            success=True,
            message="知识保存成功",
            data={
                "document_id": request.document_id,
                "knowledges_count": len(request.relations),
                "storage_type": "neo4j"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识保存失败: {str(e)}")

# 3.5 知识图谱数据接口（使用Neo4j）

@router.get("/knowledge-graph/{document_id}", response_model=KnowledgeGraphResponse)
async def get_knowledge_graph(
    document_id: str, 
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """从Neo4j获取知识图谱数据并转换为前端可用的图谱格式"""
    try:
        # 参数类型验证
        if not document_id:
            logger.error("知识图谱查询失败: document_id为空")
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        logger.info(f"正在从Neo4j查询知识图谱，document_id: {document_id}")
        
        # 使用Neo4j查询知识图谱
        graph_data = await neo4j_service.get_knowledge_graph_by_document_id(document_id)
        
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
async def get_unified_knowledge_graph(neo4j_service: Neo4jService = Depends(get_neo4j_service)):
    """获取全局统一知识图谱数据（使用Neo4j全局知识）"""
    try:
        logger.info("正在从Neo4j查询全局统一知识图谱")

        # 从Neo4j全局知识表获取所有关系数据
        relations = await neo4j_service.get_global_knowledges()

        if not relations:
            logger.warning("Neo4j全局知识图中没有数据")
            return KnowledgeGraphResponse(
                nodes=[],
                edges=[],
                metadata={"message": "Neo4j全局知识图为空", "total_relations": 0}
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
                        properties={"entity_type": "extracted", "source": "neo4j_global"}
                    )

            # 创建尾实体节点
            if relation.tail_entity and relation.tail_entity != "未知实体":
                tail_id = relation.tail_entity_id or f"entity_{hash(relation.tail_entity) % 10000}"
                if tail_id not in nodes_dict:
                    nodes_dict[tail_id] = GraphNode(
                        id=tail_id,
                        name=relation.tail_entity,
                        type="entity",
                        properties={"entity_type": "extracted", "source": "neo4j_global"}
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

        logger.info(f"Neo4j全局知识图谱构建完成，节点数: {len(nodes)}，边数: {len(edges)}")

        return KnowledgeGraphResponse(
            nodes=nodes,
            edges=edges,
            metadata={
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "total_relations": len(relations),
                "source": "neo4j_global_knowledge"
            }
        )

    except Exception as e:
        logger.error(f"Neo4j全局知识图谱查询异常，错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取全局知识图谱失败: {str(e)}")

# 3.6 知识表管理接口（使用Neo4j）

@router.get("/knowledge-tables", response_model=List[str])
async def list_knowledge_tables(neo4j_service: Neo4jService = Depends(get_neo4j_service)):
    """列出所有知识表（使用Neo4j）"""
    try:
        document_ids = await neo4j_service.list_knowledge_tables()
        return document_ids
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识表列表失败: {str(e)}")

@router.get("/knowledge-graph-options", response_model=List[KnowledgeGraphOption])
async def get_knowledge_graph_options(
    neo4j_service: Neo4jService = Depends(get_neo4j_service),
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    """获取知识图谱选项列表，包含显示名称和document_id"""
    try:
        # 从 Neo4j 获取基础选项
        options = await neo4j_service.get_knowledge_graph_options()
        
        # 从 MySQL 获取文档名称映射
        name_map = await mysql_service.get_document_name_map()
        
        # 替换显示名称
        for option in options:
            if option.document_id in name_map:
                original_name = name_map[option.document_id]
                option.display_name = original_name
                option.description = f"基于文档 '{original_name}' 构建的知识图谱"
        
        return options
    except Exception as e:
        logger.error(f"获取知识图谱选项失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱选项失败: {str(e)}")        

@router.delete("/knowledge-tables/{document_id}", response_model=APIResponse)
async def delete_knowledge_table(
    document_id: str, 
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """删除指定文档的知识表（使用Neo4j）"""
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 删除Neo4j中文档相关的所有知识
        await neo4j_service.delete_knowledge_table(document_id)
        
        logger.info(f"删除文档{document_id}的知识数据")
        return APIResponse(
            success=True, 
            message=f"文档{document_id}相关知识数据删除成功", 
            data={"deleted_document_id": document_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除知识表失败: {str(e)}")

@router.get("/knowledge-tables/{document_id}/info")
async def get_knowledge_table_info(
    document_id: str, 
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """获取知识表的详细信息（使用Neo4j）"""
    try:
        if not document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        # 获取所有相关表的信息
        table_info = {
            "document_id": document_id,
            "tables": {}
        }
        
        # 检查实体
        entity_exists = await neo4j_service.check_entity_table_exists(document_id)
        if entity_exists:
            entities = await neo4j_service.get_entities_from_table(document_id)
            table_info["tables"]["entities"] = {
                "exists": True,
                "count": len(entities),
                "storage_type": "neo4j"
            }
        else:
            table_info["tables"]["entities"] = {
                "exists": False,
                "count": 0,
                "storage_type": "neo4j"
            }
        
        # 检查关系
        relation_exists = await neo4j_service.check_relation_table_exists(document_id)
        if relation_exists:
            relations = await neo4j_service.get_relations_from_table(document_id)
            table_info["tables"]["relations"] = {
                "exists": True,
                "count": len(relations),
                "storage_type": "neo4j"
            }
        else:
            table_info["tables"]["relations"] = {
                "exists": False,
                "count": 0,
                "storage_type": "neo4j"
            }
        
        # 检查知识（与关系相同）
        knowledge_exists = await neo4j_service.check_knowledge_table_exists(document_id)
        if knowledge_exists:
            knowledges = await neo4j_service.get_knowledges_from_table(document_id)
            table_info["tables"]["knowledges"] = {
                "exists": True,
                "count": len(knowledges),
                "storage_type": "neo4j"
            }
        else:
            table_info["tables"]["knowledges"] = {
                "exists": False,
                "count": 0,
                "storage_type": "neo4j"
            }
            
        return table_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识表信息失败: {str(e)}")