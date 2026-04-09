import json
import os
import re
from typing import Dict, Any, List
from dotenv import load_dotenv
from fastapi import Depends
from openai import OpenAI
from app.dependencies.dependencies import get_neo4j_service
from app.services.neo4j_service import Neo4jService
from app.utils import id_assign, text_split
from app.utils.neo4j_importer import Neo4jImporter


def save_kg_data(index, data: Dict[str, Any], output_dir: str = "kg_output/deepseek"):
    """保存知识图谱数据到文件"""
    os.makedirs(output_dir, exist_ok=True)
    # 格式化索引为3位数字，例如1变成001，12变成012
    formatted_index = f"{index:03d}"
    output_path = os.path.join(output_dir, f"{formatted_index}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path


class KGBuildService:
    def __init__(self, neo4j_service: Neo4jService = Depends(get_neo4j_service)):
        load_dotenv()

        self.model_name = os.getenv("MODEL_NAME", "MODEL_NAME") # autodl-tmp/models/Qwen2.5-7B-Instruct

        self.neo4j_service = neo4j_service
        self.client = OpenAI(
            api_key=os.getenv("API_KEY", "API_KEY"),
            base_url=os.getenv("BASE_URL", "BASE_URL")
        )
        self.conversation_history = []  # 维护对话历史

    def extract_kg_elements(self, text: str, prompt: str) -> Dict[str, Any]:

        """从文本中提取知识图谱元素"""
        system_prompt = """你是一个文档处理专家并擅长构建知识图谱"""
        user_prompt = f"{prompt}\n\n待处理文本：\n{text}"

        # TODO: 启用历史对话的效果不佳
        # 仅保留上轮对话（如果有）
        last_conversation = self.conversation_history[-2:] if self.conversation_history else []
        # 构建包含历史对话的messages
        messages = [
            {"role": "system", "content": system_prompt},
            # *last_conversation,  # 仅注入上轮对话
            {"role": "user", "content": user_prompt}
        ]

        # TODO: 替换为本地部署的qwen模型，可能需要禁用response_format并对输出作json化处理
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            response_format={'type': 'json_object'},
            max_tokens=3000,
        )

        result = json.loads(response.choices[0].message.content)
        # 更新对话历史（仅保留最新一轮）
        self.conversation_history = [
                                        *last_conversation,
                                        {"role": "user", "content": user_prompt},  # 截断保存
                                        {"role": "assistant", "content": json.dumps(result)}
                                    ][-2:]  # 严格限制只保留1轮完整对话

        return result

    # TODO: 按页处理文件，定义一个全局变量页码，将其与每页抽取实体建立指向关系；将抽取结果合并到main中
    def build_graph(self, json_dir: str, file_path: str, prompt: str, database_name: str) -> Dict[str, Any]:
        """构建知识图谱"""
        try:

            chunks = text_split.text_split(file_path=file_path)
            chunks_count = len(chunks)
            self.conversation_history = []  # 新文件处理时重置历史

            page_index = 0  # 全局页码

            # 1. 提取知识图谱元素
            for index, chunk in enumerate(chunks):
                print(f"{index}/{chunks_count}----Processing---")
                print(chunk)
                kg_data = self.extract_kg_elements(text=chunk.page_content, prompt=prompt)
                # TODO:按页分块时启用
                # page_index = page_index + 1
                # new_node = {
                #     "id": "0",
                #     "type": "页码",
                #     "properties": {
                #         "实体名": str(page_index)
                #     }
                # }
                # kg_data["nodes"].append(new_node)  # 将新节点添加到nodes列表中
                #
                # # 为新节点创建指向现有所有节点的关系
                # existing_node_ids = [node["id"] for node in kg_data["nodes"] if node["id"] != "0"]  # 获取现有节点的id，排除新添加的节点
                # new_relationships = [
                #     {
                #         "type": "有实体",
                #         "from": "0",  # 新节点的id
                #         "to": node_id
                #     } for node_id in existing_node_ids
                # ]
                # kg_data["relationships"].extend(new_relationships)  # 将新关系添加到relationships列表中

                # 为每个节点赋予全局唯一ID
                data = id_assign.replace_ids_with_random(kg_data)
                save_kg_data(data=data, index=index, output_dir=json_dir)
                print(f"{index}----Processed")

            # 2. 保存到Neo4j
            importer = Neo4jImporter(database=database_name)
            print(f"saving to {database_name}...")
            importer.batch_import_to_neo4j(json_dir=json_dir)
            # TODO: 同时保存到main中
            # importer.database = 'main'
            # importer.batch_import_to_neo4j(json_dir=json_dir)


            return {
                "success": True,
                # "entity_count": sum(len(v) for v in kg_data["entities"].values()),
                # "relation_count": len(kg_data["relations"])
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
