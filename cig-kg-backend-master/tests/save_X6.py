import json
import os
from neo4j import GraphDatabase
from tqdm import tqdm


class Neo4jImporter:
    def __init__(self, uri, user, password, database="test"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def close(self):
        self.driver.close()

    def _create_node(self, tx, node_id, node_type, properties):
        """创建初始节点（不合并）"""
        # 检查 properties 中是否存在键 "实体名"
        if "实体名" in properties:
            # 将 "实体名" 的值赋值给 "name"
            properties["name"] = properties.pop("实体名")
        if "图片路径" in properties:
            properties["path"] = properties.pop("图片路径")

        tx.run(f"""
            CREATE (n:`{node_type}`)
            SET n.id = $node_id,
                n += $properties
        """, node_id=node_id, properties=properties)

    def _create_relationship(self, tx, from_id, to_id, rel_type):
        """创建关系（基于节点ID）"""
        tx.run(f"""
            MATCH (a), (b)
            WHERE a.id = $from_id AND b.id = $to_id
            MERGE (a)-[r:`{rel_type}`]->(b)
        """, from_id=from_id, to_id=to_id)

    def _merge_duplicate_nodes(self, tx):
        """合并相同实体名的节点，取属性的并集"""
        # 1. 为所有节点添加统一标签以便合并
        tx.run("""
            MATCH (n)
            WHERE n.name IS NOT NULL
            SET n:MergeCandidate
        """)

        # 2. 合并相同名称的节点，取属性的并集
        tx.run("""
            MATCH (n:MergeCandidate)
            WITH n.name AS name, COLLECT(n) AS nodes
            WHERE size(nodes) > 1
            CALL apoc.refactor.mergeNodes(nodes, {
                properties: "overwrite",  
                mergeRels: true,          
                mergeRels: true           
            }) YIELD node
            RETURN count(node)
        """)

        # 3. 删除所有节点的 MergeCandidate 标签
        tx.run("""
                MATCH (n:MergeCandidate)
                REMOVE n:MergeCandidate
            """)

    def import_from_json(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        with self.driver.session(database=self.database) as session:
            # 第一阶段：创建所有节点（不合并）
            for node in tqdm(data["nodes"], desc=f"Creating nodes from {os.path.basename(json_path)}"):
                session.execute_write(
                    self._create_node,
                    node["id"],
                    node["type"],
                    node["properties"]
                )

            # 第二阶段：创建关系
            for rel in tqdm(data["relationships"], desc=f"Creating relationships from {os.path.basename(json_path)}"):
                session.execute_write(
                    self._create_relationship,
                    rel["from"],
                    rel["to"],
                    rel["type"]
                )

            # 第三阶段：合并重复节点
            # session.execute_write(self._merge_duplicate_nodes)

    def batch_import_to_neo4j(self, json_dir):

        # 遍历目录中的所有JSON文件
        json_files = [f for f in os.listdir(json_dir) if f.endswith('.json')]

        for json_file in tqdm(json_files, desc="Processing JSON files"):
            json_path = os.path.join(json_dir, json_file)
            self.import_from_json(json_path)

        # 第三阶段：合并重复节点
        with self.driver.session(database=self.database) as session:
            session.execute_write(self._merge_duplicate_nodes)

        self.close()


if __name__ == "__main__":
    # 配置Neo4j连接信息
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "main"

    index = 0
    while index < 4:
        index = index + 1
        # JSON文件目录
        JSON_DIR = f"../kg_output/x6_{index}"
        importer = Neo4jImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)

        # 执行批量导入
        importer.batch_import_to_neo4j(JSON_DIR)
