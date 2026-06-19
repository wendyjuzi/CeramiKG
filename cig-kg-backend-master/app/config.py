import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # MongoDB Mn
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://root:root@localhost:27017")
    MONGO_DB: str = os.getenv("MONGO_DB", "documents")
    MONGO_COLLECTION: str = os.getenv("MONGO_COLLECTION", "documents_json")
    
    # MySQL Mn
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = str(os.getenv("MYSQL_PASSWORD", "root"))
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "document")
    
    # LLM API Mn
    API_KEY: str = os.getenv("API_KEY", "")
    BASE_URL: str = os.getenv("BASE_URL", "https://api.deepseek.com")
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "EMPTY")
    QWEN_API_BASE: str = os.getenv("QWEN_API_BASE", "http://localhost:8000/v1")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "deepseek-chat")

    # App init flags
    INIT_DB_ON_STARTUP: bool = os.getenv("INIT_DB_ON_STARTUP", "false").lower() in ("1", "true", "yes")
    INIT_DB_MARKER: str = os.getenv("INIT_DB_MARKER", ".init_db_done")

    # Knowledge graph / Neo4j configs
    KG_ONLY_MODE: bool = os.getenv("KG_ONLY_MODE", "false").lower() in ("1", "true", "yes")
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")
    EXTRACTED_KG_ROOT: str = os.getenv("EXTRACTED_KG_ROOT", "../relation")
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
