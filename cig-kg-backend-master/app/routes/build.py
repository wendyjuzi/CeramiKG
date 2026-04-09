from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from app.services.kg_build_service import KGBuildService
import tempfile
import os

router = APIRouter()

@router.post("/kg_build")
async def build_knowledge_graph(
    file: UploadFile = File(...),
    database_name: str = Form(...),
    prompt: str = Form(...)
):
    """构建知识图谱"""
    try:
        # 保存上传的文件到临时目录
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # 调用构建服务
            kg_service = KGBuildService()
            result = await kg_service.build_kg(
                file_path=temp_file_path,
                database_name=database_name,
                prompt=prompt
            )
            
            return {"success": True, "message": "知识图谱构建成功", "data": result}
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"构建失败: {str(e)}")