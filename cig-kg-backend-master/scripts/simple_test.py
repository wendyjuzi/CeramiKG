#!/usr/bin/env python3
"""
简单的后端API测试脚本
测试基本功能是否正常运行
"""
import sys
import os
import asyncio
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

print("🚀 开始简单功能测试")
print(f"📁 项目根目录: {project_root}")

def test_imports():
    """测试关键模块导入"""
    print("\n" + "="*50)
    print("📦 测试模块导入")
    print("="*50)
    
    try:
        # 测试配置
        from app import config
        print("✅ app.config 导入成功")
        
        # 测试数据库服务
        from app.services.mysql_service import MySQLService
        print("✅ MySQLService 导入成功")
        
        from app.services.mongo_service import MongoService  
        print("✅ MongoService 导入成功")
        
        from app.services.mongo_service_extended import MongoServiceExtended
        print("✅ MongoServiceExtended 导入成功")
        
        from app.services.prompt_service import PromptService
        print("✅ PromptService 导入成功")
        
        # 测试路由
        from app.routes.graph import router
        print("✅ GraphRouter 导入成功")
        
        # 测试模型
        from app.models.schemas import DocumentSummary, Term, Entity, Relation
        print("✅ Schemas 导入成功")
        
        return True
        
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False

def test_config():
    """测试配置"""
    print("\n" + "="*50)
    print("⚙️ 测试配置")
    print("="*50)
    
    try:
        from app.config import settings
        
        # 检查必需的配置
        required_configs = [
            'MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER', 
            'MYSQL_PASSWORD', 'MYSQL_DATABASE',
            'MONGO_URI', 'MONGO_DB', 'MONGO_COLLECTION'
        ]
        
        missing_configs = []
        for config_name in required_configs:
            if not hasattr(settings, config_name) or not getattr(settings, config_name):
                missing_configs.append(config_name)
        
        if missing_configs:
            print(f"⚠️ 缺少配置: {', '.join(missing_configs)}")
            print("📝 请检查 .env 文件或环境变量")
        else:
            print("✅ 所有必需配置都已设置")
            
        # 显示部分配置信息（不显示敏感信息）
        print(f"📊 数据库配置:")
        print(f"   MySQL: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}")
        print(f"   MongoDB: {settings.MONGO_DB}")
        
        return len(missing_configs) == 0
        
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

async def test_database_connections():
    """测试数据库连接"""
    print("\n" + "="*50)
    print("🗄️ 测试数据库连接")
    print("="*50)
    
    mysql_ok = await test_mysql_connection()
    mongo_ok = await test_mongo_connection()
    
    return mysql_ok and mongo_ok

async def test_mysql_connection():
    """测试MySQL连接"""
    try:
        from app.services.mysql_service import MySQLService
        
        service = MySQLService()
        await service.initialize()
        
        # 简单的连接测试
        async with service.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                result = await cursor.fetchone()
                if result and result[0] == 1:
                    print("✅ MySQL连接成功")
                    return True
        
        await service.close()
        return False
        
    except Exception as e:
        print(f"❌ MySQL连接失败: {e}")
        return False

async def test_mongo_connection():
    """测试MongoDB连接"""
    try:
        from app.services.mongo_service import MongoService
        
        service = MongoService()
        await service.initialize()
        
        # 简单的连接测试
        result = await service.client.admin.command('ping')
        if result.get('ok') == 1.0:
            print("✅ MongoDB连接成功")
            return True
        
        await service.close()
        return False
        
    except Exception as e:
        print(f"❌ MongoDB连接失败: {e}")
        return False

def test_schemas():
    """测试数据模型"""
    print("\n" + "="*50)
    print("📋 测试数据模型")
    print("="*50)
    
    try:
        from app.models.schemas import (
            DocumentSummary, DocumentDetail, Term, Entity, 
            Relation, EntityExtractionRequest, RelationExtractionRequest,
            KnowledgeStorageRequest, KnowledgeGraphResponse
        )
        
        # 测试创建模型实例
        doc_summary = DocumentSummary(
            document_id="test_001",
            name="测试文档",
            created_at=None,
            _id="test_001"
        )
        print("✅ DocumentSummary 创建成功")
        
        term = Term(
            id=1,
            name="测试术语",
            type="实体",
            description="测试描述"
        )
        print("✅ Term 创建成功")
        
        entity = Entity(
            id=1,
            name="测试实体",
            type="设备",
            confidence=0.95
        )
        print("✅ Entity 创建成功")
        
        relation = Relation(
            id=1,
            source_entity="实体1",
            relation_type="控制",
            target_entity="实体2",
            confidence=0.88
        )
        print("✅ Relation 创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据模型测试失败: {e}")
        return False

async def test_services():
    """测试服务层"""
    print("\n" + "="*50)
    print("🔧 测试服务层")
    print("="*50)
    
    try:
        from app.services.prompt_service import PromptService
        
        # 测试PromptService初始化
        prompt_service = PromptService()
        print("✅ PromptService 初始化成功")
        
        # 测试提示词生成
        sample_text = "生产设备包括切丝机和卷烟机。质量控制部门负责检测产品质量。"
        sample_terms = [
            {"id": 1, "name": "设备", "type": "实体"},
            {"id": 2, "name": "部门", "type": "实体"}
        ]
        
        # 这里只测试提示词生成，不实际调用LLM
        entity_prompt = prompt_service._build_entity_extraction_prompt(sample_text, sample_terms)
        if len(entity_prompt) > 0:
            print("✅ 实体提取提示词生成成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 服务层测试失败: {e}")
        return False

def print_summary(results):
    """打印测试结果总结"""
    print("\n" + "="*60)
    print("📊 测试结果总结")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    failed_tests = total_tests - passed_tests
    
    print(f"总测试项: {total_tests}")
    print(f"通过: {passed_tests} ✅")
    print(f"失败: {failed_tests} ❌")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    
    print("\n📋 详细结果:")
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    if failed_tests == 0:
        print("\n🎉 所有测试都通过了！后端基础功能正常。")
        return True
    else:
        print(f"\n⚠️ {failed_tests} 个测试失败，请检查相关配置和环境。")
        return False

async def main():
    """主测试函数"""
    print("🧪 开始后端基础功能测试")
    print(f"🕐 测试时间: {asyncio.get_event_loop().time()}")
    
    # 执行各项测试
    results = {}
    
    results["模块导入"] = test_imports()
    results["配置检查"] = test_config()
    results["数据模型"] = test_schemas()
    
    # 异步测试
    results["数据库连接"] = await test_database_connections()
    results["服务层"] = await test_services()
    
    # 打印总结
    all_passed = print_summary(results)
    
    if all_passed:
        print("\n✨ 后端准备就绪，可以启动API服务！")
        print("💡 建议下一步:")
        print("   1. 运行 uvicorn app.main:app --reload")
        print("   2. 访问 http://localhost:8000/docs 查看API文档")
        print("   3. 测试前端组件集成")
    else:
        print("\n🔧 需要修复以下问题后再启动服务")
    
    return all_passed

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试过程中发生未预期的错误: {e}")
        sys.exit(1)