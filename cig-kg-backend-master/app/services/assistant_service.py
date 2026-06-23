import asyncio
import logging
from typing import Dict, List, Optional, Tuple

import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.models.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantGraphEvidence,
    AssistantSource,
)
from app.services.neo4j_service import Neo4jService


logger = logging.getLogger(__name__)


class AssistantService:
    """Combine literature retrieval, graph evidence, and LLM generation."""

    def __init__(self, neo4j_service: Neo4jService):
        self.neo4j_service = neo4j_service

    async def chat(self, request: AssistantChatRequest) -> AssistantChatResponse:
        tasks = []
        task_names = []

        if request.mode in {"hybrid", "literature"}:
            tasks.append(self._retrieve_literature(request))
            task_names.append("literature")
        if request.mode in {"hybrid", "graph"}:
            tasks.append(self._retrieve_graph(request))
            task_names.append("graph")

        results = await asyncio.gather(*tasks, return_exceptions=True)
        literature_chunks: List[Dict] = []
        graph_rows: List[Dict] = []
        warnings: List[str] = []

        for task_name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.warning("Assistant %s retrieval failed: %s", task_name, result)
                label = "文献检索" if task_name == "literature" else "知识图谱检索"
                warnings.append(f"{label}暂时不可用")
            elif task_name == "literature":
                literature_chunks = result
            else:
                graph_rows = result

        sources = self._build_sources(literature_chunks)
        graph_evidence = self._build_graph_evidence(graph_rows)
        generated_by = "retrieval"

        try:
            answer = await self._generate_answer(request, sources, graph_evidence)
            if self._llm_config() is not None:
                generated_by = "llm"
        except Exception as exc:
            logger.warning("Assistant generation failed: %s", exc)
            warnings.append("大模型生成暂时不可用，已返回检索结果")
            answer = self._fallback_answer(sources, graph_evidence)

        return AssistantChatResponse(
            answer=answer,
            sources=sources,
            graph_evidence=graph_evidence,
            suggested_questions=self._suggest_questions(sources, graph_evidence),
            warnings=warnings,
            metadata={
                "mode": request.mode,
                "literature_count": len(sources),
                "graph_count": len(graph_evidence),
                "generated_by": generated_by,
                "model": settings.MODEL_NAME if generated_by == "llm" else None,
            },
        )

    async def _retrieve_literature(self, request: AssistantChatRequest) -> List[Dict]:
        payload = {
            "question": request.question,
            "top_k": request.top_k,
            "document_names": request.document_names,
        }
        timeout = httpx.Timeout(settings.RAG_REQUEST_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{settings.RAG_SERVICE_URL.rstrip('/')}/rag/search",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("chunks", [])

    async def _retrieve_graph(self, request: AssistantChatRequest) -> List[Dict]:
        if self.neo4j_service.driver is None:
            await self.neo4j_service.initialize()
        return await self.neo4j_service.search_assistant_context(
            question=request.question,
            limit=request.graph_limit,
            document_ids=request.document_ids,
        )

    def _build_sources(self, chunks: List[Dict]) -> List[AssistantSource]:
        sources = []
        for index, chunk in enumerate(chunks, start=1):
            content = str(chunk.get("content") or "").strip()
            if not content:
                continue
            score = chunk.get("score")
            sources.append(
                AssistantSource(
                    citation=f"[文献{index}]",
                    title=str(chunk.get("doc_name") or "未命名文献"),
                    excerpt=self._truncate(content, 700),
                    score=float(score) if score is not None else None,
                    page_num=chunk.get("page_num"),
                )
            )
        return sources

    def _build_graph_evidence(self, rows: List[Dict]) -> List[AssistantGraphEvidence]:
        evidence = []
        for index, row in enumerate(rows, start=1):
            head = str(row.get("head") or "").strip()
            if not head:
                continue
            evidence.append(
                AssistantGraphEvidence(
                    citation=f"[图谱{index}]",
                    head=head,
                    relation=str(row.get("relation") or "相关实体"),
                    tail=str(row.get("tail") or "").strip() or None,
                    document_id=str(row.get("document_id")) if row.get("document_id") is not None else None,
                    evidence_text=self._truncate(str(row.get("evidence_text") or "").strip(), 500) or None,
                )
            )
        return evidence

    async def _generate_answer(
        self,
        request: AssistantChatRequest,
        sources: List[AssistantSource],
        graph_evidence: List[AssistantGraphEvidence],
    ) -> str:
        llm_config = self._llm_config()
        if llm_config is None:
            return self._fallback_answer(sources, graph_evidence)

        api_key, base_url = llm_config
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        context = self._build_context(sources, graph_evidence)
        system_prompt = (
            "你是 CeramiKG 陶瓷材料知识助手。仅依据给定的文献与知识图谱证据回答。"
            "回答应准确、简洁，并在对应结论后使用 [文献1] 或 [图谱1] 标注来源。"
            "如果证据不足，明确说明无法从现有知识库确认，不要编造事实。\n\n"
            f"可用证据：\n{context}"
        )
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(
            {"role": item.role, "content": item.content}
            for item in request.history[-8:]
        )
        messages.append({"role": "user", "content": request.question})

        response = await client.chat.completions.create(
            model=settings.MODEL_NAME,
            messages=messages,
            temperature=0.2,
        )
        answer = response.choices[0].message.content
        if not answer:
            raise RuntimeError("大模型返回了空答案")
        return answer.strip()

    def _llm_config(self) -> Optional[Tuple[str, str]]:
        if settings.API_KEY and settings.BASE_URL:
            return settings.API_KEY, settings.BASE_URL
        if settings.QWEN_API_KEY and settings.QWEN_API_KEY != "EMPTY" and settings.QWEN_API_BASE:
            return settings.QWEN_API_KEY, settings.QWEN_API_BASE
        return None

    def _build_context(
        self,
        sources: List[AssistantSource],
        graph_evidence: List[AssistantGraphEvidence],
    ) -> str:
        parts = []
        for source in sources:
            parts.append(f"{source.citation} {source.title}: {source.excerpt}")
        for item in graph_evidence:
            fact = f"{item.head} -[{item.relation}]-> {item.tail}" if item.tail else item.head
            if item.evidence_text:
                fact += f"；证据：{item.evidence_text}"
            parts.append(f"{item.citation} {fact}")
        return "\n".join(parts) if parts else "当前没有检索到可用证据。"

    def _fallback_answer(
        self,
        sources: List[AssistantSource],
        graph_evidence: List[AssistantGraphEvidence],
    ) -> str:
        if not sources and not graph_evidence:
            return "暂未从已索引文献或知识图谱中找到能够回答该问题的证据。"

        lines = ["当前已检索到以下可核对的信息："]
        for source in sources[:3]:
            lines.append(f"{source.citation} {source.excerpt}")
        for item in graph_evidence[:3]:
            fact = f"{item.head}与{item.tail}的关系为“{item.relation}”" if item.tail else item.head
            lines.append(f"{item.citation} {fact}。")
        if self._llm_config() is None:
            lines.append("当前未配置可用的大模型，因此暂以检索结果代替综合回答。")
        return "\n\n".join(lines)

    def _suggest_questions(
        self,
        sources: List[AssistantSource],
        graph_evidence: List[AssistantGraphEvidence],
    ) -> List[str]:
        suggestions = ["请总结这些证据中的关键结论"]
        if sources:
            suggestions.append(f"{sources[0].title}采用了哪些实验条件？")
        if graph_evidence:
            suggestions.append(f"{graph_evidence[0].head}还与哪些材料或工艺有关？")
        else:
            suggestions.append("现有文献中有哪些值得进一步验证的问题？")
        return suggestions[:3]

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1].rstrip() + "…"
