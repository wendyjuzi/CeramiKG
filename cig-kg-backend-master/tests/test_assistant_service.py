import unittest
from unittest.mock import AsyncMock, patch

from app.models.assistant import AssistantChatRequest
from app.services.assistant_service import AssistantService
from app.services.neo4j_service import Neo4jService


class DummyNeo4jService:
    driver = object()


class AssistantServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_combines_literature_and_graph_without_llm(self):
        service = AssistantService(DummyNeo4jService())
        service._retrieve_literature = AsyncMock(return_value=[{
            "content": "氧化铝陶瓷的致密度随烧结温度升高而增加。",
            "doc_name": "氧化铝陶瓷烧结研究.pdf",
            "display_title": "氧化铝陶瓷烧结研究",
            "score": 3.2,
            "page_num": 4,
            "document_id": 42,
            "repository": "ceramic_papers",
            "preview_path": "/files/ceramic_papers/42/preview",
        }])
        service._retrieve_graph = AsyncMock(return_value=[{
            "head": "氧化铝陶瓷",
            "relation": "受影响于",
            "tail": "烧结温度",
            "document_id": "12",
            "paper_title": "氧化铝陶瓷烧结研究",
            "evidence_text": "烧结温度影响晶粒生长和致密化。",
        }])

        with patch.object(service, "_llm_config", return_value=None):
            result = await service.chat(AssistantChatRequest(
                question="哪些因素影响氧化铝陶瓷致密度？",
                document_ids=["12"],
            ))

        self.assertEqual(len(result.sources), 1)
        self.assertEqual(len(result.graph_evidence), 1)
        self.assertIn("[文献1]", result.answer)
        self.assertIn("[图谱1]", result.answer)
        self.assertEqual(result.metadata["generated_by"], "retrieval")
        self.assertEqual(result.metadata["document_ids"], ["12"])
        self.assertEqual(result.metadata["document_names"], [])
        self.assertEqual(result.graph_evidence[0].paper_title, "氧化铝陶瓷烧结研究")
        self.assertEqual(result.sources[0].title, "氧化铝陶瓷烧结研究")
        self.assertEqual(result.sources[0].document_id, 42)
        self.assertEqual(result.sources[0].preview_path, "/files/ceramic_papers/42/preview")

    async def test_chat_returns_clear_message_when_no_evidence_exists(self):
        service = AssistantService(DummyNeo4jService())
        service._retrieve_literature = AsyncMock(return_value=[])
        service._retrieve_graph = AsyncMock(return_value=[])

        with patch.object(service, "_llm_config", return_value=None):
            result = await service.chat(AssistantChatRequest(question="一个未知问题"))

        self.assertIn("暂未", result.answer)
        self.assertEqual(result.sources, [])
        self.assertEqual(result.graph_evidence, [])

    async def test_graph_mode_does_not_call_literature_service(self):
        service = AssistantService(DummyNeo4jService())
        service._retrieve_literature = AsyncMock(return_value=[])
        service._retrieve_graph = AsyncMock(return_value=[])

        with patch.object(service, "_llm_config", return_value=None):
            await service.chat(AssistantChatRequest(
                question="氧化锆和氧化铝有什么关系？",
                mode="graph",
            ))

        service._retrieve_literature.assert_not_called()
        service._retrieve_graph.assert_awaited_once()


class Neo4jAssistantSearchTermTests(unittest.TestCase):
    def test_chinese_question_produces_bounded_material_terms(self):
        terms = Neo4jService._assistant_search_terms("哪些因素影响氧化铝陶瓷烧结致密度？")

        self.assertIn("氧化铝", terms)
        self.assertIn("烧结", terms)
        self.assertLessEqual(len(terms), 24)
        self.assertNotIn("哪些", terms)


class AssistantLiteratureScopeTests(unittest.TestCase):
    def test_scope_uses_catalog_file_name_for_rag_filter(self):
        names = AssistantService._document_names_for_retrieval(
            ["氧化铝陶瓷烧结研究", "未登记文献"],
            [{
                "document_name": "氧化铝陶瓷烧结研究",
                "file_name": "alumina_sintering.pdf",
            }],
        )

        self.assertEqual(names, ["alumina_sintering.pdf", "未登记文献"])


if __name__ == "__main__":
    unittest.main()
