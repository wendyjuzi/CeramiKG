from fastapi import APIRouter, Depends, HTTPException
from app.services.neo4j_service import Neo4jService
from app.services.prompt_service_with_ontology import PromptService
from app.dependencies.dependencies import get_neo4j_service

router = APIRouter()

@router.get("/prompt/{ontology_id}")
async def get_prompt(ontology_id: str, neo4j_service: Neo4jService = Depends(get_neo4j_service)):
    """根据本体ID生成初始提示词"""
    prompt_service = PromptService(neo4j_service=neo4j_service)
    extraction_prompt = await prompt_service.build_prompt(ontology_id)

    if "error" in extraction_prompt:
        raise HTTPException(status_code=404, detail=extraction_prompt["error"])

    return {"prompt": extraction_prompt}