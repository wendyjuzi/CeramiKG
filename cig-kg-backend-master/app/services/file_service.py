"""
文件读取服务
处理JSON文件和图片文件的读取操作
"""
import json
import os
from typing import List, Dict, Any, Optional
import logging
import aiofiles
from pathlib import Path

logger = logging.getLogger(__name__)

class FileService:
    def __init__(self, base_path: str = ""):
        """
        初始化文件服务
        
        Args:
            base_path: 文件系统的基础路径
        """
        env_base_path = os.getenv("FILE_BASE_PATH", "")
        if env_base_path:
            self.base_path = Path(env_base_path)
        else:
            self.base_path = Path(base_path) if base_path else Path.cwd()
    
    async def read_json_file(self, json_file_path: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        """
        读取JSON文件内容
        
        Args:
            json_file_path: JSON文件路径
            
        Returns:
            JSON数据列表，读取失败时返回None
        """
        if not json_file_path:
            logger.warning("JSON文件路径为空")
            return None
        
        try:
            # 处理相对路径和绝对路径
            file_path = self._resolve_path(json_file_path)
            
            # 检查文件是否存在
            if not file_path.exists():
                logger.warning(f"JSON文件不存在: {file_path}")
                return None
            
            # 异步读取文件
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                content = await file.read()
                
            # 解析JSON
            json_data = json.loads(content)
            
            # 确保返回的是列表格式
            if isinstance(json_data, list):
                logger.info(f"成功读取JSON文件: {file_path}, 数据条数: {len(json_data)}")
                return json_data
            elif isinstance(json_data, dict):
                logger.info(f"成功读取JSON文件: {file_path}, 转换为列表格式")
                return [json_data]
            else:
                logger.warning(f"JSON文件格式不正确: {file_path}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败 ({json_file_path}): {e}")
            return None
        except Exception as e:
            logger.error(f"读取JSON文件失败 ({json_file_path}): {e}")
            return None
    
    async def read_image_directory(self, image_dir_path: Optional[str]) -> Optional[List[str]]:
        """
        读取图片目录下的图片文件列表
        
        Args:
            image_dir_path: 图片目录路径
            
        Returns:
            图片文件路径列表，读取失败时返回None
        """
        if not image_dir_path:
            logger.warning("图片目录路径为空")
            return None
        
        try:
            # 处理相对路径和绝对路径
            dir_path = self._resolve_path(image_dir_path)
            
            # 检查目录是否存在
            if not dir_path.exists():
                logger.warning(f"图片目录不存在: {dir_path}")
                return None
            
            if not dir_path.is_dir():
                logger.warning(f"路径不是目录: {dir_path}")
                return None
            
            # 支持的图片格式
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
            
            # 获取目录下的所有图片文件
            image_files = []
            for file_path in dir_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                    # 返回相对于base_path的路径
                    relative_path = str(file_path.relative_to(self.base_path)) if self.base_path in file_path.parents else str(file_path)
                    image_files.append(relative_path)
            
            # 按文件名排序
            image_files.sort()
            
            logger.info(f"成功读取图片目录: {dir_path}, 图片数量: {len(image_files)}")
            return image_files
            
        except Exception as e:
            logger.error(f"读取图片目录失败 ({image_dir_path}): {e}")
            return None
    
    def _resolve_path(self, file_path: str) -> Path:
        """
        解析文件路径，处理相对路径和绝对路径
        
        Args:
            file_path: 文件路径字符串
            
        Returns:
            解析后的Path对象
        """
        path = Path(file_path)
        
        # 如果是绝对路径，直接返回
        if path.is_absolute():
            return path
        
        # 如果是相对路径，相对于base_path解析
        return self.base_path / path
    
    async def check_file_exists(self, file_path: Optional[str]) -> bool:
        """
        检查文件是否存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件是否存在
        """
        if not file_path:
            return False
        
        try:
            resolved_path = self._resolve_path(file_path)
            return resolved_path.exists()
        except Exception:
            return False