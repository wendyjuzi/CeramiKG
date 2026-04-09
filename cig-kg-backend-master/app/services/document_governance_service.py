"""
文档治理服务
整合MySQL documents表和MongoDB JSON数据的业务逻辑
"""
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from app.services.mysql_service import MySQLService
from app.services.mongo_service_extended import MongoServiceExtended
from app.services.file_service import FileService
from app.models.schemas import (
    DocumentGovernance, DocumentGovernanceCreate, DocumentGovernanceUpdate,
    DocumentGovernanceListItem, DocumentGovernanceDetail, 
    DocumentReviewRequest, DocumentReviewCompleteRequest, DocumentDeleteRequest
)

logger = logging.getLogger(__name__)

class DocumentGovernanceService:
    def __init__(self):
        self.mysql_service = MySQLService()
        self.mongo_service = MongoServiceExtended()
        self.file_service = FileService()
    
    async def initialize(self):
        """初始化服务"""
        await self.mysql_service.initialize()
        await self.mongo_service.initialize()
    
    async def close(self):
        """关闭服务"""
        await self.mysql_service.close()
        await self.mongo_service.close()
    
    # ==================== 文档列表相关 ====================
    
    async def get_documents_list(
        self, 
        status: Optional[int] = None, 
        limit: Optional[int] = None, 
        offset: int = 0
    ) -> List[DocumentGovernanceListItem]:
        """获取文档列表（用于上半区域显示）"""
        try:
            return await self.mysql_service.get_documents(status=status, limit=limit, offset=offset)
        except Exception as e:
            logger.error(f"获取文档列表失败: {e}")
            return []
    
    async def get_documents_count(self, status: Optional[int] = None) -> int:
        """获取文档总数"""
        try:
            return await self.mysql_service.get_documents_count(status=status)
        except Exception as e:
            logger.error(f"获取文档总数失败: {e}")
            return 0
    
    # ==================== 文档详情相关 ====================
    
    async def get_document_detail(self, document_id: int) -> Optional[DocumentGovernanceDetail]:
        """获取文档详情（用于审核面板）"""
        try:
            # 从MySQL获取文档基本信息
            document = await self.mysql_service.get_document_by_id(document_id)
            if not document:
                return None
            
            # 从文件系统读取JSON数据（替代原来的MongoDB读取）
            json_data = await self.file_service.read_json_file(document.json_file_path)
            
            # 从文件系统读取图片文件列表
            image_files = await self.file_service.read_image_directory(document.image_file_path)
            
            # 组装详情数据
            return DocumentGovernanceDetail(
                id=document.id,
                name=document.name,
                file_path=document.file_path,
                pdf_path=document.pdf_path,
                json_file_path=document.json_file_path,
                image_file_path=document.image_file_path,
                status=document.status,
                upload_time=document.upload_time,
                update_time=document.update_time,
                upload_user=document.upload_user,
                json_data=json_data,
                image_files=image_files
            )
        except Exception as e:
            logger.error(f"获取文档详情失败 (ID: {document_id}): {e}")
            return None
    
    # ==================== 文档操作相关 ====================
    
    async def create_document(self, document: DocumentGovernanceCreate) -> Optional[int]:
        """创建新文档"""
        try:
            return await self.mysql_service.create_document(document)
        except Exception as e:
            logger.error(f"创建文档失败: {e}")
            return None
    
    async def update_document(self, document_id: int, document: DocumentGovernanceUpdate) -> bool:
        """更新文档信息"""
        try:
            return await self.mysql_service.update_document(document_id, document)
        except Exception as e:
            logger.error(f"更新文档失败 (ID: {document_id}): {e}")
            return False
    
    async def delete_document(self, request: DocumentDeleteRequest) -> bool:
        """删除文档（逻辑删除）"""
        try:
            return await self.mysql_service.delete_document(
                request.document_id, 
                force_delete=request.force_delete
            )
        except Exception as e:
            logger.error(f"删除文档失败 (ID: {request.document_id}): {e}")
            return False
    
    # ==================== 审核流程相关 ====================
    
    async def start_review(self, document_id: int) -> Optional[DocumentGovernanceDetail]:
        """开始审核流程（获取文档详情用于审核面板）"""
        return await self.get_document_detail(document_id)
    
    async def save_review_changes(self, request: DocumentReviewRequest) -> bool:
        """保存审核过程中的修改（临时保存，不改变状态）"""
        try:
            # 这里可以实现临时保存逻辑，比如保存到缓存或临时表
            # 当前版本直接返回True，实际应用中可能需要实现撤销功能的历史记录
            logger.info(f"保存审核修改 (ID: {request.document_id})")
            return True
        except Exception as e:
            logger.error(f"保存审核修改失败 (ID: {request.document_id}): {e}")
            return False
    
    async def complete_review(self, request: DocumentReviewCompleteRequest) -> bool:
        """完成审核流程"""
        try:
            # 1. 获取文档信息
            document = await self.mysql_service.get_document_by_id(request.document_id)
            if not document:
                logger.error(f"文档不存在 (ID: {request.document_id})")
                return False
            
            # 2. 将审核完毕的JSON数据插入到MongoDB
            logger.info(f"开始插入审核完毕的JSON数据到MongoDB (ID: {request.document_id})")
            mongo_success = await self.mongo_service.insert_json_data(
                str(request.document_id), 
                request.json_data,
                document.name  # 传递文档名称
            )
            if not mongo_success:
                logger.error(f"插入JSON数据到MongoDB失败 (ID: {request.document_id})")
                return False
            
            logger.info(f"成功插入JSON数据到MongoDB (ID: {request.document_id}, 数据项数量: {len(request.json_data)})")
            
            # 3. 更新MySQL中的文档状态为"已审核"(1)
            success = await self.mysql_service.update_document_status(request.document_id, 1)
            if not success:
                logger.error(f"更新文档状态失败 (ID: {request.document_id})")
                return False
            
            logger.info(f"审核完成 (ID: {request.document_id})")
            return True
            
        except Exception as e:
            logger.error(f"完成审核失败 (ID: {request.document_id}): {e}")
            return False
    
