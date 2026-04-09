#!/usr/bin/env python3
"""
文档治理API测试脚本
测试所有文档治理相关的API端点
"""
import asyncio
import json
import aiohttp
from datetime import datetime
from typing import Dict, Any

class DocumentGovernanceAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_prefix = "/api/document-governance"
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """发送GET请求"""
        url = f"{self.base_url}{self.api_prefix}{endpoint}"
        try:
            async with self.session.get(url, params=params) as response:
                return {
                    "status": response.status,
                    "data": await response.json(),
                    "headers": dict(response.headers)
                }
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    async def post(self, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """发送POST请求"""
        url = f"{self.base_url}{self.api_prefix}{endpoint}"
        try:
            async with self.session.post(url, json=data) as response:
                return {
                    "status": response.status,
                    "data": await response.json(),
                    "headers": dict(response.headers)
                }
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    async def put(self, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """发送PUT请求"""
        url = f"{self.base_url}{self.api_prefix}{endpoint}"
        try:
            async with self.session.put(url, json=data) as response:
                return {
                    "status": response.status,
                    "data": await response.json(),
                    "headers": dict(response.headers)
                }
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    async def delete(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """发送DELETE请求"""
        url = f"{self.base_url}{self.api_prefix}{endpoint}"
        try:
            async with self.session.delete(url, params=params) as response:
                return {
                    "status": response.status,
                    "data": await response.json(),
                    "headers": dict(response.headers)
                }
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    def print_result(self, test_name: str, result: Dict[str, Any]):
        """打印测试结果"""
        print(f"\n📋 {test_name}")
        print(f"   状态码: {result['status']}")
        
        if result['status'] == 0:
            print(f"   ❌ 错误: {result['error']}")
        elif 200 <= result['status'] < 300:
            print(f"   ✅ 成功")
            if 'data' in result and result['data']:
                if isinstance(result['data'], list):
                    print(f"   📊 返回数据: {len(result['data'])} 条记录")
                    if result['data']:
                        print(f"   📄 示例数据: {json.dumps(result['data'][0], ensure_ascii=False, indent=2)[:200]}...")
                else:
                    print(f"   📄 返回数据: {json.dumps(result['data'], ensure_ascii=False, indent=2)[:200]}...")
        else:
            print(f"   ⚠️ HTTP {result['status']}")
            if 'data' in result:
                print(f"   📄 错误信息: {result['data']}")

async def test_health_check(tester: DocumentGovernanceAPITester):
    """测试健康检查"""
    result = await tester.get("/health")
    tester.print_result("健康检查", result)
    return result

async def test_get_documents(tester: DocumentGovernanceAPITester):
    """测试获取文档列表"""
    # 测试无参数请求
    result = await tester.get("/documents")
    tester.print_result("获取全部文档列表", result)
    
    # 测试状态筛选
    result = await tester.get("/documents", {"status": 0})
    tester.print_result("获取待审核文档列表", result)
    
    # 测试分页
    result = await tester.get("/documents", {"limit": 2, "offset": 0})
    tester.print_result("获取文档列表（分页）", result)
    
    return result

async def test_get_documents_count(tester: DocumentGovernanceAPITester):
    """测试获取文档总数"""
    result = await tester.get("/documents/count")
    tester.print_result("获取文档总数", result)
    return result

async def test_create_document(tester: DocumentGovernanceAPITester):
    """测试创建文档"""
    new_doc = {
        "name": f"测试文档_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "file_path": "/test/test_document.pdf",
        "json_file_path": "/test/test_document.json",
        "image_file_path": "/test/test_document_images/",
        "upload_user": "test_user",
        "mongo_document_id": "test_001"
    }
    
    result = await tester.post("/documents", new_doc)
    tester.print_result("创建新文档", result)
    
    return result.get('data', {}).get('data', {}).get('document_id') if result['status'] == 200 else None

async def test_document_review_workflow(tester: DocumentGovernanceAPITester):
    """测试文档审核工作流"""
    # 假设有文档ID为1的文档
    document_id = 1
    
    # 1. 获取文档审核详情
    result = await tester.get(f"/documents/{document_id}/review")
    tester.print_result(f"获取文档 {document_id} 审核详情", result)
    
    if result['status'] != 200:
        print(f"⚠️ 跳过审核流程测试，文档 {document_id} 不存在")
        return
    
    # 2. 保存审核修改
    review_data = {
        "document_id": document_id,
        "json_data": [
            {
                "type": "text",
                "text": "这是测试修改的内容",
                "page_idx": 1
            }
        ]
    }
    
    result = await tester.post(f"/documents/{document_id}/review/save", review_data)
    tester.print_result(f"保存文档 {document_id} 审核修改", result)
    
    # 3. 撤销修改
    result = await tester.post(f"/documents/{document_id}/review/undo")
    tester.print_result(f"撤销文档 {document_id} 修改", result)
    
    # 4. 完成审核
    complete_data = {
        "document_id": document_id,
        "json_data": [
            {
                "type": "text",
                "text": "这是最终审核完成的内容",
                "page_idx": 1
            },
            {
                "type": "table",
                "table_body": "<table><tr><td>测试表格</td></tr></table>",
                "page_idx": 2
            }
        ]
    }
    
    result = await tester.post(f"/documents/{document_id}/review/complete", complete_data)
    tester.print_result(f"完成文档 {document_id} 审核", result)

async def test_update_document(tester: DocumentGovernanceAPITester, document_id: int):
    """测试更新文档"""
    if not document_id:
        print("⚠️ 跳过更新测试，没有有效的文档ID")
        return
    
    update_data = {
        "name": f"更新后的文档名_{datetime.now().strftime('%H%M%S')}",
        "status": 1  # 设置为已审核
    }
    
    result = await tester.put(f"/documents/{document_id}", update_data)
    tester.print_result(f"更新文档 {document_id}", result)

async def test_delete_document(tester: DocumentGovernanceAPITester, document_id: int):
    """测试删除文档"""
    if not document_id:
        print("⚠️ 跳过删除测试，没有有效的文档ID")
        return
    
    # 测试逻辑删除
    result = await tester.delete(f"/documents/{document_id}")
    tester.print_result(f"逻辑删除文档 {document_id}", result)

async def main():
    """主测试函数"""
    print("=" * 80)
    print("🧪 文档治理API功能测试")
    print("=" * 80)
    
    async with DocumentGovernanceAPITester() as tester:
        # 1. 健康检查
        await test_health_check(tester)
        
        # 2. 文档列表功能
        await test_get_documents(tester)
        await test_get_documents_count(tester)
        
        # 3. 创建文档
        new_document_id = await test_create_document(tester)
        
        # 4. 审核工作流
        await test_document_review_workflow(tester)
        
        # 5. 更新文档
        await test_update_document(tester, new_document_id)
        
        # 6. 删除文档
        await test_delete_document(tester, new_document_id)
    
    print("\n" + "=" * 80)
    print("✅ 文档治理API测试完成")
    print("=" * 80)
    print("\n📋 测试说明:")
    print("  • 确保FastAPI服务正在运行: uvicorn app.main:app --reload")
    print("  • 确保已初始化数据库: python scripts/init_documents_table.py")
    print("  • 检查API文档: http://localhost:8000/docs")

if __name__ == "__main__":
    asyncio.run(main())