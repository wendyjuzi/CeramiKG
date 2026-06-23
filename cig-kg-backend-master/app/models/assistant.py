from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AssistantHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class AssistantChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: List[AssistantHistoryMessage] = Field(default_factory=list, max_length=12)
    mode: Literal["hybrid", "literature", "graph"] = "hybrid"
    document_names: List[str] = Field(default_factory=list, max_length=20)
    document_ids: List[str] = Field(default_factory=list, max_length=20)
    top_k: int = Field(default=5, ge=1, le=10)
    graph_limit: int = Field(default=8, ge=1, le=20)


class AssistantSource(BaseModel):
    citation: str
    title: str
    excerpt: str
    score: Optional[float] = None
    page_num: Optional[int] = None


class AssistantGraphEvidence(BaseModel):
    citation: str
    head: str
    relation: str
    tail: Optional[str] = None
    document_id: Optional[str] = None
    paper_title: Optional[str] = None
    evidence_text: Optional[str] = None


class AssistantChatResponse(BaseModel):
    answer: str
    sources: List[AssistantSource] = Field(default_factory=list)
    graph_evidence: List[AssistantGraphEvidence] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
