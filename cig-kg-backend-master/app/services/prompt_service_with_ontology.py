from typing import Dict, List, Any
from app.services.neo4j_service import Neo4jService


class PromptService:
    def __init__(self, neo4j_service: Neo4jService):
        self.neo4j_service = neo4j_service
        self.prompt_template = """
你是一名知识图谱构建助手，请根据用户提供的规范从文本中提取结构化信息。请遵循以下步骤：  

1. 实体与关系定义：  
【实体类型定义】  
{entity_definitions}  

【关系类型定义】  
{relation_definitions}  


2. 处理规则：  
a. 逐句分析文本，识别符合定义的实体及属性，特别注意实体可能被不同 chunk 截断的情况。
b. 根据上下文推断实体间符合定义的关系，确保跨 chunk 的实体关系正确关联。
c. 为每个实体分配唯一数字ID（从1001开始自增），对于跨 chunk 的实体，使用相同的ID。
d. 遇到无法明确判断的情况时保持谨慎，宁可忽略不记录。

3. 输出要求：  
{{  
  "nodes": [  
    {{"id": 1001, "type": "类型1", "properties": {{"属性a":"值","属性b":"值"}}}},  
    ...  
  ],  
  "relationships": [  
    {{"type": "关系X", "from": 1001, "to": 1002}},  
    ...  
  ]  
}}  

4. 特别说明：  
- 输出必须为纯JSON格式，不需要解释文本  
- 确保所有节点ID唯一且关系端点有效  
- 属性值为空时使用null  
- 严格遵循用户定义的实体/关系类型体系  
- 忽略无关的页眉与页脚
- 在抽取实体时，需考虑实体可能被不同 chunk 截断的情况。如果一个实体在当前 chunk 中未完整出现，需结合上一轮 chunk 的信息进行补充和关联，确保实体的完整性。
- 如果实体在上一轮 chunk 中部分出现，且在当前 chunk 中继续出现，需将两部分合并为一个完整的实体，并为合并后的实体分配唯一ID。
- 对于跨 chunk 的实体，优先考虑其在上下文中的连续性和完整性，避免因截断导致信息遗漏或错误。

"""

    async def build_prompt(self, ontology_id: str) -> str:
        """根据本体结构构建提示模板"""
        ontology_structure = await self.get_ontology_structure(ontology_id)

        if "error" in ontology_structure:
            return ontology_structure["error"]

        # 构建实体类型定义部分
        entity_definitions = []
        for entity_name, entity_data in ontology_structure["entities"].items():
            properties = [prop["property_name"] for prop in entity_data["properties"]]
            instances = [inst["instance_name"] for inst in entity_data["instances"]]

            entity_def = f"- 类型名称：[{entity_name}]\n"
            entity_def += f"  属性列表：[{', '.join(properties)}]\n"
            if instances:
                entity_def += f"  示例：[{', '.join(instances) if instances else '无'}]"

            if entity_data.get("definition"):
                entity_def += f"\n  定义：{entity_data['definition']}"
            if entity_data.get("label"):
                entity_def += f"\n  标签：{entity_data['label']}"
            entity_definitions.append(entity_def)

        # 构建关系类型定义部分
        relation_definitions = []
        for relation in ontology_structure["relations"]:
            rel_def = (
                f"- 关系名称：[{relation.get('relation_name', '未命名')}]\n"
                f"  起点类型：[{relation['source_name']}]\n"
                f"  终点类型：[{relation['target_name']}]"
            )
            if relation.get("relation_definition"):
                rel_def += f"\n  定义：{relation['relation_definition']}"
            if relation.get("relation_label"):
                rel_def += f"\n  标签：{relation['relation_label']}"
            relation_definitions.append(rel_def)

        # 替换模板中的占位符
        prompt = self.prompt_template.format(
            entity_definitions="\n".join(entity_definitions),
            relation_definitions="\n".join(relation_definitions)
        )

        return prompt

    async def get_ontology_structure(self, ontology_id: int) -> Dict[str, Any]:
        """根据 ontology_id 查询本体结构"""
        async with await self.neo4j_service.get_session(database_name="ontology") as session:
            # 查询所有 BELONGS_TO 该本体的 Entity 节点
            entity_query = """
            MATCH (e:Entity)-[:BELONGS_TO]->(o:Ontology {id: $ontology_id})
            RETURN e.id AS entity_id, e.name AS entity_name, e.definition as entity_definition, e.label as entity_label
            """
            entities = await session.run(entity_query, ontology_id=ontology_id)
            entity_records = [dict(record) for record in await entities.data()]

            if not entity_records:
                return {"error": "未找到指定本体的实体"}

            result = {
                "entities": {},
                "relations": []
            }

            for entity in entity_records:
                entity_id = entity["entity_id"]
                entity_name = entity["entity_name"]
                entity_definition = entity.get("entity_definition", "")
                entity_label = entity.get("entity_label", "")

                result["entities"][entity_name] = {
                    "definition": entity_definition,
                    "label": entity_label,
                    "properties": [],
                    "instances": [],
                }

                # 查询 Entity 之间的 RELATION 关系
                relation_query = """
                MATCH (e1:Entity {id: $entity_id})-[r:RELATION]->(e2:Entity)
                RETURN e1.name AS source_name, e2.name AS target_name, 
                r.definition AS relation_definition, r.label AS relation_label, r.name AS relation_name
                """
                relations = await session.run(relation_query, entity_id=entity_id)
                result["relations"].extend([dict(record) for record in await relations.data()])

                # 查询 Entity 的 HAS_PROPERTY 关系
                property_query = """
                MATCH (e:Entity {id: $entity_id})-[:HAS_PROPERTY]->(p:Property)
                RETURN p.id AS property_id, p.name AS property_name
                """
                properties = await session.run(property_query, entity_id=entity_id)
                result["entities"][entity_name]["properties"].extend(
                    [dict(record) for record in await properties.data()]
                )

                # 查询 Entity 的 HAS_INSTANCE 关系
                instance_query = """
                MATCH (e:Entity {id: $entity_id})-[:HAS_INSTANCE]->(i:Instance)
                RETURN i.id AS instance_id, i.name AS instance_name
                """
                instances = await session.run(instance_query, entity_id=entity_id)
                result["entities"][entity_name]["instances"].extend(
                    [dict(record) for record in await instances.data()]
                )

            return result

