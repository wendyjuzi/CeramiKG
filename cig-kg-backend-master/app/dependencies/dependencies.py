from app.services.mongo_service import MongoService
from app.services.mongo_service_extended import MongoServiceExtended
from app.services.mysql_service import MySQLService
from app.services.prompt_service import PromptService
# 新增：导入 Neo4j 服务
from app.services.neo4j_service import Neo4jService

# 全局服务实例
mongo_service = MongoService()
mongo_service_extended = MongoServiceExtended()
mysql_service = MySQLService()
prompt_service = PromptService()
# 新增：实例化 Neo4j 服务
neo4j_service = Neo4jService()

async def get_mongo_service():
    if mongo_service.client is None:
        await mongo_service.initialize()
    return mongo_service

async def get_mongo_service_extended():
    if mongo_service_extended.client is None:
        await mongo_service_extended.initialize()
    return mongo_service_extended

async def get_mysql_service():
    if not mysql_service.pool:
        await mysql_service.initialize()
    return mysql_service

async def get_prompt_service():
    return prompt_service

# 新增：Neo4j 服务获取函数
async def get_neo4j_service():
    if neo4j_service.driver is None:
        await neo4j_service.initialize()
    return neo4j_service
