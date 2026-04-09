from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from app.services.img_service import get_image_path

router = APIRouter()


@router.get("/{image_path}")
async def serve_image(image_path: str):
    """根据路径返回图片文件"""
    try:
        image_blob = get_image_path(image_path)
        return FileResponse(image_blob)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"图片不存在, image_path={image_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取图片失败: {str(e)}")