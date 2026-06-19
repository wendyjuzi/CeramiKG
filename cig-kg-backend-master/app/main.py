from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routes import  graph_2, document_governance
from app.dependencies.dependencies import mongo_service_extended, mysql_service
from app.config import settings
from pathlib import Path
import importlib.util
import os
import sys

app = FastAPI(title="Knowledge Graph Builder API")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174", 
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含路由
# app.include_router(ontology.router, prefix="/api/ontology", tags=["Ontology"])
# app.include_router(build.router, prefix="/api/build", tags=["Build"])
# app.include_router(entitiy.router, prefix="/api/entities", tags=["Entities"])
# app.include_router(graph.router, prefix="/api/graph", tags=["Graph Construction"])

app.include_router(graph_2.router, prefix="/api/graph", tags=["Graph Construction"])
app.include_router(document_governance.router, tags=["Document Governance"])


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库连接"""
    try:
        if os.getenv("KG_ONLY_MODE", "false").lower() in ("1", "true", "yes"):
            print("KG_ONLY_MODE enabled: skipping MongoDB/MySQL startup initialization")
            return

        await mongo_service_extended.initialize()
        await mysql_service.initialize()
        await _run_first_time_init()
        print("Database connections initialized successfully")
    except Exception as e:
        print(f"Failed to initialize databases: {e}")
        raise


async def _run_first_time_init():
    """首次启动时初始化数据库数据（可通过环境变量控制）"""
    if not settings.INIT_DB_ON_STARTUP:
        return

    project_root = Path(__file__).resolve().parent.parent
    marker_path = project_root / settings.INIT_DB_MARKER

    if marker_path.exists():
        return

    def _load_module_from_path(module_name: str, file_path: Path):
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module {module_name} from {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    init_db_module = _load_module_from_path(
        "scripts.init_db",
        project_root / "scripts" / "init_db.py",
    )
    init_db_main = init_db_module.main
    await init_db_main()
    marker_path.write_text("initialized", encoding="utf-8")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时关闭数据库连接"""
    try:
        await mongo_service_extended.close()
        await mysql_service.close()
        # await neo4j_service.close()
        print("Database connections closed successfully")
    except Exception as e:
        print(f"Error closing databases: {e}")




