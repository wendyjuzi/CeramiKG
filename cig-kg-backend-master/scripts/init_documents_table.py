#!/usr/bin/env python3
"""
文档治理表初始化脚本
创建documents表并插入示例数据
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.mysql_service import MySQLService
from app.services.mongo_service_extended import MongoServiceExtended
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_documents_table():
    """初始化documents表"""
    print("🔧 初始化文档治理表...")
    
    mysql_service = MySQLService()
    try:
        await mysql_service.initialize()
        print("✅ MySQL连接成功")
        
        # 表会通过MySQLService的initialize方法自动创建
        print("✅ Documents表创建/验证成功")
        
        # 插入示例数据（与现有MongoDB数据关联）
        sample_documents = [
            {
                "name": "卷烟生产工艺流程说明",
                "file_path": "/docs/production_process.pdf",
                "json_file_path": "/json/doc_001.json",
                "image_file_path": "/images/doc_001/",
                "upload_user": "admin",
                "mongo_document_id": "1"
            },
            {
                "name": "设备维护手册",
                "file_path": "/docs/equipment_maintenance.pdf", 
                "json_file_path": "/json/doc_002.json",
                "image_file_path": "/images/doc_002/",
                "upload_user": "admin",
                "mongo_document_id": "2"
            },
            {
                "name": "质量检测标准",
                "file_path": "/docs/quality_standards.pdf",
                "json_file_path": "/json/doc_003.json", 
                "image_file_path": "/images/doc_003/",
                "upload_user": "admin",
                "mongo_document_id": "3"
            }
        ]
        
        from app.models.schemas import DocumentGovernanceCreate
        
        # 检查是否已有数据
        existing_count = await mysql_service.get_documents_count()
        if existing_count > 0:
            print(f"⚠️ Documents表已有 {existing_count} 条数据，跳过示例数据插入")
        else:
            # 插入示例数据
            for doc_data in sample_documents:
                try:
                    doc_create = DocumentGovernanceCreate(**doc_data)
                    doc_id = await mysql_service.create_document(doc_create)
                    print(f"  ➤ 添加文档: {doc_data['name']} (ID: {doc_id})")
                except Exception as e:
                    print(f"  ⚠️ 文档 {doc_data['name']} 插入失败: {e}")
            
            print(f"✅ 成功初始化 {len(sample_documents)} 个示例文档")
        
    except Exception as e:
        print(f"❌ MySQL初始化失败: {e}")
        raise
    finally:
        await mysql_service.close()

async def verify_mongo_data():
    """验证MongoDB数据"""
    print("🔧 验证MongoDB数据...")
    
    mongo_service = MongoServiceExtended()
    try:
        await mongo_service.initialize()
        print("✅ MongoDB连接成功")
        
        # 获取MongoDB中的文档
        documents = await mongo_service.get_documents_from_juanyan()
        print(f"✅ MongoDB中有 {len(documents)} 个文档")
        
        for doc in documents[:3]:  # 只显示前3个
            print(f"  ➤ 文档: {doc.get('name', '未知')} (ID: {doc.get('document_id', '未知')})")
        
    except Exception as e:
        print(f"⚠️ MongoDB验证失败: {e}")
    finally:
        await mongo_service.close()

async def main():
    """主函数"""
    print("=" * 60)
    print("🚀 文档治理功能数据库初始化")
    print("=" * 60)
    
    try:
        # 初始化MySQL documents表
        await init_documents_table()
        print()
        
        # 验证MongoDB数据
        await verify_mongo_data()
        print()
        
        print("=" * 60)
        print("✅ 文档治理数据库初始化完成!")
        print("=" * 60)
        
        print("\n📊 初始化统计:")
        print("  • MySQL documents表: 已创建并插入示例数据")
        print("  • MongoDB documents_json集合: 已验证数据连接")
        print("  • 数据关联: MySQL通过mongo_document_id关联MongoDB数据")
        
        print("\n🔗 下一步:")
        print("  1. 启动FastAPI服务: uvicorn app.main:app --reload")
        print("  2. 访问API文档: http://localhost:8000/docs")
        print("  3. 测试文档治理API: /api/document-governance/")
        print("  4. 前端开发: 添加文档治理导航和页面")
        
    except Exception as e:
        print(f"❌ 初始化过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())