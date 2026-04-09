"""
MongoDB服务扩展 - 专门处理juanyan.cigarette_kg.documents的查询
异常12修复：确保JSON数据格式正确性
"""
from motor.motor_asyncio import AsyncIOMotorClient
# from bson import ObjectId
from app.config import settings
from app.utils.json_validator import JSONValidator, validate_json_field, safe_serialize
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class MongoServiceExtended:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
    
    async def initialize(self):
        """初始化 MongoDB 连接"""
        self.client = AsyncIOMotorClient(settings.MONGO_URI)
    
    async def close(self):
        """关闭 MongoDB 连接"""
        if self.client:
            self.client.close()

    async def get_documents_from_juanyan(self) -> List[Dict[str, Any]]:
        """从 cigarette_kg.documents 获取文档列表（实际数据库结构）"""
        if self.client is None:
            await self.initialize()
        
        # 连接到实际的数据库结构：cigarette_kg数据库的documents集合
        cigarette_kg_db = self.client["documents"]
        documents_collection = cigarette_kg_db["documents_json"]
        
        documents = []
        try:
            # 直接查询documents集合中的文档
            cursor = documents_collection.find({})
            async for doc in cursor:
                # 从json_data提取text内容作为content
                json_data = doc.get("json_data", [])
                content_texts = []
                if isinstance(json_data, list):
                    for item in json_data:
                        if isinstance(item, dict) and "text" in item:
                            text = item["text"].strip()
                            if text:  # 只添加非空文本
                                content_texts.append(text)
                
                # 将提取的文本拼接作为content
                extracted_content = " ".join(content_texts) if content_texts else None
                
                documents.append({
                    "document_id": doc.get("document_id"),
                    "name": doc.get("name", f"文档{doc.get('document_id', '未知')}"),
                    "json_data": json_data,
                    "content": extracted_content,  # 使用从json_data提取的内容
                    "created_at": doc.get("created_at"),
                    "updated_at": doc.get("updated_at"),
                    "_id": str(doc.get("_id", ""))
                })
                    
        except Exception as e:
            logger.error(f"Error querying cigarette_kg database: {e}")
        
        return documents

    async def get_document_by_document_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """根据 document_id 从 cigarette_kg.documents 获取文档详情"""
        if self.client is None:
            await self.initialize()
        
        # 连接到实际的数据库结构
        cigarette_kg_db = self.client["documents"]
        documents_collection = cigarette_kg_db["documents_json"]
        
        try:
            # 尝试将document_id转换为整数（根据示例数据，document_id可能是数字）
            try:
                doc_id_int = int(document_id)
                document = await documents_collection.find_one({"document_id": doc_id_int})
            except ValueError:
                # 如果转换失败，使用字符串查询
                document = await documents_collection.find_one({"document_id": document_id})
            
            if document:
                logger.info(f"Found document: {document.get('document_id')}")
                
                # 从json_data提取text内容作为content
                json_data = document.get("json_data", [])
                content_texts = []
                if isinstance(json_data, list):
                    for item in json_data:
                        if isinstance(item, dict) and "text" in item:
                            text = item["text"].strip()
                            if text:  # 只添加非空文本
                                content_texts.append(text)
                
                # 将提取的文本拼接作为content
                extracted_content = " ".join(content_texts) if content_texts else None
                
                # 异常12修复：验证和修复json_data字段
                json_data_validation = validate_json_field(json_data, 'json_data')
                
                # 记录修复信息
                if json_data_validation.get('repair_actions'):
                    logger.info(f"文档 {document.get('document_id')} json_data修复: {json_data_validation['repair_actions']}")
                
                if json_data_validation.get('error_message'):
                    logger.warning(f"文档 {document.get('document_id')} json_data问题: {json_data_validation['error_message']}")
                
                # 使用修复后的数据
                cleaned_json_data = json_data_validation.get('fixed_data', [])
                
                return {
                    "document_id": document.get("document_id"),
                    "name": document.get("name", f"文档{document.get('document_id', '未知')}"),
                    "json_data": cleaned_json_data,  # 使用验证和修复后的数据
                    "content": extracted_content,  # 使用从json_data提取的内容
                    "created_at": document.get("created_at"),
                    "updated_at": document.get("updated_at"),
                    "_id": str(document.get("_id", "")),
                    "_json_validation": {  # 添加验证信息用于调试
                        "original_type": json_data_validation.get('original_type'),
                        "is_valid": json_data_validation.get('is_valid'),
                        "repair_actions": json_data_validation.get('repair_actions', [])
                    }
                }
                
        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
        
        logger.warning(f"Document {document_id} not found")
        return None

    async def get_json_data(self, document_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取文档的json_data字段（异常36修复：添加缺少的方法）"""
        if self.client is None:
            await self.initialize()
        
        # 连接到实际的数据库结构
        cigarette_kg_db = self.client["documents"]
        documents_collection = cigarette_kg_db["documents_json"]
        
        try:
            # 尝试将document_id转换为整数
            try:
                doc_id_int = int(document_id)
                document = await documents_collection.find_one(
                    {"document_id": doc_id_int}, 
                    {"json_data": 1, "document_id": 1}  # 只获取需要的字段
                )
            except ValueError:
                # 如果转换失败，使用字符串查询
                document = await documents_collection.find_one(
                    {"document_id": document_id}, 
                    {"json_data": 1, "document_id": 1}
                )
            
            if document:
                json_data = document.get("json_data", [])
                logger.info(f"获取文档 {document_id} 的json_data，包含 {len(json_data) if isinstance(json_data, list) else 0} 个chunk")
                
                # 异常36修复：验证json_data格式
                if not isinstance(json_data, list):
                    logger.warning(f"文档 {document_id} 的json_data不是列表格式，尝试修复")
                    json_data = []
                
                # 验证每个chunk的结构
                valid_chunks = []
                for i, chunk in enumerate(json_data):
                    if isinstance(chunk, dict):
                        # 确保chunk包含必要的字段
                        if "text" in chunk or "page_idx" in chunk:
                            valid_chunks.append(chunk)
                        else:
                            logger.warning(f"文档 {document_id} chunk {i} 缺少必要字段: {list(chunk.keys())}")
                    else:
                        logger.warning(f"文档 {document_id} chunk {i} 不是字典格式")
                
                logger.info(f"文档 {document_id} 有效chunk数量: {len(valid_chunks)}")
                return valid_chunks
                
        except Exception as e:
            logger.error(f"获取文档 {document_id} 的json_data失败: {e}")
        
        logger.warning(f"无法获取文档 {document_id} 的json_data")
        return None

    async def update_json_data(self, document_id: str, json_data: List[Dict[str, Any]]) -> bool:
        """更新文档的json_data字段（文档治理审核功能）"""
        if self.client is None:
            await self.initialize()
        
        # 连接到实际的数据库结构
        cigarette_kg_db = self.client["documents"]
        documents_collection = cigarette_kg_db["documents_json"]
        
        try:
            # 尝试将document_id转换为整数
            try:
                doc_id_int = int(document_id)
                filter_query = {"document_id": doc_id_int}
            except ValueError:
                # 如果转换失败，使用字符串查询
                filter_query = {"document_id": document_id}
            
            # 验证json_data格式
            if not isinstance(json_data, list):
                logger.error(f"json_data必须是列表格式，当前类型: {type(json_data)}")
                return False
            
            # 验证每个chunk的结构
            validated_chunks = []
            for i, chunk in enumerate(json_data):
                if not isinstance(chunk, dict):
                    logger.warning(f"跳过无效chunk {i}：不是字典格式")
                    continue
                
                # 确保chunk包含必要的字段
                if "type" not in chunk:
                    logger.warning(f"Chunk {i} 缺少type字段，设置默认值")
                    chunk["type"] = "text"
                
                validated_chunks.append(chunk)
            
            # 执行更新操作
            update_result = await documents_collection.update_one(
                filter_query,
                {
                    "$set": {
                        "json_data": validated_chunks,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            
            if update_result.matched_count == 0:
                logger.warning(f"文档 {document_id} 不存在")
                return False
            
            if update_result.modified_count == 0:
                logger.info(f"文档 {document_id} 的json_data没有变化")
                return True
            
            logger.info(f"成功更新文档 {document_id} 的json_data，包含 {len(validated_chunks)} 个chunk")
            return True
            
        except Exception as e:
            logger.error(f"更新文档 {document_id} 的json_data失败: {e}")
            return False

    async def backup_json_data(self, document_id: str) -> Optional[List[Dict[str, Any]]]:
        """备份当前的json_data（用于撤销功能）"""
        try:
            return await self.get_json_data(document_id)
        except Exception as e:
            logger.error(f"备份文档 {document_id} 的json_data失败: {e}")
            return None

    async def insert_json_data(self, document_id: str, json_data: List[Dict[str, Any]], document_name: str = None) -> bool:
        """插入新的JSON数据到MongoDB（文档治理审核完毕功能）"""
        if self.client is None:
            await self.initialize()
        
        # 连接到指定的数据库和集合
        documents_db = self.client[settings.MONGO_DB]  # "documents" 数据库
        documents_collection = documents_db[settings.MONGO_COLLECTION]  # "documents_json" 集合
        
        try:
            # 验证json_data格式
            if not isinstance(json_data, list):
                logger.error(f"json_data必须是列表格式，当前类型: {type(json_data)}")
                return False
            
            # 验证每个chunk的结构
            validated_chunks = []
            for i, chunk in enumerate(json_data):
                if not isinstance(chunk, dict):
                    logger.warning(f"跳过无效chunk {i}：不是字典格式")
                    continue
                
                # 确保chunk包含必要的字段
                if "type" not in chunk:
                    logger.warning(f"Chunk {i} 缺少type字段，设置默认值")
                    chunk["type"] = "text"
                
                validated_chunks.append(chunk)
            
            # 尝试将document_id转换为整数
            try:
                doc_id_int = int(document_id)
            except ValueError:
                doc_id_int = document_id
            
            # 构建要插入的文档
            document_to_insert = {
                "document_id": doc_id_int,
                "name": document_name or f"文档{document_id}",
                "json_data": validated_chunks,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # 执行插入操作
            insert_result = await documents_collection.insert_one(document_to_insert)
            
            if insert_result.inserted_id:
                logger.info(f"成功插入文档 {document_id} 的JSON数据到MongoDB，包含 {len(validated_chunks)} 个chunk，插入ID: {insert_result.inserted_id}")
                return True
            else:
                logger.error(f"插入文档 {document_id} 的JSON数据失败")
                return False
            
        except Exception as e:
            logger.error(f"插入文档 {document_id} 的JSON数据失败: {e}")
            return False