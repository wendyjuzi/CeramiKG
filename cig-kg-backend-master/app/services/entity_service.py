from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os

# 定义数据模型
class Entity(BaseModel):
    id: str
    name: str
    type: str
    properties: Dict[str, Any]


class EntityListResponse(BaseModel):
    entities: List[Entity]


class BuildResponse(BaseModel):
    success: bool
    message: str
    filtered_file_path: Optional[str] = None

def read_all_json_files(directory: str) -> List[Dict]:
    """
    读取指定目录下的所有JSON文件
    """
    json_files_data = []

    if not os.path.exists(directory):
        return json_files_data

    # 遍历目录下的所有文件
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 添加文件名信息以便追踪数据来源
                    data['source_file'] = filename
                    json_files_data.append(data)
            except (json.JSONDecodeError, Exception) as e:
                print(f"读取文件 {filename} 时出错: {str(e)}")
                continue

    return json_files_data