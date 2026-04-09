from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime

app = FastAPI()

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# 配置文件路径
JSON_DATA_DIR = "json_data"  # 存放所有JSON文件的文件夹路径
FILTERED_JSON_DIR = "filtered_data"  # 过滤后的JSON文件保存目录

# 确保目录存在
os.makedirs(JSON_DATA_DIR, exist_ok=True)
os.makedirs(FILTERED_JSON_DIR, exist_ok=True)


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


@app.get("/api/entities/list", response_model=EntityListResponse)
async def get_entities():
    """
    获取实体列表，从文件夹下所有JSON文件中读取nodes数据
    """
    try:
        # 读取所有JSON文件
        json_files_data = read_all_json_files(JSON_DATA_DIR)

        if not json_files_data:
            raise HTTPException(status_code=404, detail="未找到任何JSON文件")

        # 提取所有文件中的nodes数据并转换为Entity格式
        entities = []

        for file_data in json_files_data:
            nodes = file_data.get("nodes", [])
            source_file = file_data.get("source_file", "unknown")

            for node in nodes:
                # 在属性中添加来源文件信息
                properties = node.get("properties", {})
                properties["source_file"] = source_file

                entity = Entity(
                    id=node.get("id", ""),
                    name=node.get("name", ""),
                    type=node.get("type", ""),
                    properties=properties
                )
                entities.append(entity)

        # 根据ID去重（如果多个文件中有相同ID的实体，保留第一个）
        unique_entities = {}
        for entity in entities:
            if entity.id not in unique_entities:
                unique_entities[entity.id] = entity

        return EntityListResponse(entities=list(unique_entities.values()))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@app.post("/api/build/kg_build", response_model=BuildResponse)
async def build_knowledge_graph(
        file: UploadFile = File(...),
        database_name: str = Form(...),
        prompt: str = Form(...),
        selected_entities: str = Form(...)
):
    """
    构建知识图谱，根据选中的实体ID过滤原始数据
    """
    try:
        # 解析选中的实体ID列表
        selected_entity_ids = json.loads(selected_entities)

        # 读取所有JSON文件
        json_files_data = read_all_json_files(JSON_DATA_DIR)

        if not json_files_data:
            raise HTTPException(status_code=404, detail="未找到任何JSON文件")

        # 合并所有文件的数据并过滤
        all_filtered_nodes = []
        all_filtered_relationships = []

        for file_data in json_files_data:
            source_file = file_data.get("source_file", "unknown")

            # 过滤nodes数据
            for node in file_data.get("nodes", []):
                if node.get("id") in selected_entity_ids:
                    # 添加来源文件信息
                    node_copy = node.copy()
                    if "properties" not in node_copy:
                        node_copy["properties"] = {}
                    node_copy["properties"]["source_file"] = source_file
                    all_filtered_nodes.append(node_copy)

            # 过滤relationships数据，只保留涉及选中实体的关系
            for rel in file_data.get("relationships", []):
                if (rel.get("from") in selected_entity_ids and
                        rel.get("to") in selected_entity_ids):
                    # 添加来源文件信息
                    rel_copy = rel.copy()
                    rel_copy["source_file"] = source_file
                    all_filtered_relationships.append(rel_copy)

        # 根据ID去重nodes（保留第一个出现的）
        unique_nodes = {}
        for node in all_filtered_nodes:
            if node["id"] not in unique_nodes:
                unique_nodes[node["id"]] = node

        # 创建过滤后的数据结构
        filtered_data = {
            "nodes": list(unique_nodes.values()),
            "relationships": all_filtered_relationships,
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "database_name": database_name,
                "total_source_files": len(json_files_data),
                "source_files": [data.get("source_file", "unknown") for data in json_files_data],
                "selected_entities_count": len(selected_entity_ids),
                "filtered_nodes_count": len(unique_nodes),
                "filtered_relationships_count": len(all_filtered_relationships)
            }
        }

        # 生成过滤后的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filtered_filename = f"filtered_{database_name}_{timestamp}.json"
        filtered_filepath = os.path.join(FILTERED_JSON_DIR, filtered_filename)

        # 保存过滤后的数据
        with open(filtered_filepath, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, ensure_ascii=False, indent=2)

        # 这里可以添加实际的知识图谱构建逻辑
        # 例如：调用Neo4j插入数据，或者其他图数据库操作

        return BuildResponse(
            success=True,
            message=f"成功从 {len(json_files_data)} 个JSON文件中过滤并保存了 {len(unique_nodes)} 个实体和 {len(all_filtered_relationships)} 个关系",
            filtered_file_path=filtered_filepath
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="选中实体数据格式错误")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"构建失败: {str(e)}")


@app.get("/api/ontology/prompt/{ontology_id}")
async def get_ontology_prompt(ontology_id: str):
    """
    获取本体库对应的提示词
    """
    try:
        # 这里可以根据实际需求从数据库或配置文件中获取提示词
        # 目前返回一个示例提示词
        prompt = """
请根据以下文档内容，提取其中的实体、关系和属性信息：

1. 实体类型包括：系统、公司、文档部分等
2. 关系类型包括：拥有、包含、部分等
3. 属性包括：描述、权限、页码等

请按照JSON格式返回提取的知识图谱数据。
        """

        return {"prompt": prompt.strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取提示词失败: {str(e)}")


# 添加一个用于测试的健康检查接口
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)