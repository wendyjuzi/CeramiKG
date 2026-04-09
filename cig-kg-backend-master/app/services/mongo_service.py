from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from app.config import settings
from app.models.schemas import Document
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class MongoService:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.collection = None
    
    async def initialize(self):
        """初始化 MongoDB 连接"""
        self.client = AsyncIOMotorClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.collection = self.db[settings.MONGO_COLLECTION]
    
    async def close(self):
        """关闭 MongoDB 连接"""
        if self.client:
            self.client.close()

    async def get_documents(self) -> List[Document]:
        """从 MongoDB 获取文档列表"""
        if self.collection is None:
            await self.initialize()
        
        documents = []
        cursor = self.collection.find({})
        async for document in cursor:
            documents.append(Document(
                id=str(document["_id"]), 
                name=document.get("name", ""),
                content=document.get("content"),
                file_path=document.get("file_path"),
                created_at=document.get("created_at")
            ))
        return documents

    async def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """根据文档 ID 获取文档"""
        if self.collection is None:
            await self.initialize()
        
        try:
            document = await self.collection.find_one({"_id": ObjectId(document_id)})
            if document:
                return Document(
                    id=str(document["_id"]), 
                    name=document.get("name", ""),
                    content=document.get("content"),
                    file_path=document.get("file_path"),
                    created_at=document.get("created_at")
                )
        except Exception:
            pass
        return None

    async def insert_document(self, document: Document) -> str:
        """插入新文档"""
        if self.collection is None:
            await self.initialize()
        
        document_data = document.dict(exclude={'id'})
        document_data['created_at'] = datetime.utcnow().isoformat()
        result = await self.collection.insert_one(document_data)
        return str(result.inserted_id)

    async def update_document(self, document_id: str, update_data: dict):
        """更新文档"""
        if self.collection is None:
            await self.initialize()
        
        await self.collection.update_one(
            {"_id": ObjectId(document_id)}, 
            {"$set": update_data}
        )

    async def delete_document(self, document_id: str):
        """删除文档"""
        if self.collection is None:
            await self.initialize()
        
        await self.collection.delete_one({"_id": ObjectId(document_id)})
    
    async def search_documents(self, query: str) -> List[Document]:
        """搜索文档"""
        if self.collection is None:
            await self.initialize()
        
        documents = []
        cursor = self.collection.find({
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"content": {"$regex": query, "$options": "i"}}
            ]
        })
        async for document in cursor:
            documents.append(Document(
                id=str(document["_id"]), 
                name=document.get("name", ""),
                content=document.get("content"),
                file_path=document.get("file_path"),
                created_at=document.get("created_at")
            ))
        return documents