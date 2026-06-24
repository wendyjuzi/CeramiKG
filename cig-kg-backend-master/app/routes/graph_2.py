from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List, Optional
import logging
import os
from app.dependencies.dependencies import get_mongo_service_extended, get_mysql_service, get_prompt_service, get_neo4j_service
from app.utils.json_validator import JSONValidator

from app.services.mongo_service_extended import MongoServiceExtended
from app.services.mysql_service import MySQLService
from app.services.neo4j_service import Neo4jService
from app.services.prompt_service import PromptService
from app.services.chunked_ie import ChunkedIEService
from app.services.extracted_kg_import_service import load_extracted_papers, scan_extracted_results
from app.models.schemas import (
    Document, DocumentSummary, DocumentDetail, Term, Entity, Relation,
    EntityExtractionRequest, RelationExtractionRequest,
    EntityStorageRequest, RelationStorageRequest,
    KnowledgeStorageRequest, KnowledgeStorageRequestNew, KnowledgeGraphResponse, KnowledgeGraphOption, APIResponse, TermFilterRequest,
    TermCreateRequest, TermUpdateRequest, GraphNode, GraphEdge, ExtractedKGImportRequest
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

# 3.3 在线知识抽取接口（保存接口由前端会话承接，避免污染底层图谱）

ONLINE_SESSION_STORAGE_TYPE = "frontend_session"


def _relation_entity_keys(entity: Entity) -> set:
    return {
        str(value).strip().lower()
        for value in (
            entity.entity_id,
            entity.entity_name,
            getattr(entity, "name", None),
        )
        if value is not None and str(value).strip()
    }


def _filter_relations_for_entities(relations: List[Relation], entities: List[Entity]) -> List[Relation]:
    selected_keys = set()
    for entity in entities:
        selected_keys.update(_relation_entity_keys(entity))

    if not selected_keys:
        return []

    filtered = []
    for relation in relations:
        head_keys = {
            str(value).strip().lower()
            for value in (
                relation.head_entity_id,
                relation.head_entity,
                relation.head_entity_name,
            )
            if value is not None and str(value).strip()
        }
        tail_keys = {
            str(value).strip().lower()
            for value in (
                relation.tail_entity_id,
                relation.tail_entity,
                relation.tail_entity_name,
            )
            if value is not None and str(value).strip()
        }
        if head_keys & selected_keys and tail_keys & selected_keys:
            filtered.append(relation)

    return filtered

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
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended),
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """实体识别（可只读缓存加速，保存不写入Neo4j）
    
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

        if request.document_id:
            try:
                entity_exists = await neo4j_service.check_entity_table_exists(request.document_id)
                if entity_exists:
                    cached_entities = await neo4j_service.get_entities_from_table(request.document_id)
                    if cached_entities:
                        logger.info(f"从Neo4j只读缓存返回 {len(cached_entities)} 个实体")
                        return cached_entities
            except Exception as cache_error:
                logger.info(f"读取实体缓存失败，继续在线抽取: {cache_error}")
        
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
                    
                    # 转换结果并直接返回给前端。
                    if result.get("entities"):
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
                            entities_to_return.append(entity)

                        logger.info(f"分块实体识别完成，返回 {len(entities_to_return)} 个实体")
                        
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
    request: EntityStorageRequest
):
    """确认用户选择的实体（会话级保存，不写入底层图谱）
    
    用户在前端确认实体信息后，调用此接口返回保存成功结果。
    """
    try:
        if not request.document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        if not request.entities:
            raise HTTPException(status_code=400, detail="实体列表不能为空")
        
        return APIResponse(
            success=True,
            message="实体保存成功",
            data={
                "document_id": request.document_id,
                "entities_count": len(request.entities),
                "storage_type": ONLINE_SESSION_STORAGE_TYPE,
                "session_only": True
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
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended),
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """关系抽取（可只读缓存加速，保存不写入Neo4j）
    
    优化逻辑：
    1. 统一缓存检查，避免重复查询
    2. 优先使用分块关系抽取逻辑
    3. 改进错误处理和回退机制
    4. 支持缓存机制和强制重新抽取
    """
    try:
        if not request.entities:
            raise HTTPException(status_code=400, detail="实体列表不能为空")

        if request.document_id:
            try:
                relation_exists = await neo4j_service.check_relation_table_exists(request.document_id)
                if relation_exists:
                    cached_relations = await neo4j_service.get_relations_from_table(request.document_id)
                    filtered_relations = _filter_relations_for_entities(cached_relations, request.entities)
                    if filtered_relations:
                        logger.info(
                            "从Neo4j只读缓存返回 %s/%s 个局部关系",
                            len(filtered_relations),
                            len(cached_relations),
                        )
                        return filtered_relations
            except Exception as cache_error:
                logger.info(f"读取关系缓存失败，继续在线抽取: {cache_error}")
        
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
    request: RelationStorageRequest
):
    """确认用户选择的关系（会话级保存，不写入底层图谱）
    
    用户在前端确认关系信息后，调用此接口返回保存成功结果。
    """
    try:
        if not request.document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        if not request.relations:
            raise HTTPException(status_code=400, detail="关系列表不能为空")
        
        return APIResponse(
            success=True,
            message="关系保存成功",
            data={
                "document_id": request.document_id,
                "relations_count": len(request.relations),
                "storage_type": ONLINE_SESSION_STORAGE_TYPE,
                "session_only": True
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
    mongo_service_extended: MongoServiceExtended = Depends(get_mongo_service_extended)
):
    """
    分块知识抽取接口（会话级构建）
    
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
        
        # 1. 获取文档的json_data
        doc_data = await mongo_service_extended.get_document_by_document_id(document_id)
        if not doc_data:
            raise HTTPException(status_code=404, detail=f"文档 {document_id} 不存在")
            
        json_data = doc_data.get("json_data", [])
        if not json_data:
            raise HTTPException(status_code=400, detail=f"文档 {document_id} 没有json_data内容")
        
        # 2. 执行分块知识抽取
        chunked_service = ChunkedIEService()
        result = await chunked_service.extract_chunked_knowledge(
            document_id=document_id,
            json_data=json_data,
            terms=terms if terms else None
        )

        result.setdefault("meta", {})
        result["meta"].update({
            "document_id": document_id,
            "source": ONLINE_SESSION_STORAGE_TYPE,
            "session_only": True,
            "processing_method": "chunked_extraction"
        })

        # 3. 返回结果
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

# 3.4 在线知识确认接口（会话级保存，避免污染底层图谱）

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
    request: KnowledgeStorageRequestNew
):
    """确认最终知识（会话级保存，不写入底层图谱）
    
    用户在前端最终确认知识信息后，调用此接口返回保存成功结果。
    """
    try:
        if not request.document_id:
            raise HTTPException(status_code=400, detail="文档ID不能为空")
        
        if not request.relations:
            raise HTTPException(status_code=400, detail="知识列表不能为空")
        
        return APIResponse(
            success=True,
            message="知识保存成功",
            data={
                "document_id": request.document_id,
                "knowledges_count": len(request.relations),
                "relations_count": len(request.relations),
                "storage_type": ONLINE_SESSION_STORAGE_TYPE,
                "session_only": True
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识保存失败: {str(e)}")

# 3.5 离线抽取结果图谱接口（relation目录导入Neo4j）

@router.get("/extracted-results/scan")
async def scan_extracted_kg_results(
    root_path: Optional[str] = Query(None, description="relation/extracted.json root path"),
    limit: Optional[int] = Query(None, ge=1, description="Maximum number of extracted.json files to scan")
):
    """Scan local relation/**/extracted.json files without connecting to Neo4j."""
    try:
        return scan_extracted_results(root_path=root_path, limit=limit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"扫描抽取结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"扫描抽取结果失败: {str(e)}")

@router.post("/extracted-results/import", response_model=APIResponse)
async def import_extracted_kg_results(
    request: ExtractedKGImportRequest,
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """Import relation/**/extracted.json results into Neo4j as the ceramic KG."""
    try:
        resolved_root, papers, parse_errors = load_extracted_papers(
            root_path=request.root_path,
            limit=request.limit
        )
        import_result = await neo4j_service.import_extracted_papers(
            papers,
            clear_existing=request.clear_existing
        )
        import_result.update({
            "root_path": str(resolved_root),
            "parsed_file_count": len(papers),
            "parse_errors": parse_errors,
        })
        return APIResponse(
            success=len(import_result.get("errors", [])) == 0,
            message="抽取结果导入Neo4j完成",
            data=import_result
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"导入抽取结果到Neo4j失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入抽取结果到Neo4j失败: {str(e)}")

@router.delete("/extracted-results/graph", response_model=APIResponse)
async def clear_extracted_kg_graph(
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """Clear only the Neo4j graph built from relation/**/extracted.json."""
    try:
        result = await neo4j_service.clear_extracted_kg()
        return APIResponse(
            success=True,
            message="抽取结果图谱已清空",
            data=result
        )
    except Exception as e:
        logger.error(f"清空抽取结果图谱失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空抽取结果图谱失败: {str(e)}")

@router.get("/extracted-results/graph", response_model=KnowledgeGraphResponse)
async def get_extracted_unified_graph(
    limit: int = Query(2000, ge=1, le=10000),
    include_all: bool = Query(False, description="Return all imported extracted relations without LIMIT"),
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """Get a unified graph view for imported ceramic extraction results."""
    try:
        graph_limit = None if include_all else limit
        return await neo4j_service.get_extracted_unified_knowledge_graph(limit=graph_limit)
    except Exception as e:
        logger.error(f"获取抽取结果全局图谱失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取抽取结果全局图谱失败: {str(e)}")

@router.get("/extracted-results/papers", response_model=List[KnowledgeGraphOption])
async def list_extracted_papers(
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """List only papers imported from relation/**/extracted.json."""
    try:
        async with neo4j_service._session() as session:
            result = await session.run("""
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

            options = []
            async for record in result:
                document_id = record["document_id"]
                if not document_id:
                    continue

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
                    display_name=record["title"] or document_id,
                    description=f"Imported ceramic KG from relation/extracted.json{description_suffix}",
                    table_count=entity_count + relation_count,
                    is_legacy=False
                ))

            return options
    except Exception as e:
        logger.error(f"获取离线抽取论文列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取离线抽取论文列表失败: {str(e)}")

@router.get("/extracted-results/graph/{paper_id}", response_model=KnowledgeGraphResponse)
async def get_extracted_graph_by_paper(
    paper_id: str,
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """Get imported ceramic KG data for one paper."""
    try:
        return await neo4j_service.get_extracted_knowledge_graph_by_paper_id(paper_id)
    except Exception as e:
        logger.error(f"获取论文抽取图谱失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取论文抽取图谱失败: {str(e)}")

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
async def get_unified_knowledge_graph(
    limit: int = Query(2000, ge=1, le=10000),
    include_all: bool = Query(False, description="Return all imported extracted relations without LIMIT"),
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """获取全局统一知识图谱数据（旧全局知识 + relation抽取图谱）"""
    try:
        logger.info("正在从Neo4j查询全局统一知识图谱")

        graph_limit = None if include_all else limit
        extracted_graph = await neo4j_service.get_extracted_unified_knowledge_graph(limit=graph_limit)
        relations = await neo4j_service.get_global_knowledges()

        if not relations:
            logger.warning("Neo4j全局知识图中没有数据")
            if extracted_graph.nodes or extracted_graph.edges:
                return extracted_graph
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

        for node in extracted_graph.nodes:
            if node.id not in nodes_dict:
                nodes_dict[node.id] = node

        existing_edge_ids = {edge.id for edge in edges}
        for edge in extracted_graph.edges:
            if edge.id not in existing_edge_ids:
                edges.append(edge)
                existing_edge_ids.add(edge.id)

        # 转换为列表
        nodes = list(nodes_dict.values())

        legacy_relation_count = len(relations)
        extracted_relation_count = extracted_graph.metadata.get("total_relations") if extracted_graph.metadata else 0

        logger.info(f"Neo4j全局知识图谱构建完成，节点数: {len(nodes)}，边数: {len(edges)}")

        return KnowledgeGraphResponse(
            nodes=nodes,
            edges=edges,
            metadata={
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "total_relations": legacy_relation_count + extracted_relation_count,
                "legacy_relations": legacy_relation_count,
                "extracted_relations": extracted_relation_count,
                "limit": graph_limit,
                "include_all": bool(extracted_graph.metadata.get("include_all")) if extracted_graph.metadata else include_all,
                "truncated": bool(extracted_graph.metadata.get("truncated")) if extracted_graph.metadata else False,
                "source": "neo4j_global_knowledge+relation_extracted"
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
    neo4j_service: Neo4jService = Depends(get_neo4j_service)
):
    """获取知识图谱选项列表，包含显示名称和document_id"""
    try:
        options = await neo4j_service.get_knowledge_graph_options()

        if os.getenv("KG_ONLY_MODE", "false").lower() not in ("1", "true", "yes"):
            try:
                mysql_service = await get_mysql_service()
                name_map = await mysql_service.get_document_name_map()

                for option in options:
                    if option.document_id in name_map:
                        original_name = name_map[option.document_id]
                        option.display_name = original_name
                        option.description = f"基于文档 '{original_name}' 构建的知识图谱"
            except Exception as mysql_error:
                logger.warning(f"MySQL document name mapping unavailable, using Neo4j options only: {mysql_error}")
        
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
