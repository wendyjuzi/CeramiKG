#!/usr/bin/env python3
"""
API接口测试脚本
测试所有图谱构建相关的API接口功能
"""
import asyncio
import aiohttp
import json
import sys
from typing import Dict, Any, List

# API基础URL
BASE_URL = "http://localhost:8000/api/graph"

class APITester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """发送GET请求"""
        url = f"{self.base_url}{endpoint}"
        async with self.session.get(url, params=params) as response:
            result = {
                "status": response.status,
                "data": await response.json() if response.content_type == "application/json" else await response.text()
            }
            return result

    async def post(self, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """发送POST请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        async with self.session.post(url, json=data, headers=headers) as response:
            result = {
                "status": response.status,
                "data": await response.json() if response.content_type == "application/json" else await response.text()
            }
            return result

    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """发送DELETE请求"""
        url = f"{self.base_url}{endpoint}"
        async with self.session.delete(url) as response:
            result = {
                "status": response.status,
                "data": await response.json() if response.content_type == "application/json" else await response.text()
            }
            return result

    def print_result(self, test_name: str, result: Dict[str, Any]):
        """打印测试结果"""
        status = result["status"]
        status_symbol = "✅" if 200 <= status < 300 else "❌"
        
        print(f"\n{status_symbol} {test_name}")
        print(f"   状态码: {status}")
        
        if isinstance(result["data"], dict):
            if "detail" in result["data"]:
                print(f"   详情: {result['data']['detail']}")
            elif "message" in result["data"]:
                print(f"   消息: {result['data']['message']}")
        
        if status == 200 and isinstance(result["data"], list):
            print(f"   返回数据: {len(result['data'])} 项")
        elif status == 200 and isinstance(result["data"], dict):
            if "nodes" in result["data"]:
                print(f"   图谱节点: {len(result['data']['nodes'])} 个")
                print(f"   图谱边: {len(result['data']['edges'])} 条")

async def test_documents_api(tester: APITester):
    """测试文档管理API"""
    print("=" * 60)
    print("📄 测试文档管理API")
    print("=" * 60)
    
    # 测试获取文档列表（默认数据库）
    result = await tester.get("/documents")
    tester.print_result("GET /documents (默认数据库)", result)
    
    # 测试获取文档列表（juanyan数据库）
    result = await tester.get("/documents", params={"juanyan":"true"})
    tester.print_result("GET /documents (juanyan数据库)", result)
    
    # 获取第一个文档的详情
    documents_result = await tester.get("/documents")
    if documents_result["status"] == 200 and documents_result["data"]:
        first_doc = documents_result["data"][0]
        doc_id = first_doc.get("document_id", first_doc.get("_id"))
        
        if doc_id:
            result = await tester.get(f"/documents/{doc_id}")
            tester.print_result(f"GET /documents/{doc_id}", result)

async def test_terms_api(tester: APITester):
    """测试术语库API"""
    print("=" * 60)
    print("📚 测试术语库API")
    print("=" * 60)
    
    # 测试获取所有术语
    result = await tester.get("/terms")
    tester.print_result("GET /terms (所有术语)", result)
    
    # 测试按类型筛选
    result = await tester.get("/terms", params={"term_type": "实体"})
    tester.print_result("GET /terms (实体类型)", result)
    
    result = await tester.get("/terms", params={"term_type": "关系"})
    tester.print_result("GET /terms (关系类型)", result)
    
    # 测试关键字搜索
    result = await tester.get("/terms", params={"search": "设备"})
    tester.print_result("GET /terms (搜索'设备')", result)

async def test_knowledge_extraction_api(tester: APITester):
    """测试知识抽取API"""
    print("=" * 60)
    print("🧠 测试知识抽取API")
    print("=" * 60)
    
    # 首先获取术语和文档数据
    terms_result = await tester.get("/terms")
    documents_result = await tester.get("/documents")
    
    if terms_result["status"] != 200 or documents_result["status"] != 200:
        print("❌ 无法获取测试数据，跳过知识抽取测试")
        return
    
    terms = terms_result["data"]
    documents = documents_result["data"]
    
    if not terms or not documents:
        print("❌ 测试数据为空，跳过知识抽取测试")
        return
    
    # 准备测试数据
    test_document = {
        "id": documents[0].get("document_id", documents[0].get("_id")),
        "name": documents[0].get("name", "测试文档"),
        "content": "生产设备包括切丝机和卷烟机。质量控制部门负责检测产品质量。操作人员使用设备进行生产。"
    }
    
    entity_terms = [term for term in terms if term.get("type") == "实体"][:5]
    relation_terms = [term for term in terms if term.get("type") == "关系"][:5]
    
    # 测试实体抽取
    entity_request = {
        "document": test_document,
        "terms": entity_terms
    }
    
    result = await tester.post("/entity-extraction", entity_request)
    tester.print_result("POST /entity-extraction", result)
    
    if result["status"] == 200 and result["data"]:
        entities = result["data"]
        
        # 测试关系抽取
        relation_request = {
            "entities": entities,
            "terms": relation_terms,
            "document_content": test_document["content"]
        }
        
        result = await tester.post("/relation-extraction", relation_request)
        tester.print_result("POST /relation-extraction", result)
        
        if result["status"] == 200 and result["data"]:
            relations = result["data"]
            
            # 测试知识保存
            save_request = {
                "document_name": "test_document",
                "relations": relations
            }
            
            result = await tester.post("/save-knowledge", save_request)
            tester.print_result("POST /save-knowledge", result)

async def test_knowledge_graph_api(tester: APITester):
    """测试知识图谱API"""
    print("=" * 60)
    print("🕸️  测试知识图谱API")
    print("=" * 60)
    
    # 测试获取知识表列表
    result = await tester.get("/knowledge-tables")
    tester.print_result("GET /knowledge-tables", result)
    
    # 测试获取知识图谱数据
    result = await tester.get("/knowledge-graph/test_document")
    tester.print_result("GET /knowledge-graph/test_document", result)
    
    # 测试获取表信息
    result = await tester.get("/knowledge-tables/test_document/info")
    tester.print_result("GET /knowledge-tables/test_document/info", result)

async def main():
    """主测试函数"""
    print("🚀 开始API接口测试")
    print(f"📡 目标服务器: {BASE_URL}")
    print()
    
    try:
        async with APITester() as tester:
            # 按顺序执行测试
            await test_documents_api(tester)
            await test_terms_api(tester)
            await test_knowledge_extraction_api(tester)
            await test_knowledge_graph_api(tester)
            
        print("\n" + "=" * 60)
        print("✅ API测试完成!")
        print("=" * 60)
        
    except aiohttp.ClientConnectorError:
        print("❌ 无法连接到服务器")
        print("请确保FastAPI服务正在运行:")
        print("  uvicorn app.main:app --reload")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())