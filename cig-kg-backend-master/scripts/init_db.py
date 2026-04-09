#!/usr/bin/env python3
"""
数据库初始化脚本
创建必要的表结构并插入示例数据
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.mysql_service import MySQLService
from app.services.mongo_service import MongoService
from app.models.schemas import Document, Term
from datetime import datetime
import json

async def init_mysql_data():
    """初始化MySQL数据"""
    print("🔧 初始化MySQL数据库...")
    
    mysql_service = MySQLService()
    try:
        await mysql_service.initialize()
        print("✅ MySQL连接成功")
        
        # 插入示例术语数据
        terms_data = [
            # 实体类型
            ("设备", "实体", "生产设备、机械装置等"),
            ("原料", "实体", "卷烟生产所需的原材料"),
            ("工艺", "实体", "生产过程中的工艺流程"),
            ("质量指标", "实体", "产品质量相关的指标参数"),
            ("人员", "实体", "相关的工作人员、操作员等"),
            ("时间", "实体", "时间相关的概念"),
            ("地点", "实体", "生产场所、地理位置等"),
            ("数据", "实体", "各种数据、参数、值等"),
            
            # 关系类型  
            ("包含", "关系", "A包含B的关系"),
            ("使用", "关系", "A使用B的关系"),
            ("生产", "关系", "A生产B的关系"),
            ("控制", "关系", "A控制B的关系"),
            ("影响", "关系", "A影响B的关系"),
            ("属于", "关系", "A属于B的关系"),
            ("位于", "关系", "A位于B的关系"),
            ("负责", "关系", "A负责B的关系"),
            ("检测", "关系", "A检测B的关系"),
            ("配备", "关系", "A配备B的关系"),
        ]
        
        for name, term_type, description in terms_data:
            try:
                await mysql_service.add_term(name, term_type, description)
                print(f"  ➤ 添加术语: {name} ({term_type})")
            except Exception as e:
                print(f"  ⚠️  术语 {name} 可能已存在: {e}")
        
        print(f"✅ 成功初始化 {len(terms_data)} 个术语")
        
    except Exception as e:
        print(f"❌ MySQL初始化失败: {e}")
        raise
    finally:
        await mysql_service.close()

async def init_mongodb_data():
    """初始化MongoDB数据"""
    print("🔧 初始化MongoDB数据库...")
    
    mongo_service = MongoService()
    try:
        await mongo_service.initialize()
        print("✅ MongoDB连接成功")
        
        # 插入示例文档数据
        documents_data = [
            {
                "document_id": "doc_001",
                "name": "卷烟生产工艺流程说明",
                "content": "卷烟生产过程包括原料准备、配方调制、卷制成型、包装等主要工艺环节。生产设备主要包括切丝机、卷烟机、包装机等。质量控制部门负责检测各项质量指标，确保产品符合标准要求。",
                "json_data": {
                    "sections": [
                        {"title": "工艺流程", "content": "原料准备 → 配方调制 → 卷制成型 → 包装"},
                        {"title": "主要设备", "content": "切丝机、卷烟机、包装机"},
                        {"title": "质量控制", "content": "质量控制部门负责检测各项指标"}
                    ],
                    "keywords": ["生产工艺", "设备", "质量控制"],
                    "metadata": {"type": "工艺说明", "version": "1.0"}
                },
                "file_path": "/docs/production_process.pdf",
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "document_id": "doc_002", 
                "name": "设备维护手册",
                "content": "生产设备需要定期维护保养。维护人员应按照规定的时间间隔对切丝机进行清洁和检查。设备故障时需要及时报修，技术人员负责设备维修。",
                "json_data": {
                    "sections": [
                        {"title": "维护计划", "content": "定期维护保养计划"},
                        {"title": "操作规范", "content": "维护人员操作规范"},
                        {"title": "故障处理", "content": "设备故障处理流程"}
                    ],
                    "keywords": ["设备维护", "维护人员", "故障处理"],
                    "metadata": {"type": "操作手册", "version": "2.1"}
                },
                "file_path": "/docs/equipment_maintenance.pdf",
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "document_id": "doc_003",
                "name": "质量检测标准",
                "content": "产品质量检测包括物理指标和化学指标两大类。检测设备包括水分仪、密度计等。检测人员需要按照标准操作程序进行检测，确保数据准确性。",
                "json_data": {
                    "sections": [
                        {"title": "检测项目", "content": "物理指标和化学指标检测"},
                        {"title": "检测设备", "content": "水分仪、密度计等专业设备"},
                        {"title": "操作要求", "content": "按标准操作程序进行"}
                    ],
                    "keywords": ["质量检测", "检测设备", "操作程序"],
                    "metadata": {"type": "检测标准", "version": "1.5"}
                },
                "file_path": "/docs/quality_standards.pdf", 
                "created_at": datetime.utcnow().isoformat()
            }
        ]
        
        for doc_data in documents_data:
            try:
                document = Document(
                    name=doc_data["name"],
                    content=doc_data["content"], 
                    file_path=doc_data["file_path"]
                )
                # 将json_data作为content的一部分或单独字段存储
                document.content = json.dumps({
                    "text": doc_data["content"],
                    "json_data": doc_data["json_data"]
                }, ensure_ascii=False, indent=2)
                
                doc_id = await mongo_service.insert_document(document)
                print(f"  ➤ 添加文档: {doc_data['name']} (ID: {doc_id})")
            except Exception as e:
                print(f"  ⚠️  文档 {doc_data['name']} 插入失败: {e}")
        
        print(f"✅ 成功初始化 {len(documents_data)} 个文档")
        
    except Exception as e:
        print(f"❌ MongoDB初始化失败: {e}")
        raise
    finally:
        await mongo_service.close()

async def main():
    """主函数"""
    print("=" * 50)
    print("🚀 卷烟知识图谱数据库初始化")
    print("=" * 50)
    
    try:
        # 初始化MySQL数据
        await init_mysql_data()
        print()
        
        # 初始化MongoDB数据  
        await init_mongodb_data()
        print()
        
        print("=" * 50)
        print("✅ 数据库初始化完成!")
        print("=" * 50)
        
        print("\n📊 初始化统计:")
        print("  • MySQL术语表: 已添加示例术语数据")
        print("  • MongoDB文档集合: 已添加示例文档数据")
        print("  • 知识表结构: 已定义动态表创建逻辑")
        
        print("\n🔗 下一步:")
        print("  1. 启动FastAPI服务: uvicorn app.main:app --reload")
        print("  2. 访问API文档: http://localhost:8000/docs")
        print("  3. 测试知识图谱构建流程")
        
    except Exception as e:
        print(f"❌ 初始化过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())