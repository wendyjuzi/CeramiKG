from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.dependencies import get_assistant_service
from app.models.assistant import AssistantChatRequest, AssistantChatResponse
from app.services.assistant_service import AssistantService


router = APIRouter()


@router.post("/chat", response_model=AssistantChatResponse)
async def chat(
    request: AssistantChatRequest,
    service: AssistantService = Depends(get_assistant_service),
):
    """Answer a question using bounded literature and graph evidence."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    request.question = question
    try:
        return await service.chat(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"智能问答失败: {exc}") from exc
