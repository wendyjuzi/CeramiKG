"""
文档治理API路由
实现文档信息管理与审核功能的API端点
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
import logging

from app.services.document_governance_service import DocumentGovernanceService
from app.models.schemas import (
    DocumentGovernanceListItem, DocumentGovernanceDetail,
    DocumentGovernanceCreate, DocumentGovernanceUpdate,
    DocumentReviewRequest, DocumentReviewCompleteRequest, 
    DocumentDeleteRequest, APIResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/document-governance", tags=["文档治理"])

# 依赖注入
async def get_document_service() -> DocumentGovernanceService:
    service = DocumentGovernanceService()
    await service.initialize()
    try:
        yield service
    finally:
        await service.close()

# ==================== 文档列表相关API ====================

@router.get("/documents", response_model=List[DocumentGovernanceListItem])
async def get_documents_list(
    status: Optional[int] = Query(None, description="文档状态筛选：0=待审核, 1=已审核, 2=已删除"),
    limit: Optional[int] = Query(50, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    service: DocumentGovernanceService = Depends(get_document_service)
):
    """
    获取文档列表（上半区域显示）
    
    返回字段包括：
    - id: 序号
    - name: 文档名
    - file_path: 文档路径
    - status: 状态
    - status_text: 状态文本
    - upload_time: 上传时间
    - update_time: 最近更新时间
    - upload_user: 上传用户
    - can_review: 是否可以审核
    - can_delete: 是否可以删除
    """
    try:
        documents = await service.get_documents_list(
            status=status, 
            limit=limit, 
            offset=offset
        )
        return documents
    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取文档列表失败")

@router.get("/documents/count")
async def get_documents_count(
    status: Optional[int] = Query(None, description="文档状态筛选"),
    service: DocumentGovernanceService = Depends(get_document_service)
):
    """获取文档总数（用于分页）"""
    try:
        total = await service.get_documents_count(status=status)
        return {"total": total}
    except Exception as e:
        logger.error(f"获取文档总数失败: {e}")
        raise HTTPException(status_code=500, detail="获取文档总数失败")

# ==================== 文档操作相关API ====================

@router.post("/documents", response_model=APIResponse)
async def create_document(
    document: DocumentGovernanceCreate,
    service: DocumentGovernanceService = Depends(get_document_service)
):
    """创建新文档"""
    try:
        document_id = await service.create_document(document)
        if document_id:
            return APIResponse(
                success=True,
                message="文档创建成功",
                data={"document_id": document_id}
            )
        else:
            raise HTTPException(status_code=400, detail="文档创建失败")
    except Exception as e:
        logger.error(f"创建文档失败: {e}")
        raise HTTPException(status_code=500, detail="创建文档失败")

@router.put("/documents/{document_id}", response_model=APIResponse)
async def update_document(
    document_id: int,
    document: DocumentGovernanceUpdate,
    service: DocumentGovernanceService = Depends(get_document_service)
):
    """更新文档信息"""
    try:
        success = await service.update_document(document_id, document)
        if success:
            return APIResponse(success=True, message="文档更新成功")
        else:
            raise HTTPException(status_code=404, detail="文档不存在或更新失败")
    except Exception as e:
        logger.error(f"更新文档失败: {e}")
        raise HTTPException(status_code=500, detail="更新文档失败")

@router.delete("/documents/{document_id}", response_model=APIResponse)
async def delete_document(
    document_id: int,
    force_delete: bool = Query(False, description="是否强制删除（物理删除）"),
    service: DocumentGovernanceService = Depends(get_document_service)
):
    """删除文档（逻辑删除或物理删除）"""
    try:
        request = DocumentDeleteRequest(
            document_id=document_id,
            force_delete=force_delete
        )
        success = await service.delete_document(request)
        if success:
            return APIResponse(
                success=True, 
                message="文档删除成功" if force_delete else "文档标记为删除"
            )
        else:
            raise HTTPException(status_code=404, detail="文档不存在或删除失败")
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail="删除文档失败")

# ==================== 审核流程相关API ====================

@router.get("/documents/{document_id}/review", response_model=DocumentGovernanceDetail)
async def get_document_for_review(
    document_id: int,
    service: DocumentGovernanceService = Depends(get_document_service)
):
    """
    获取文档详情用于审核（下半区域显示）
    
    包含PDF预览和JSON编辑所需的完整数据：
    - 文档基本信息
    - PDF文件路径
    - 图片文件路径 
    - 从文件系统读取的JSON数据
    - 图片文件列表
    """
    try:
        detail = await service.start_review(document_id)
        if detail:
            return detail
        else:
            raise HTTPException(status_code=404, detail="文档不存在")
    except Exception as e:
        logger.error(f"获取审核文档详情失败: {e}")
        raise HTTPException(status_code=500, detail="获取文档详情失败")

@router.post("/documents/{document_id}/review/save", response_model=APIResponse)
async def save_review_changes(
    document_id: int,
    request: DocumentReviewRequest,
    service: DocumentGovernanceService = Depends(get_document_service)
):
    """
    保存审核修改（确认修改按钮）
    
    保存用户在右区界面上所做的修改，但不改变文档状态
    """
    try:
        # 确保请求中的document_id一致
        request.document_id = document_id
        
        success = await service.save_review_changes(request)
        if success:
            return APIResponse(success=True, message="修改已保存")
        else:
            raise HTTPException(status_code=400, detail="保存修改失败")
    except Exception as e:
        logger.error(f"保存审核修改失败: {e}")
        raise HTTPException(status_code=500, detail="保存修改失败")

@router.post("/documents/{document_id}/review/complete", response_model=APIResponse)
async def complete_document_review(
    document_id: int,
    request: DocumentReviewCompleteRequest,
    service: DocumentGovernanceService = Depends(get_document_service)
):
    """
    完成文档审核（审核完毕按钮）
    
    执行以下操作：
    1. 捕获用户在右区界面上所做的所有修改
    2. 将修改后的结构化数据（JSON格式）更新保存到 MongoDB 数据库
    3. 更新MySQL documents表中该文档的状态为"已审核"和最近更新时间字段
    4. 关闭或重置审核面板，并且刷新文档列表状态
    """
    try:
        # 确保请求中的document_id一致
        request.document_id = document_id
        
        success = await service.complete_review(request)
        if success:
            return APIResponse(success=True, message="审核完成")
        else:
            raise HTTPException(status_code=400, detail="审核完成失败")
    except Exception as e:
        logger.error(f"完成审核失败: {e}")
        raise HTTPException(status_code=500, detail="审核完成失败")

# ==================== 撤销功能相关API ====================

@router.post("/documents/{document_id}/review/undo", response_model=APIResponse)
async def undo_review_changes(
    document_id: int,
    service: DocumentGovernanceService = Depends(get_document_service)
):
    """
    撤销修改（撤销修改按钮）
    
    撤销本次审核会话中用户在右边界面所做的上一次修改内容
    如重复点击，则继续撤销上一次修改内容，最多撤销5次
    """
    try:
        # TODO: 实现撤销功能
        # 这需要维护修改历史栈（最多5步）
        logger.info(f"撤销审核修改 (ID: {document_id})")
        
        return APIResponse(
            success=True, 
            message="撤销成功",
            data={"remaining_undo_count": 4}  # 示例：剩余可撤销次数
        )
    except Exception as e:
        logger.error(f"撤销修改失败: {e}")
        raise HTTPException(status_code=500, detail="撤销修改失败")

# ==================== 文件访问API ====================

@router.get("/files/pdf")
async def get_pdf_file(path: str = Query(..., description="PDF文件绝对路径")):
    """
    获取PDF文件（支持绝对路径和中文路径）
    用于预览MySQL中存储的绝对路径PDF文件
    """
    from fastapi.responses import StreamingResponse
    from pathlib import Path
    import os
    import urllib.parse
    import aiofiles
    
    try:
        # 处理URL编码的路径参数，确保正确解码中文字符
        decoded_path = urllib.parse.unquote(path, encoding='utf-8')
        file_path = Path(decoded_path)
        
        logger.info(f"请求PDF文件: 原始路径={path}, 解码路径={decoded_path}")
        logger.info(f"文件路径对象: {file_path}")
        logger.info(f"文件是否存在: {file_path.exists()}")
        
        # 检查文件是否存在
        if not file_path.exists():
            logger.error(f"PDF文件不存在: {file_path}")
            raise HTTPException(status_code=404, detail=f"PDF文件不存在: {decoded_path}")
        
        # 检查是否为PDF文件
        if not file_path.suffix.lower() == '.pdf':
            logger.error(f"不是PDF文件: {file_path}")
            raise HTTPException(status_code=400, detail="不是PDF文件")
        
        # 获取文件大小
        file_size = file_path.stat().st_size
        
        # 对文件名进行安全编码，确保中文文件名正确显示
        try:
            safe_filename = urllib.parse.quote(file_path.name, safe='')
        except Exception as e:
            logger.warning(f"文件名编码失败，使用默认名称: {e}")
            safe_filename = "document.pdf"
        
        logger.info(f"返回PDF文件: {file_path}, 安全文件名: {safe_filename}, 文件大小: {file_size}")
        
        # 创建文件流生成器
        async def generate_file():
            try:
                async with aiofiles.open(file_path, mode='rb') as file:
                    while True:
                        chunk = await file.read(8192)  # 8KB chunks
                        if not chunk:
                            break
                        yield chunk
            except Exception as e:
                logger.error(f"读取文件时出错: {e}")
                raise
        
        # 构建安全的HTTP头部
        headers = {
            "Content-Type": "application/pdf",
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=3600",
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*"
        }
        
        # 安全地设置Content-Disposition头部
        try:
            # 使用RFC 5987标准格式
            headers["Content-Disposition"] = f"inline; filename*=UTF-8''{safe_filename}"
        except Exception as e:
            logger.warning(f"设置Content-Disposition失败: {e}")
            headers["Content-Disposition"] = "inline; filename=document.pdf"
        
        return StreamingResponse(
            generate_file(),
            media_type="application/pdf",
            headers=headers
        )
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"获取PDF文件失败: {e}, 路径: {path}")
        raise HTTPException(status_code=500, detail=f"获取PDF文件失败: {str(e)}")

@router.get("/files/image")
async def get_image_file(path: str = Query(..., description="图片文件绝对路径")):
    """
    获取图片文件（支持绝对路径和中文路径）
    用于显示JSON编辑器中的图片
    """
    from fastapi.responses import StreamingResponse
    from pathlib import Path
    import mimetypes
    import urllib.parse
    import aiofiles
    
    try:
        # 处理URL编码的路径参数，确保正确解码中文字符
        decoded_path = urllib.parse.unquote(path, encoding='utf-8')
        file_path = Path(decoded_path)
        
        logger.info(f"请求图片文件: 原始路径={path}, 解码路径={decoded_path}")
        logger.info(f"文件路径对象: {file_path}")
        logger.info(f"文件是否存在: {file_path.exists()}")
        
        # 检查文件是否存在
        if not file_path.exists():
            logger.error(f"图片文件不存在: {file_path}")
            raise HTTPException(status_code=404, detail=f"图片文件不存在: {decoded_path}")
        
        # 检查是否为图片文件
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type or not mime_type.startswith('image/'):
            logger.error(f"不是图片文件: {file_path}, MIME类型: {mime_type}")
            raise HTTPException(status_code=400, detail="不是图片文件")
        
        # 获取文件大小
        file_size = file_path.stat().st_size
        
        # 对文件名进行安全编码，确保中文文件名正确显示
        try:
            safe_filename = urllib.parse.quote(file_path.name, safe='')
        except Exception as e:
            logger.warning(f"文件名编码失败，使用默认名称: {e}")
            safe_filename = "image" + (file_path.suffix if file_path.suffix else ".jpg")
        
        logger.info(f"返回图片文件: {file_path}, 安全文件名: {safe_filename}, MIME类型: {mime_type}, 文件大小: {file_size}")
        
        # 创建文件流生成器
        async def generate_file():
            try:
                async with aiofiles.open(file_path, mode='rb') as file:
                    while True:
                        chunk = await file.read(8192)  # 8KB chunks
                        if not chunk:
                            break
                        yield chunk
            except Exception as e:
                logger.error(f"读取图片文件时出错: {e}")
                raise
        
        # 构建安全的HTTP头部
        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=3600",
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*"
        }
        
        # 安全地设置Content-Disposition头部
        try:
            # 使用RFC 5987标准格式
            headers["Content-Disposition"] = f"inline; filename*=UTF-8''{safe_filename}"
        except Exception as e:
            logger.warning(f"设置Content-Disposition失败: {e}")
            headers["Content-Disposition"] = f"inline; filename=image{file_path.suffix if file_path.suffix else '.jpg'}"
        
        return StreamingResponse(
            generate_file(),
            media_type=mime_type,
            headers=headers
        )
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"获取图片文件失败: {e}, 路径: {path}")
        raise HTTPException(status_code=500, detail=f"获取图片文件失败: {str(e)}")

# ==================== 健康检查API ====================

@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "document-governance"}