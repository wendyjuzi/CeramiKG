from fastapi import APIRouter, File, UploadFile, HTTPException
from app.services.getEntities_service import EntitiesService
import tempfile
import os

router = APIRouter()

@router.post("/list")
async def get_entities_list(file: UploadFile = File(...)):
    """获取实体列表"""
    try:
        # 保存上传的文件到临时目录
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # 调用实体提取服务
            entities_service = EntitiesService()
            entities = await entities_service.extract_entities(temp_file_path)
            
            return {"entities": entities}
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"实体提取失败: {str(e)}")