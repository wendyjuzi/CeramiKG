import os
import uuid
import logging
import shutil  # 新增：用于移动物理文件
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, or_
from flask_cors import CORS
from datetime import datetime, timedelta  # 需确保导入 timedelta（用于时间偏移）

# --- Elasticsearch 配置（新增）---
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    ConnectionError as ESConnectionError, 
    RequestError, 
    NotFoundError,
    TransportError
)
import hashlib
import csv
import re
import json
from pathlib import Path

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- CORS 配置 ---
cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
cors_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

CORS(app,
    origins=cors_origins,
    expose_headers=["Content-Disposition", "Content-Type"],
    supports_credentials=True)

# --- Elasticsearch 初始化 ---
def init_elasticsearch():
    """初始化 Elasticsearch 客户端，兼容版本不匹配问题"""
    try:
        logger.info("初始化 Elasticsearch 客户端...")
        
        # 创建最基本的 ES 客户端配置，避免版本验证问题
        es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
        es_client = Elasticsearch([es_url])
        
        # 使用 transport 层直接测试连接，绕过高级验证
        result = es_client.transport.perform_request('HEAD', '/')
        logger.info(f"✅ Elasticsearch 连接成功！(Transport 结果: {result})")
        
        # 获取服务器信息（用于日志）
        try:
            server_info = es_client.transport.perform_request('GET', '/')
            if isinstance(server_info, dict) and 'version' in server_info:
                version = server_info['version']['number']
                cluster = server_info.get('cluster_name', 'unknown')
                logger.info(f"ES 服务器: {cluster} - 版本 {version}")
        except Exception as info_e:
            logger.warning(f"获取服务器信息失败: {info_e} (不影响功能)")
        
        return es_client
        
    except Exception as e:
        logger.error(f"❌ Elasticsearch 连接失败: {str(e)}")
        return None

# 初始化 ES 客户端
es_client = init_elasticsearch()

# --- RAG Adapter 初始化 ---
try:
    from rag_adapter import RAGAdapter
    if es_client:
        rag_adapter = RAGAdapter(es_client)
        logger.info("✅ RAG DeepDoc Adapter 初始化成功")
    else:
        rag_adapter = None
        logger.warning("RAGAdapter 未初始化 (依赖 ES)")
except ImportError as e:
    rag_adapter = None
    logger.error(f"❌ RAGAdapter 导入失败: {e}")
except Exception as e:
    rag_adapter = None
    logger.error(f"❌ RAGAdapter 初始化出错: {e}")

# --- 引入 AI 用于问答 ---
from openai import OpenAI
API_KEY = os.getenv("API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen-plus")

def get_llm_client():
    if not API_KEY:
        return None
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def parse_and_index_with_rag(file_path: str, doc_name: str, markdown_text: str | None = None):
    """优先索引 MinerU 产出的 Markdown，缺失时回退 DeepDoc。"""
    if not rag_adapter:
        logger.warning("RAG service not available, skip indexing: %s", doc_name)
        return 0

    if markdown_text and markdown_text.strip():
        return rag_adapter.parse_markdown_and_index(markdown_text, doc_name=doc_name)

    return rag_adapter.parse_and_index(file_path, doc_name=doc_name)

# 暂停以下上传接口的使用，将RAG解析能力整合到主上传接口中
# @app.route('/rag/upload', methods=['POST'])
# def rag_upload():
#     """
#     RAGFlow DeepDoc 上传接口
#     """
#     if not rag_adapter:
#         return jsonify({'error': 'RAG service not available'}), 503
#     if 'file' not in request.files:
#         return jsonify({'error': 'No file part'}), 400
#     file = request.files['file']
#     if file.filename == '':
#         return jsonify({'error': 'No selected file'}), 400
#     filename = file.filename
#     upload_folder = os.getenv('UPLOAD_FOLDER', '/app/uploads')
#     if not os.path.exists(upload_folder):
#         os.makedirs(upload_folder)
#     file_path = os.path.join(upload_folder, filename)
#     file.save(file_path)
#     try:
#         # 使用 DeepDoc 解析
#         count = parse_and_index_with_rag(file_path, doc_name=filename)
#         return jsonify({'message': 'File processed with RAGFlow DeepDoc', 'doc_name': filename, 'chunks_count': count})
#     except Exception as e:
#         logger.error(f"处理文件失败: {e}")
#         return jsonify({'error': str(e)}), 500

@app.route('/rag/ask', methods=['POST'])
def rag_ask():
    if not rag_adapter:
        return jsonify({'error': 'RAG service not available'}), 503
    data = request.json
    question = data.get('question')
    if not question:
        return jsonify({'error': 'Missing question'}), 400
    try:
        chunks = rag_adapter.search(question, top_k=5)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return jsonify({'error': f"Search failed: {e}"}), 500
    llm = get_llm_client()
    if not llm:
        return jsonify({'answer': "LLM not configured. Returning retrieved chunks.", 'chunks': chunks})
    try:
        context = "\n\n".join([f"片段 {i+1} : {c['content'][:500]}" for i, c in enumerate(chunks)])
        system_prompt = f"你是一个智能助手。请基于以下上下文回答用户的问题。如果上下文中没有答案，请如实告知。\n\n上下文:\n{context}"
        response = llm.chat.completions.create(model=MODEL_NAME, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": question}])
        answer = response.choices[0].message.content
        return jsonify({'answer': answer, 'chunks': chunks})
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return jsonify({'error': f"Generation failed: {e}"}), 500

# --- 数据库配置 ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'mysql+pymysql://root:root@localhost/document'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}

# --- 上传配置 ---
UPLOAD_FOLDER = os.path.abspath(os.getenv('UPLOAD_FOLDER', 'uploads'))  # 使用绝对路径更可靠
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'png', 'jpg', 'jpeg'}  # 匹配前端支持的文件类型

# --- MinerU 解析配置（SDK 方式） ---
MINERU_OUTPUT_FOLDER = os.path.abspath(os.getenv('MINERU_OUTPUT_FOLDER', os.path.join(UPLOAD_FOLDER, 'mineru_outputs')))
MINERU_BACKEND = os.getenv('MINERU_BACKEND', 'pipeline')
MINERU_PARSE_METHOD = os.getenv('MINERU_PARSE_METHOD', 'auto')
MINERU_LANG = os.getenv('MINERU_LANG', 'ch')
MINERU_ENABLED = os.getenv('MINERU_ENABLED', 'true').lower() in {'1', 'true', 'yes', 'y'}
MINERU_ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.webp', '.jp2'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

db = SQLAlchemy(app)

# 库类型映射 — 必须在 init_upload_dirs 之前定义
LIBRARY_TYPE_MAP = {
    'maintenance': '维修库',
    'experience': '经验库',
    'operation': '操作库'
}

# --- 初始化函数 ---
def init_upload_dirs():
    """确保上传目录及各库子目录存在"""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    for lib_type in LIBRARY_TYPE_MAP.keys():
        lib_upload_dir = os.path.join(UPLOAD_FOLDER, lib_type)
        os.makedirs(lib_upload_dir, exist_ok=True)
        logger.info(f"初始化上传目录: {lib_upload_dir}")
    os.makedirs(MINERU_OUTPUT_FOLDER, exist_ok=True)
    logger.info(f"初始化 MinerU 输出目录: {MINERU_OUTPUT_FOLDER}")


def init_db_schema():
    """同步数据库模型"""
    with app.app_context():
        db.create_all()
        ensure_document_metadata_columns()
        ensure_task_columns()
        seed_builtin_task_templates()
        logger.info("数据库模型同步完成（新增字段已创建）")


def bootstrap_app():
    """首次请求前初始化资源（兼容 Gunicorn/Docker）"""
    init_upload_dirs()
    init_db_schema()
    if os.getenv("SYNC_CERAMIC_INDEX_ON_STARTUP", "true").lower() in {"1", "true", "yes", "y"}:
        try:
            result = sync_ceramic_paper_index()
            logger.info(f"Ceramic literature index synchronized on startup: {result}")
        except FileNotFoundError as exc:
            logger.warning(f"Ceramic literature metadata not found, startup sync skipped: {exc}")
        except Exception as exc:
            db.session.rollback()
            logger.warning(f"Ceramic literature startup sync skipped: {exc}", exc_info=True)

# --- 数据库模型 ---

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    display_title = db.Column(db.String(1000), nullable=True, comment='真实文献标题')
    original_name = db.Column(db.String(500), nullable=True, comment='原始文件名或DOI文件名')
    doi = db.Column(db.String(255), nullable=True, comment='DOI')
    recovered_doi = db.Column(db.String(255), nullable=True, comment='恢复后的DOI')
    relative_path = db.Column(db.String(1000), nullable=True, comment='相对uploads目录的路径')
    metadata_source = db.Column(db.String(255), nullable=True, comment='元数据来源')
    authors = db.Column(db.Text, nullable=True, comment='作者')
    journal = db.Column(db.String(500), nullable=True, comment='期刊')
    publish_year = db.Column(db.String(50), nullable=True, comment='发表年份')
    abstract = db.Column(db.Text, nullable=True, comment='摘要')
    keywords = db.Column(db.Text, nullable=True, comment='关键词')
    name = db.Column(db.String(255), nullable=False, comment='文档名称')
    file_path = db.Column(db.String(500), nullable=False, comment='文档路径')
    pdf_path = db.Column(db.String(500), nullable=True, comment='PDF文件路径')
    json_file_path = db.Column(db.String(500), nullable=True, comment='JSON文件路径')
    image_file_path = db.Column(db.String(500), nullable=True, comment='图片文件路径')
    status = db.Column(db.Integer, nullable=True, default=0, comment='状态：0-待审核，1-已审核，2-已删除')
    upload_time = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=8), comment='上传时间')
    update_time = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=8), 
                          onupdate=lambda: datetime.utcnow() + timedelta(hours=8), comment='最近更新时间')
    upload_user = db.Column(db.String(255), nullable=True)
    es_code = db.Column(db.String(255), nullable=True, comment='文件量化索引码')
    file_size = db.Column(db.Integer, nullable=True, comment='文件大小(bytes)')
    file_type = db.Column(db.String(255), nullable=True, comment='文件类型: 经验库，维修库，操作库')

    def to_dict(self):
        library_type_map = globals().get('LIBRARY_TYPE_MAP', {})
        repository = next((key for key, value in library_type_map.items() if value == self.file_type), self.file_type)
        return {
            'id': self.id,
            'file_name': self.name,
            'display_title': self.display_title or self.name,
            'original_name': self.original_name,
            'doi': self.doi,
            'recovered_doi': self.recovered_doi,
            'relative_path': self.relative_path,
            'metadata_source': self.metadata_source,
            'authors': self.authors,
            'journal': self.journal,
            'publish_year': self.publish_year,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'upload_time': self.upload_time.isoformat() if self.upload_time else None,
            'es_code': self.es_code,
            'repository': repository
        }


class TaskItem(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False, comment='任务标题')
    description = db.Column(db.Text, nullable=True, comment='任务说明')
    task_type = db.Column(db.String(80), nullable=False, default='other', comment='任务类型')
    status = db.Column(db.String(40), nullable=False, default='pending', comment='任务状态')
    priority = db.Column(db.String(40), nullable=False, default='medium', comment='优先级')
    assignee = db.Column(db.String(255), nullable=True, comment='负责人')
    due_date = db.Column(db.DateTime, nullable=True, comment='截止时间')
    related_document_id = db.Column(db.Integer, nullable=True, comment='关联文献ID')
    project_id = db.Column(db.Integer, nullable=True, comment='关联项目ID')
    template_id = db.Column(db.Integer, nullable=True, comment='关联模板ID')
    created_by = db.Column(db.String(255), nullable=True, comment='创建人')
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=8), comment='创建时间')
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.utcnow() + timedelta(hours=8),
        onupdate=lambda: datetime.utcnow() + timedelta(hours=8),
        comment='更新时间'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'task_type': self.task_type,
            'status': self.status,
            'priority': self.priority,
            'assignee': self.assignee,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'related_document_id': self.related_document_id,
            'project_id': self.project_id,
            'template_id': self.template_id,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TaskTemplate(db.Model):
    __tablename__ = 'task_templates'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False, comment='模板名称')
    code = db.Column(db.String(120), nullable=False, unique=True, comment='模板编码')
    description = db.Column(db.Text, nullable=True, comment='模板说明')
    task_type = db.Column(db.String(80), nullable=False, default='literature', comment='任务类型')
    schema_json = db.Column(db.Text, nullable=False, comment='提取模板配置')
    is_builtin = db.Column(db.Boolean, nullable=False, default=False, comment='是否预置模板')
    created_by = db.Column(db.String(255), nullable=True, comment='创建人')
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=8), comment='创建时间')
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.utcnow() + timedelta(hours=8),
        onupdate=lambda: datetime.utcnow() + timedelta(hours=8),
        comment='更新时间'
    )

    def to_dict(self):
        try:
            schema = json.loads(self.schema_json or '{}')
        except Exception:
            schema = {}
        fields = schema.get('fields') if isinstance(schema, dict) else []
        meta = schema.get('meta') if isinstance(schema, dict) else {}
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'task_type': self.task_type,
            'schema': schema,
            'fields_count': len(fields) if isinstance(fields, list) else 0,
            'version': meta.get('version') if isinstance(meta, dict) else None,
            'tags': meta.get('tags', []) if isinstance(meta, dict) else [],
            'is_builtin': self.is_builtin,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ResearchProject(db.Model):
    __tablename__ = 'research_projects'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False, comment='项目名称')
    description = db.Column(db.Text, nullable=True, comment='项目说明')
    owner = db.Column(db.String(255), nullable=True, comment='负责人')
    status = db.Column(db.String(40), nullable=False, default='active', comment='项目状态')
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=8), comment='创建时间')
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.utcnow() + timedelta(hours=8),
        onupdate=lambda: datetime.utcnow() + timedelta(hours=8),
        comment='更新时间'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'owner': self.owner,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class UserLog(db.Model):
    __tablename__ = 'user_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    actor = db.Column(db.String(255), nullable=True, comment='操作用户')
    action = db.Column(db.String(120), nullable=False, comment='操作类型')
    target_type = db.Column(db.String(80), nullable=True, comment='对象类型')
    target_id = db.Column(db.Integer, nullable=True, comment='对象ID')
    detail = db.Column(db.Text, nullable=True, comment='操作详情')
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=8), comment='创建时间')

    def to_dict(self):
        return {
            'id': self.id,
            'actor': self.actor,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'detail': self.detail,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# --- 辅助函数 ---

# 库类型映射
LIBRARY_TYPE_MAP = {
    'ceramic_papers': '陶瓷文献库'
}


# --- 新增：生成唯一索引码的工具函数 ---


def ensure_document_metadata_columns():
    """Add metadata columns used by the ceramic literature index when an old DB already exists."""
    columns = {
        "display_title": "VARCHAR(1000) NULL COMMENT '真实文献标题'",
        "original_name": "VARCHAR(500) NULL COMMENT '原始文件名或DOI文件名'",
        "doi": "VARCHAR(255) NULL COMMENT 'DOI'",
        "recovered_doi": "VARCHAR(255) NULL COMMENT '恢复后的DOI'",
        "relative_path": "VARCHAR(1000) NULL COMMENT '相对uploads目录的路径'",
        "metadata_source": "VARCHAR(255) NULL COMMENT '元数据来源'",
        "authors": "TEXT NULL COMMENT '作者'",
        "journal": "VARCHAR(500) NULL COMMENT '期刊'",
        "publish_year": "VARCHAR(50) NULL COMMENT '发表年份'",
        "abstract": "MEDIUMTEXT NULL COMMENT '摘要'",
        "keywords": "TEXT NULL COMMENT '关键词'",
    }

    try:
        existing = {
            row[0]
            for row in db.session.execute(text("SHOW COLUMNS FROM documents")).fetchall()
        }
        for column_name, column_def in columns.items():
            if column_name not in existing:
                db.session.execute(text(f"ALTER TABLE documents ADD COLUMN {column_name} {column_def}"))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning(f"Optional document metadata migration skipped: {exc}")


def ensure_task_columns():
    columns = {
        "project_id": "INT NULL COMMENT '关联项目ID'",
        "template_id": "INT NULL COMMENT '关联模板ID'",
        "created_by": "VARCHAR(255) NULL COMMENT '创建人'",
    }

    try:
        existing = {
            row[0]
            for row in db.session.execute(text("SHOW COLUMNS FROM tasks")).fetchall()
        }
        for column_name, column_def in columns.items():
            if column_name not in existing:
                db.session.execute(text(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_def}"))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning(f"Optional task migration skipped: {exc}")


def log_user_action(action, target_type=None, target_id=None, detail=None, actor=None):
    try:
        actor_name = actor or request.headers.get('X-User') or 'admin'
        log = UserLog(
            actor=actor_name,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=json.dumps(detail, ensure_ascii=False) if isinstance(detail, (dict, list)) else detail,
        )
        db.session.add(log)
    except Exception as exc:
        logger.warning(f"Failed to append user log: {exc}")


def seed_builtin_task_templates():
    builtin_templates = [
        {
            'name': '文献元数据提取模板',
            'code': 'builtin_literature_metadata',
            'description': '提取标题、作者、DOI、期刊、年份、摘要和关键词。',
            'task_type': 'literature',
            'schema': {
                'fields': [
                    {'key': 'title', 'label': '标题', 'type': 'text', 'required': True},
                    {'key': 'authors', 'label': '作者', 'type': 'list', 'required': False},
                    {'key': 'doi', 'label': 'DOI', 'type': 'text', 'required': False},
                    {'key': 'journal', 'label': '期刊', 'type': 'text', 'required': False},
                    {'key': 'publish_year', 'label': '年份', 'type': 'text', 'required': False},
                    {'key': 'abstract', 'label': '摘要', 'type': 'textarea', 'required': False},
                    {'key': 'keywords', 'label': '关键词', 'type': 'list', 'required': False},
                ]
            }
        },
        {
            'name': '陶瓷材料性能提取模板',
            'code': 'builtin_ceramic_property',
            'description': '提取材料体系、制备工艺、烧结条件、力学/热学/电学性能。',
            'task_type': 'kg_build',
            'schema': {
                'fields': [
                    {'key': 'material_system', 'label': '材料体系', 'type': 'text', 'required': True},
                    {'key': 'process', 'label': '制备工艺', 'type': 'textarea', 'required': False},
                    {'key': 'sintering_temperature', 'label': '烧结温度', 'type': 'text', 'required': False},
                    {'key': 'properties', 'label': '性能指标', 'type': 'list', 'required': True},
                    {'key': 'application', 'label': '应用场景', 'type': 'text', 'required': False},
                ]
            }
        },
        {
            'name': '证据链与置信度抽取模板',
            'code': 'builtin_evidence_confidence',
            'description': '面向人工审核的证据句、页码、置信度和冲突标记模板。',
            'task_type': 'review',
            'schema': {
                'meta': {
                    'version': '1.0',
                    'tags': ['evidence', 'confidence', 'human-in-the-loop'],
                    'inspiration': 'Human-in-the-loop information extraction and confidence-aware review workflows'
                },
                'fields': [
                    {'key': 'claim', 'label': '抽取结论', 'type': 'textarea', 'required': True},
                    {'key': 'evidence_sentence', 'label': '证据句', 'type': 'textarea', 'required': True},
                    {'key': 'page', 'label': '页码', 'type': 'number', 'required': False},
                    {'key': 'confidence', 'label': '置信度', 'type': 'number', 'required': True, 'min': 0, 'max': 1},
                    {'key': 'conflict_flag', 'label': '冲突标记', 'type': 'boolean', 'required': False},
                    {'key': 'review_note', 'label': '审核备注', 'type': 'textarea', 'required': False},
                ]
            }
        },
        {
            'name': '工艺-结构-性能链路模板',
            'code': 'builtin_process_structure_property_chain',
            'description': '提取陶瓷材料制备工艺、微观结构、性能指标与应用之间的链式关系。',
            'task_type': 'kg_build',
            'schema': {
                'meta': {
                    'version': '1.0',
                    'tags': ['ceramic', 'process-structure-property', 'relation-extraction'],
                    'inspiration': 'Schema-guided relation extraction for scientific knowledge graphs'
                },
                'fields': [
                    {'key': 'material', 'label': '材料/组分', 'type': 'text', 'required': True},
                    {'key': 'preparation_method', 'label': '制备方法', 'type': 'text', 'required': False},
                    {'key': 'process_parameters', 'label': '工艺参数', 'type': 'list', 'required': False},
                    {'key': 'microstructure', 'label': '微观结构', 'type': 'list', 'required': False},
                    {'key': 'property_name', 'label': '性能名称', 'type': 'text', 'required': True},
                    {'key': 'property_value', 'label': '性能数值', 'type': 'text', 'required': True},
                    {'key': 'unit', 'label': '单位', 'type': 'text', 'required': False},
                    {'key': 'application', 'label': '应用场景', 'type': 'text', 'required': False},
                    {'key': 'relation_summary', 'label': '工艺-结构-性能关系摘要', 'type': 'textarea', 'required': True},
                ]
            }
        },
        {
            'name': '自适应追问字段模板',
            'code': 'builtin_adaptive_followup_fields',
            'description': '为缺失字段生成追问项，支撑半自动模板补全和人工复核。',
            'task_type': 'literature',
            'schema': {
                'meta': {
                    'version': '1.0',
                    'tags': ['adaptive', 'missing-field', 'review'],
                    'inspiration': 'Active-learning style annotation: focus reviewers on uncertain or missing fields'
                },
                'fields': [
                    {'key': 'target_field', 'label': '待补字段', 'type': 'text', 'required': True},
                    {'key': 'missing_reason', 'label': '缺失原因', 'type': 'text', 'required': False},
                    {'key': 'followup_question', 'label': '追问问题', 'type': 'textarea', 'required': True},
                    {'key': 'candidate_answer', 'label': '候选答案', 'type': 'textarea', 'required': False},
                    {'key': 'reviewer_decision', 'label': '审核决定', 'type': 'select', 'options': ['accept', 'revise', 'reject'], 'required': True},
                ]
            }
        },
    ]

    try:
        for item in builtin_templates:
            template = TaskTemplate.query.filter_by(code=item['code']).first()
            if template is None:
                template = TaskTemplate(
                    name=item['name'],
                    code=item['code'],
                    description=item['description'],
                    task_type=item['task_type'],
                    schema_json=json.dumps(item['schema'], ensure_ascii=False),
                    is_builtin=True,
                    created_by='system',
                )
                db.session.add(template)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning(f"Builtin task template seeding skipped: {exc}")


def resolve_stored_file_path(stored_path: str) -> str:
    """Resolve absolute paths and paths relative to UPLOAD_FOLDER."""
    if not stored_path:
        return stored_path
    if os.path.isabs(stored_path):
        return stored_path
    normalized = stored_path.replace("\\", "/").lstrip("/")
    upload_name = Path(app.config["UPLOAD_FOLDER"]).name
    if normalized == upload_name or normalized.startswith(f"{upload_name}/"):
        normalized = normalized[len(upload_name):].lstrip("/")
    return os.path.join(app.config["UPLOAD_FOLDER"], normalized)


def make_upload_relative_path(path: str | Path) -> str:
    """Return a slash-normalized path relative to UPLOAD_FOLDER."""
    path_obj = Path(path).resolve()
    upload_root = Path(app.config["UPLOAD_FOLDER"]).resolve()
    return path_obj.relative_to(upload_root).as_posix()


def normalize_lookup_key(value: str | None) -> str:
    return (value or "").replace("\\", "/").strip().lower()


def doi_from_filename(filename: str | None) -> str:
    stem = Path(filename or "").stem.strip()
    if not stem.startswith("10."):
        return ""
    for separator in ("_", "@"):
        if separator in stem:
            prefix, suffix = stem.split(separator, 1)
            return f"{prefix}/{suffix}"
    return stem


def get_effective_doi(row: dict) -> str:
    return (
        (row.get("DOI") or "").strip()
        or (row.get("Recovered_DOI") or "").strip()
        or doi_from_filename(row.get("Name"))
    )


def decode_pdf_literal(value: bytes) -> str:
    """Decode a simple PDF literal string, including UTF-16BE metadata values."""
    if not value:
        return ""
    value = value.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
    try:
        if value.startswith(b"\xfe\xff"):
            return value[2:].decode("utf-16-be", errors="ignore").strip()
        return value.decode("utf-8", errors="ignore").strip() or value.decode("latin1", errors="ignore").strip()
    except Exception:
        return ""


def normalize_extracted_doi(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    value = value.strip().strip('"').strip("'").rstrip(".,;)")
    value = value.replace("\\", "")
    value = value.replace("https://doi.org/", "").replace("http://doi.org/", "")
    value = value.replace("doi.org/", "").replace("DOI:", "").replace("doi:", "")
    return value.lower() if value.lower().startswith("10.") else ""


def extract_pdf_title_and_doi(file_path: Path) -> dict:
    """Best-effort local recovery for PDFs whose CSV metadata has no title."""
    try:
        data = file_path.read_bytes()[: 768 * 1024]
    except Exception as exc:
        logger.debug(f"Failed to read PDF metadata for {file_path}: {exc}")
        return {"title": "", "doi": ""}

    title = ""
    title_match = re.search(rb"/Title\s*\((.*?)\)", data, re.S)
    if title_match:
        title = decode_pdf_literal(title_match.group(1))
        title = re.sub(r"\s+", " ", title).strip()

    doi = ""
    doi_org_match = re.search(rb"doi\.org/(10\.\d{4,9}/[^\s<>\)\"']{3,160})", data, re.I)
    if doi_org_match:
        doi = normalize_extracted_doi(doi_org_match.group(1))
    if not doi:
        doi_match = re.search(rb"(10\.\d{4,9}/[^\s<>\)\"']{3,160})", data, re.I)
        if doi_match:
            doi = normalize_extracted_doi(doi_match.group(1))

    return {"title": title, "doi": doi}


def sync_ceramic_paper_index():
    """Sync every local ceramic PDF; use CSV title when available, otherwise keep a searchable placeholder."""
    library_type = "ceramic_papers"
    library_root = Path(app.config["UPLOAD_FOLDER"]) / library_type
    metadata_path = library_root / "Combined_Final_Metadata_Recovered.csv"

    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {metadata_path}")

    local_files = [
        path for path in library_root.rglob("*")
        if path.is_file() and path.name != metadata_path.name
    ]
    files_by_rel = {
        normalize_lookup_key(path.relative_to(library_root).as_posix()): path
        for path in local_files
    }
    files_by_name = {}
    for path in local_files:
        files_by_name.setdefault(path.name.lower(), []).append(path)

    with metadata_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        metadata_rows = list(csv.DictReader(csv_file))

    rows_by_rel = {}
    rows_by_name = {}
    rows_by_doi = {}
    valid_title_count = 0
    for row in metadata_rows:
        title = (row.get("Title") or "").strip()
        if title:
            valid_title_count += 1

        rel_key = normalize_lookup_key(row.get("FullName"))
        name_key = (row.get("Name") or "").strip().lower()
        doi_key = get_effective_doi(row)

        if rel_key:
            rows_by_rel.setdefault(rel_key, row)
        if name_key:
            rows_by_name.setdefault(name_key, row)
        if doi_key:
            rows_by_doi.setdefault(doi_key, row)

    synced = 0
    matched_with_title = 0
    recovered_from_pdf_metadata = 0
    fallback_without_title = 0
    skipped_missing_file = 0
    duplicate_name_fallback = 0
    seen_paths = set()

    for file_path in local_files:
        relative_path = make_upload_relative_path(file_path)
        if relative_path in seen_paths:
            continue
        seen_paths.add(relative_path)

        rel_under_library = normalize_lookup_key(file_path.relative_to(library_root).as_posix())
        original_name = file_path.name
        doi_key = doi_from_filename(original_name)

        row = (
            rows_by_rel.get(rel_under_library)
            or rows_by_name.get(original_name.lower())
            or (rows_by_doi.get(doi_key) if doi_key else None)
        )

        title = (row.get("Title") or "").strip() if row else ""
        doi = get_effective_doi(row) if row else doi_key
        pdf_metadata = {"title": "", "doi": ""}
        if not title or not doi:
            pdf_metadata = extract_pdf_title_and_doi(file_path)
            title = title or pdf_metadata.get("title", "")
            doi = doi or pdf_metadata.get("doi", "")

        display_name = title or original_name
        if (row and (row.get("Title") or "").strip()):
            matched_with_title += 1
        elif title:
            recovered_from_pdf_metadata += 1
        else:
            fallback_without_title += 1

        es_code = hashlib.md5(relative_path.encode("utf-8")).hexdigest()

        doc = Document.query.filter_by(relative_path=relative_path).first()
        if doc is None:
            doc = Document(
                relative_path=relative_path,
                file_path=relative_path,
                pdf_path=relative_path if file_path.suffix.lower() == ".pdf" else None,
                status=0,
                upload_user="metadata_sync",
            )
            db.session.add(doc)

        doc.name = display_name
        doc.display_title = title or None
        doc.original_name = original_name
        doc.doi = doi
        doc.recovered_doi = (row.get("Recovered_DOI") or "").strip() or None if row else None
        if row and (row.get("Title") or "").strip():
            doc.metadata_source = (row.get("Original_Source") or "").strip() or metadata_path.name
        elif title or doi:
            doc.metadata_source = "pdf_metadata_recovered"
        else:
            doc.metadata_source = "local_pdf_without_valid_title"
        doc.authors = (row.get("Authors") or "").strip() or None if row else None
        doc.journal = (row.get("Journal") or "").strip() or None if row else None
        doc.publish_year = (row.get("Publish_Year") or "").strip() or None if row else None
        doc.abstract = (row.get("Abstract") or "").strip() or None if row else None
        doc.keywords = (row.get("Keywords") or "").strip() or None if row else None
        doc.file_path = relative_path
        doc.pdf_path = relative_path if file_path.suffix.lower() == ".pdf" else None
        doc.file_size = file_path.stat().st_size
        doc.file_type = LIBRARY_TYPE_MAP[library_type]
        doc.es_code = es_code
        doc.update_time = datetime.utcnow() + timedelta(hours=8)
        synced += 1

    db.session.commit()
    return {
        "synced_count": synced,
        "local_file_count": len(local_files),
        "csv_row_count": len(metadata_rows),
        "csv_valid_title_count": valid_title_count,
        "matched_with_title": matched_with_title,
        "recovered_from_pdf_metadata": recovered_from_pdf_metadata,
        "fallback_without_title": fallback_without_title,
        "skipped_missing_file": skipped_missing_file,
        "duplicate_name_fallback": duplicate_name_fallback,
    }


def generate_es_code(file_content: bytes, file_id: str) -> str:
    import hashlib
    try:
        # 1. 计算文件内容+文件ID的MD5哈希（确保唯一性）
        combined_data = file_content + file_id.encode("utf-8")
        md5_hash = hashlib.md5(combined_data).hexdigest()  # 32位哈希值

        # ES 不可用时，退回本地索引码，保证上传不中断
        if es_client is None:
            logger.warning("Elasticsearch 服务不可用，改用本地索引码: %s", md5_hash)
            return md5_hash
        
        # 2. 在 ES 中创建索引（若不存在）
        es_index = "file_es_codes"  # ES 索引名（可自定义）
        
        # 使用 transport 检查索引是否存在，避免高级 API 的兼容性问题
        try:
            es_client.transport.perform_request('HEAD', f'/{es_index}')
            index_exists = True
        except:
            index_exists = False
        
        if not index_exists:
            # 使用 transport 创建索引
            index_config = {
                "mappings": {
                    "properties": {
                        "es_code": {"type": "keyword"},  # 索引码（精确匹配）
                        "file_id": {"type": "keyword"},  # 文件ID
                        "create_time": {"type": "date", "format": "iso8601"}  # 创建时间
                    }
                }
            }
            headers = {'Content-Type': 'application/json'}
            es_client.transport.perform_request(
                'PUT', 
                f'/{es_index}', 
                body=index_config,
                headers=headers
            )
            logger.info(f"ES 索引 {es_index} 创建成功")
        
        # 3. 将索引码写入 ES（绑定文件ID，确保后续可追溯）
        doc_body = {
            "es_code": md5_hash,
            "file_id": file_id,
            "create_time": datetime.utcnow().isoformat() + "Z"  # ES 标准时间格式
        }
        
        # 使用正确的 Content-Type 头
        headers = {'Content-Type': 'application/json'}
        es_client.transport.perform_request(
            'PUT', 
            f'/{es_index}/_doc/{md5_hash}', 
            body=doc_body,
            headers=headers
        )
        logger.info(f"文件 {file_id} 索引码生成成功: {md5_hash}")
        return md5_hash
    
    except (ESConnectionError, RequestError, TransportError, NotFoundError) as e:
        logger.warning(f"ES 操作失败，改用本地索引码: {str(e)}", exc_info=True)
        combined_data = file_content + file_id.encode("utf-8")
        return hashlib.md5(combined_data).hexdigest()
    except Exception as e:
        logger.warning(f"索引码生成异常，改用本地索引码: {str(e)}", exc_info=True)
        combined_data = file_content + file_id.encode("utf-8")
        return hashlib.md5(combined_data).hexdigest()

TASK_STATUS_SET = {'pending', 'in_progress', 'done', 'blocked', 'cancelled'}
TASK_PRIORITY_SET = {'low', 'medium', 'high', 'urgent'}
TASK_TYPE_SET = {'literature', 'kg_build', 'review', 'qa', 'system', 'other'}


def parse_task_datetime(value):
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.strip().replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            try:
                return datetime.strptime(normalized[:10], '%Y-%m-%d')
            except ValueError as exc:
                raise ValueError('Invalid due_date format') from exc
    raise ValueError('Invalid due_date format')


def normalize_task_payload(data, partial=False):
    data = data or {}
    payload = {}

    if not partial or 'title' in data:
        title = (data.get('title') or '').strip()
        if not title:
            raise ValueError('Task title cannot be empty')
        payload['title'] = title

    if 'description' in data:
        payload['description'] = (data.get('description') or '').strip() or None

    if not partial or 'task_type' in data:
        task_type = (data.get('task_type') or 'other').strip()
        if task_type not in TASK_TYPE_SET:
            raise ValueError(f'Invalid task_type: {task_type}')
        payload['task_type'] = task_type

    if not partial or 'status' in data:
        status = (data.get('status') or 'pending').strip()
        if status not in TASK_STATUS_SET:
            raise ValueError(f'Invalid task status: {status}')
        payload['status'] = status

    if not partial or 'priority' in data:
        priority = (data.get('priority') or 'medium').strip()
        if priority not in TASK_PRIORITY_SET:
            raise ValueError(f'Invalid priority: {priority}')
        payload['priority'] = priority

    if 'assignee' in data:
        payload['assignee'] = (data.get('assignee') or '').strip() or None

    if 'due_date' in data:
        payload['due_date'] = parse_task_datetime(data.get('due_date'))

    if 'related_document_id' in data:
        related_document_id = data.get('related_document_id')
        payload['related_document_id'] = int(related_document_id) if related_document_id not in (None, '') else None

    if 'project_id' in data:
        project_id = data.get('project_id')
        payload['project_id'] = int(project_id) if project_id not in (None, '') else None

    if 'template_id' in data:
        template_id = data.get('template_id')
        payload['template_id'] = int(template_id) if template_id not in (None, '') else None

    if 'created_by' in data:
        payload['created_by'] = (data.get('created_by') or '').strip() or None

    return payload


def get_task_with_document(task):
    item = task.to_dict()
    if task.related_document_id:
        doc = Document.query.get(task.related_document_id)
        item['related_document'] = {
            'id': doc.id,
            'title': doc.display_title or doc.name,
            'original_name': doc.original_name,
            'doi': doc.doi or doc.recovered_doi,
        } if doc else None
    else:
        item['related_document'] = None
    if task.project_id:
        project = ResearchProject.query.get(task.project_id)
        item['project'] = project.to_dict() if project else None
    else:
        item['project'] = None
    if task.template_id:
        template = TaskTemplate.query.get(task.template_id)
        item['template'] = {
            'id': template.id,
            'name': template.name,
            'code': template.code,
            'task_type': template.task_type,
        } if template else None
    else:
        item['template'] = None
    return item


def get_model_by_library_type(library_type):
    """根据库类型获取对应的数据库模型 - 现在统一使用Document模型"""
    if library_type in LIBRARY_TYPE_MAP:
        return Document
    return None


def allowed_file(filename):
    """验证文件后缀是否在允许列表内"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_with_mineru(file_path: str, file_id: str) -> tuple[str, str, str | None, str | None]:
    """使用 MinerU 解析文件，返回 (json_file_path, json_content, md_file_path, md_content)。"""
    if not MINERU_ENABLED:
        raise Exception("MinerU 解析已禁用")

    # 延迟导入，避免启动时加载过重依赖
    from mineru.cli.common import do_parse, read_fn

    os.makedirs(MINERU_OUTPUT_FOLDER, exist_ok=True)

    file_bytes = read_fn(file_path)
    do_parse(
        output_dir=MINERU_OUTPUT_FOLDER,
        pdf_file_names=[file_id],
        pdf_bytes_list=[file_bytes],
        p_lang_list=[MINERU_LANG],
        backend=MINERU_BACKEND,
        parse_method=MINERU_PARSE_METHOD,
        formula_enable=True,
        table_enable=True,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
        f_dump_md=True,
        f_dump_middle_json=False,
        f_dump_model_output=False,
        f_dump_orig_pdf=False,
        f_dump_content_list=True,
    )

    if MINERU_BACKEND == "pipeline":
        parse_dir = os.path.join(MINERU_OUTPUT_FOLDER, file_id, MINERU_PARSE_METHOD)
    elif MINERU_BACKEND.startswith("vlm-"):
        parse_dir = os.path.join(MINERU_OUTPUT_FOLDER, file_id, "vlm")
    elif MINERU_BACKEND.startswith("hybrid-"):
        parse_dir = os.path.join(MINERU_OUTPUT_FOLDER, file_id, f"hybrid_{MINERU_PARSE_METHOD}")
    else:
        parse_dir = os.path.join(MINERU_OUTPUT_FOLDER, file_id, MINERU_PARSE_METHOD)

    json_file_path = os.path.join(parse_dir, f"{file_id}_content_list.json")
    if not os.path.exists(json_file_path):
        raise Exception(f"MinerU 输出文件不存在: {json_file_path}")

    with open(json_file_path, "r", encoding="utf-8") as f:
        json_content = f.read()

    md_file_path = os.path.join(parse_dir, f"{file_id}.md")
    if not os.path.exists(md_file_path):
        md_file_path = None
        for name in os.listdir(parse_dir):
            if name.lower().endswith(".md"):
                md_file_path = os.path.join(parse_dir, name)
                break

    md_content = None
    if md_file_path and os.path.exists(md_file_path):
        with open(md_file_path, "r", encoding="utf-8") as f:
            md_content = f.read()

    return json_file_path, json_content, md_file_path, md_content


def save_file(file, library_type):
    """保存文件到本地和数据库（新增索引码生成，失败则整体回滚）"""
    try:
        if not file or file.filename == '':
            return None, 'No file selected'
        if not allowed_file(file.filename):
            allowed_ext_str = ', '.join(ALLOWED_EXTENSIONS)
            return None, f'Only {allowed_ext_str} files are allowed'

        if library_type not in LIBRARY_TYPE_MAP:
            return None, f'Invalid library_type: {library_type}'

        original_filename = file.filename
        file_extension = os.path.splitext(original_filename)[1]  # 保留原始后缀（如.pdf）
        unique_physical_name = f"{uuid.uuid4()}{file_extension}"  # 物理文件名（防重名）

        # 1. 准备存储路径
        library_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], library_type)
        os.makedirs(library_upload_folder, exist_ok=True)
        file_path = os.path.join(library_upload_folder, unique_physical_name)

        # 2. 生成文件唯一ID（先创建ID，用于索引码生成）
        file_id = str(uuid.uuid4())
        file_content = file.read()  # 读取为 bytes 类型
        file.seek(0)  # 重置指针，确保后续 file.save() 能正常保存完整文件

        # -------------------------- 核心修改：生成索引码（失败则终止）--------------------------
        es_code = generate_es_code(file_content, file_id)  # 调用新增的索引码生成函数
        # 若索引码生成失败，会直接抛出异常，不执行后续保存逻辑

        # 3. 获取文件大小
        file_size = len(file_content)  # 优化：直接使用已读取的内容长度

        # 4. 保存物理文件到本地
        file.save(file_path)

        # 5. MinerU 解析（仅支持 PDF/图片），优先使用其 Markdown 结果进行分块
        json_file_path = None
        markdown_content = None
        if MINERU_ENABLED and file_extension.lower() in MINERU_ALLOWED_EXTENSIONS:
            json_file_path, _, _, markdown_content = parse_with_mineru(file_path, file_id)

        parse_and_index_with_rag(file_path, original_filename, markdown_text=markdown_content)

        # 6. 写入数据库（使用新的Document模型）
        pdf_path = file_path if file_extension.lower() == '.pdf' else None
        
        db_file = Document(
            name=original_filename,  # 存储原始文件名（给用户看）
            file_path=file_path,  # 存储物理路径（服务器用）
            pdf_path=pdf_path,    # 明确设置PDF路径（前端预览依赖此字段）
            file_size=file_size,
            es_code=es_code,  # 写入生成的索引码
            file_type=LIBRARY_TYPE_MAP[library_type],  # 设置文件类型（维修库/经验库/操作库）
            status=0,  # 强制上传时状态为待审核
            json_file_path=json_file_path,
        )
        db.session.add(db_file)
        db.session.flush()  # 暂不提交，批量上传统一处理

        logger.info(f"文件保存成功: {original_filename} -> {LIBRARY_TYPE_MAP[library_type]}, 索引码: {es_code}")
        return db_file, None

    # 捕获索引码生成失败/文件保存失败的异常
    except Exception as e:
        # 若已生成物理文件，删除残留
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
            logger.warning(f"删除残留文件: {file_path}")
        if 'file_id' in locals():
            mineru_dir = os.path.join(MINERU_OUTPUT_FOLDER, file_id)
            if os.path.exists(mineru_dir):
                shutil.rmtree(mineru_dir, ignore_errors=True)
                logger.warning(f"删除残留 MinerU 输出: {mineru_dir}")
        db.session.rollback()
        error_msg = f'Failed to save file: {str(e)}'
        logger.error(error_msg, exc_info=True)
        return None, error_msg


# --- 路由 ---

@app.route('/upload/batch', methods=['POST'])
def upload_batch_pdfs():
    """批量上传文件接口"""
    try:
        files = request.files.getlist('files')
        library_type = request.form.get('library_type')
        print(library_type)
        print(files)

        # 参数校验
        if not library_type or library_type not in LIBRARY_TYPE_MAP:
            return jsonify({'status': 'error', 'message': 'Missing or invalid library_type.'}), 400
        if not files:
            return jsonify({'status': 'error', 'message': 'No files provided'}), 400

        success_files = []
        failed_files = []
        
        for file in files:
            saved_file, error = save_file(file, library_type)
            if error:
                failed_files.append({'file_name': file.filename, 'reason': error})
            else:
                success_files.append(saved_file.to_dict())

        # 批量提交（确保要么全部成功，要么全部回滚）
        if success_files:
            db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Upload finished.',
            'data': {
                'success_files': success_files,
                'failed_files': failed_files,
                'success_count': len(success_files),
                'failed_count': len(failed_files)
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"批量上传失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Batch upload failed: {str(e)}'}), 500


@app.route('/files/sync/ceramic-papers', methods=['POST'])
def sync_ceramic_papers():
    """Build/update the ceramic literature index from local PDFs and metadata CSV."""
    try:
        result = sync_ceramic_paper_index()
        return jsonify({
            'status': 'success',
            'message': 'Ceramic literature index synchronized.',
            'data': result
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Ceramic literature sync failed: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Ceramic literature sync failed: {str(e)}'
        }), 500


@app.route('/files', methods=['GET'])
def get_files():
    """获取文件列表（支持搜索、库类型过滤）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search_query = request.args.get('search')
        library_type = request.args.get('library_type')  # 按库类型过滤
        sort = request.args.get('sort', 'id_desc')
        category = request.args.get('category')

        # 构建查询
        query = Document.query

        # 库类型过滤
        if library_type and library_type in LIBRARY_TYPE_MAP:
            query = query.filter(Document.file_type == LIBRARY_TYPE_MAP[library_type])

        if category == 'has_doi':
            query = query.filter(or_(Document.doi.isnot(None), Document.recovered_doi.isnot(None)))
        elif category == 'missing_doi':
            query = query.filter(Document.doi.is_(None), Document.recovered_doi.is_(None))
        elif category == 'pending_review':
            query = query.filter(Document.status == 0)
        elif category == 'reviewed':
            query = query.filter(Document.status == 1)
        elif category == 'metadata_enriched':
            query = query.filter(or_(
                Document.display_title.isnot(None),
                Document.authors.isnot(None),
                Document.journal.isnot(None),
                Document.publish_year.isnot(None)
            ))

        # 搜索过滤（真实标题、原始DOI文件名、DOI或量化索引码）
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(or_(
                Document.name.ilike(search_term),
                Document.display_title.ilike(search_term),
                Document.original_name.ilike(search_term),
                Document.doi.ilike(search_term),
                Document.recovered_doi.ilike(search_term),
                Document.relative_path.ilike(search_term),
                Document.es_code.ilike(search_term)
            ))

        # 排序：同步导入时 upload_time 很接近，默认按 ID 倒序让后导入/后插入的文献靠前
        if sort == 'id_asc':
            query = query.order_by(Document.id.asc())
        elif sort == 'time_desc':
            query = query.order_by(Document.upload_time.desc(), Document.id.desc())
        elif sort == 'time_asc':
            query = query.order_by(Document.upload_time.asc(), Document.id.asc())
        else:
            query = query.order_by(Document.id.desc())

        # 分页处理
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        results = pagination.items

        # 格式化返回数据
        files_list = []
        for doc in results:
            # 通过file_type反向查找repository标识
            repository = None
            for key, value in LIBRARY_TYPE_MAP.items():
                if value == doc.file_type:
                    repository = key
                    break
            
            files_list.append({
                'id': doc.id,
                'file_name': doc.name,
                'display_title': doc.display_title or doc.name,
                'original_name': doc.original_name,
                'doi': doc.doi,
                'recovered_doi': doc.recovered_doi,
                'relative_path': doc.relative_path or doc.file_path,
                'metadata_source': doc.metadata_source,
                'authors': doc.authors,
                'journal': doc.journal,
                'publish_year': doc.publish_year,
                'file_size': doc.file_size,
                'status': doc.status,
                'status_text': get_document_status_text(doc.status if doc.status is not None else 0),
                'upload_time': doc.upload_time.isoformat() if doc.upload_time else None,
                'es_code': doc.es_code,
                'repository': repository
            })

        return jsonify({
            'status': 'success',
            'data': {
                'files': files_list,
                'pagination': {
                    'page': page,
                    'pages': pagination.pages,
                    'per_page': per_page,
                    'total': pagination.total
                }
            }
        }), 200

    except Exception as e:
        logger.error(f"获取文件列表失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Failed to get files: {str(e)}'}), 500


@app.route('/files/stats', methods=['GET'])
def get_file_stats():
    try:
        total = Document.query.count()
        has_doi = Document.query.filter(or_(Document.doi.isnot(None), Document.recovered_doi.isnot(None))).count()
        pending_review = Document.query.filter(Document.status == 0).count()
        reviewed = Document.query.filter(Document.status == 1).count()
        metadata_enriched = Document.query.filter(or_(
            Document.display_title.isnot(None),
            Document.authors.isnot(None),
            Document.journal.isnot(None),
            Document.publish_year.isnot(None)
        )).count()
        total_size = db.session.query(db.func.coalesce(db.func.sum(Document.file_size), 0)).scalar() or 0
        years = db.session.query(Document.publish_year, db.func.count(Document.id)).filter(
            Document.publish_year.isnot(None),
            Document.publish_year != ''
        ).group_by(Document.publish_year).order_by(db.func.count(Document.id).desc()).limit(8).all()
        return jsonify({
            'status': 'success',
            'data': {
                'total': total,
                'has_doi': has_doi,
                'missing_doi': max(total - has_doi, 0),
                'pending_review': pending_review,
                'reviewed': reviewed,
                'metadata_enriched': metadata_enriched,
                'doi_coverage': round(has_doi * 100 / total, 1) if total else 0,
                'metadata_coverage': round(metadata_enriched * 100 / total, 1) if total else 0,
                'total_size': int(total_size),
                'top_years': [{'year': year, 'count': count} for year, count in years],
            }
        }), 200
    except Exception as e:
        logger.error(f"Failed to get file stats: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to get file stats: {str(e)}'}), 500


@app.route('/tasks/stats', methods=['GET'])
def get_task_stats():
    """Get task counts grouped by status and priority."""
    try:
        total = TaskItem.query.count()
        by_status = {status: TaskItem.query.filter_by(status=status).count() for status in TASK_STATUS_SET}
        by_priority = {priority: TaskItem.query.filter_by(priority=priority).count() for priority in TASK_PRIORITY_SET}
        overdue = TaskItem.query.filter(
            TaskItem.due_date.isnot(None),
            TaskItem.due_date < datetime.utcnow() + timedelta(hours=8),
            TaskItem.status.notin_(['done', 'cancelled'])
        ).count()
        return jsonify({
            'status': 'success',
            'data': {
                'total': total,
                'by_status': by_status,
                'by_priority': by_priority,
                'overdue': overdue,
            }
        }), 200
    except Exception as e:
        logger.error(f"Failed to get task stats: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to get task stats: {str(e)}'}), 500


@app.route('/task-templates', methods=['GET'])
def get_task_templates():
    try:
        search_query = request.args.get('search')
        task_type = request.args.get('task_type')
        query = TaskTemplate.query
        if task_type:
            query = query.filter(TaskTemplate.task_type == task_type)
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(or_(
                TaskTemplate.name.ilike(search_term),
                TaskTemplate.code.ilike(search_term),
                TaskTemplate.description.ilike(search_term)
            ))
        templates = query.order_by(TaskTemplate.is_builtin.desc(), TaskTemplate.updated_at.desc()).all()
        return jsonify({'status': 'success', 'data': {'templates': [item.to_dict() for item in templates]}}), 200
    except Exception as e:
        logger.error(f"Failed to get task templates: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to get task templates: {str(e)}'}), 500


@app.route('/task-templates/stats', methods=['GET'])
def get_task_template_stats():
    try:
        templates = TaskTemplate.query.all()
        total = len(templates)
        builtin = sum(1 for item in templates if item.is_builtin)
        custom = total - builtin
        by_type = {}
        fields_total = 0
        for template in templates:
            by_type[template.task_type] = by_type.get(template.task_type, 0) + 1
            fields_total += template.to_dict().get('fields_count', 0)
        return jsonify({
            'status': 'success',
            'data': {
                'total': total,
                'builtin': builtin,
                'custom': custom,
                'fields_total': fields_total,
                'avg_fields': round(fields_total / total, 1) if total else 0,
                'by_type': by_type,
            }
        }), 200
    except Exception as e:
        logger.error(f"Failed to get task template stats: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to get task template stats: {str(e)}'}), 500


def normalize_template_payload(data, partial=False):
    data = data or {}
    payload = {}
    if not partial or 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            raise ValueError('Template name cannot be empty')
        payload['name'] = name
    if not partial or 'code' in data:
        code = (data.get('code') or '').strip()
        if not code:
            raise ValueError('Template code cannot be empty')
        payload['code'] = code
    if 'description' in data:
        payload['description'] = (data.get('description') or '').strip() or None
    if not partial or 'task_type' in data:
        task_type = (data.get('task_type') or 'literature').strip()
        if task_type not in TASK_TYPE_SET:
            raise ValueError(f'Invalid task_type: {task_type}')
        payload['task_type'] = task_type
    if not partial or 'schema' in data:
        schema = data.get('schema')
        if isinstance(schema, str):
            schema = json.loads(schema or '{}')
        if not isinstance(schema, dict):
            raise ValueError('Template schema must be an object')
        payload['schema_json'] = json.dumps(schema, ensure_ascii=False)
    if 'created_by' in data:
        payload['created_by'] = (data.get('created_by') or '').strip() or None
    return payload


@app.route('/task-templates', methods=['POST'])
def create_task_template():
    try:
        payload = normalize_template_payload(request.get_json() or {})
        if TaskTemplate.query.filter_by(code=payload['code']).first():
            return jsonify({'status': 'error', 'message': 'Template code already exists'}), 400
        template = TaskTemplate(**payload, is_builtin=False)
        db.session.add(template)
        db.session.flush()
        log_user_action('create_template', 'task_template', template.id, {'name': template.name})
        db.session.commit()
        return jsonify({'status': 'success', 'data': template.to_dict()}), 201
    except ValueError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create task template: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to create task template: {str(e)}'}), 500


@app.route('/task-templates/<int:template_id>', methods=['PUT'])
def update_task_template(template_id):
    try:
        template = TaskTemplate.query.get(template_id)
        if not template:
            return jsonify({'status': 'error', 'message': 'Template not found'}), 404
        if template.is_builtin:
            return jsonify({'status': 'error', 'message': 'Builtin templates cannot be edited'}), 400
        payload = normalize_template_payload(request.get_json() or {}, partial=True)
        if 'code' in payload:
            exists = TaskTemplate.query.filter(TaskTemplate.code == payload['code'], TaskTemplate.id != template_id).first()
            if exists:
                return jsonify({'status': 'error', 'message': 'Template code already exists'}), 400
        for key, value in payload.items():
            setattr(template, key, value)
        template.updated_at = datetime.utcnow() + timedelta(hours=8)
        log_user_action('update_template', 'task_template', template.id, {'name': template.name})
        db.session.commit()
        return jsonify({'status': 'success', 'data': template.to_dict()}), 200
    except ValueError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to update task template: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to update task template: {str(e)}'}), 500


@app.route('/task-templates/<int:template_id>', methods=['DELETE'])
def delete_task_template(template_id):
    try:
        template = TaskTemplate.query.get(template_id)
        if not template:
            return jsonify({'status': 'error', 'message': 'Template not found'}), 404
        if template.is_builtin:
            return jsonify({'status': 'error', 'message': 'Builtin templates cannot be deleted'}), 400
        log_user_action('delete_template', 'task_template', template.id, {'name': template.name})
        db.session.delete(template)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Template deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to delete task template: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to delete task template: {str(e)}'}), 500


@app.route('/task-templates/<int:template_id>/export', methods=['GET'])
def export_task_template(template_id):
    template = TaskTemplate.query.get(template_id)
    if not template:
        return jsonify({'status': 'error', 'message': 'Template not found'}), 404
    payload = json.dumps(template.to_dict(), ensure_ascii=False, indent=2)
    return Response(
        payload,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename={template.code}.json'}
    )


@app.route('/task-templates/import', methods=['POST'])
def import_task_template():
    try:
        if 'file' in request.files:
            data = json.loads(request.files['file'].read().decode('utf-8-sig'))
        else:
            data = request.get_json() or {}
        if 'schema_json' in data and 'schema' not in data:
            data['schema'] = json.loads(data.get('schema_json') or '{}')
        payload = normalize_template_payload(data)
        existing = TaskTemplate.query.filter_by(code=payload['code']).first()
        if existing:
            suffix = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            payload['code'] = f"{payload['code']}_{suffix}"
        template = TaskTemplate(**payload, is_builtin=False)
        db.session.add(template)
        db.session.flush()
        log_user_action('import_template', 'task_template', template.id, {'name': template.name})
        db.session.commit()
        return jsonify({'status': 'success', 'data': template.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to import task template: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to import task template: {str(e)}'}), 500


@app.route('/tasks', methods=['GET'])
def get_tasks():
    """List tasks with filtering, search and pagination."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search_query = request.args.get('search')
        status = request.args.get('status')
        priority = request.args.get('priority')
        task_type = request.args.get('task_type')
        project_id = request.args.get('project_id', type=int)
        template_id = request.args.get('template_id', type=int)

        query = TaskItem.query
        if status:
            query = query.filter(TaskItem.status == status)
        if priority:
            query = query.filter(TaskItem.priority == priority)
        if task_type:
            query = query.filter(TaskItem.task_type == task_type)
        if project_id:
            query = query.filter(TaskItem.project_id == project_id)
        if template_id:
            query = query.filter(TaskItem.template_id == template_id)
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(or_(
                TaskItem.title.ilike(search_term),
                TaskItem.description.ilike(search_term),
                TaskItem.assignee.ilike(search_term)
            ))

        query = query.order_by(TaskItem.updated_at.desc(), TaskItem.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'status': 'success',
            'data': {
                'tasks': [get_task_with_document(task) for task in pagination.items],
                'pagination': {
                    'page': page,
                    'pages': pagination.pages,
                    'per_page': per_page,
                    'total': pagination.total
                }
            }
        }), 200
    except Exception as e:
        logger.error(f"Failed to get tasks: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to get tasks: {str(e)}'}), 500


@app.route('/tasks', methods=['POST'])
def create_task():
    """Create a task."""
    try:
        payload = normalize_task_payload(request.get_json() or {})
        task = TaskItem(**payload)
        db.session.add(task)
        db.session.flush()
        log_user_action('create_task', 'task', task.id, {'title': task.title})
        if task.project_id:
            log_user_action('project_task_change', 'project', task.project_id, {
                'task_id': task.id,
                'action': 'create_task',
                'title': task.title,
            })
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Task created successfully',
            'data': get_task_with_document(task)
        }), 201
    except ValueError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create task: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to create task: {str(e)}'}), 500


@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """Update a task."""
    try:
        task = TaskItem.query.get(task_id)
        if not task:
            return jsonify({'status': 'error', 'message': 'Task not found'}), 404

        payload = normalize_task_payload(request.get_json() or {}, partial=True)
        for key, value in payload.items():
            setattr(task, key, value)
        task.updated_at = datetime.utcnow() + timedelta(hours=8)
        log_user_action('update_task', 'task', task.id, {'title': task.title})
        if task.project_id:
            log_user_action('project_task_change', 'project', task.project_id, {
                'task_id': task.id,
                'action': 'update_task',
                'title': task.title,
            })
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Task updated successfully',
            'data': get_task_with_document(task)
        }), 200
    except ValueError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to update task: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to update task: {str(e)}'}), 500


@app.route('/tasks/<int:task_id>/status', methods=['PATCH'])
def update_task_status(task_id):
    """Update only task status."""
    try:
        task = TaskItem.query.get(task_id)
        if not task:
            return jsonify({'status': 'error', 'message': 'Task not found'}), 404

        status = (request.get_json() or {}).get('status')
        if status not in TASK_STATUS_SET:
            return jsonify({'status': 'error', 'message': f'Invalid task status: {status}'}), 400

        task.status = status
        task.updated_at = datetime.utcnow() + timedelta(hours=8)
        log_user_action('update_task_status', 'task', task.id, {'status': status})
        if task.project_id:
            log_user_action('project_task_status_change', 'project', task.project_id, {
                'task_id': task.id,
                'status': status,
            })
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Task status updated successfully',
            'data': get_task_with_document(task)
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to update task status: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to update task status: {str(e)}'}), 500


@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task."""
    try:
        task = TaskItem.query.get(task_id)
        if not task:
            return jsonify({'status': 'error', 'message': 'Task not found'}), 404

        project_id = task.project_id
        task_title = task.title
        log_user_action('delete_task', 'task', task.id, {'title': task.title})
        db.session.delete(task)
        if project_id:
            log_user_action('project_task_change', 'project', project_id, {
                'task_id': task_id,
                'action': 'delete_task',
                'title': task_title,
            })
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Task deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to delete task: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to delete task: {str(e)}'}), 500


PROJECT_STATUS_SET = {'active', 'archived', 'paused'}


def normalize_project_payload(data, partial=False):
    data = data or {}
    payload = {}
    if not partial or 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            raise ValueError('Project name cannot be empty')
        payload['name'] = name
    if 'description' in data:
        payload['description'] = (data.get('description') or '').strip() or None
    if 'owner' in data:
        payload['owner'] = (data.get('owner') or '').strip() or None
    if not partial or 'status' in data:
        status = (data.get('status') or 'active').strip()
        if status not in PROJECT_STATUS_SET:
            raise ValueError(f'Invalid project status: {status}')
        payload['status'] = status
    return payload


def get_project_summary(project):
    item = project.to_dict()
    item['task_count'] = TaskItem.query.filter_by(project_id=project.id).count()
    item['document_count'] = db.session.query(TaskItem.related_document_id).filter(
        TaskItem.project_id == project.id,
        TaskItem.related_document_id.isnot(None)
    ).distinct().count()
    item['open_task_count'] = TaskItem.query.filter(
        TaskItem.project_id == project.id,
        TaskItem.status.notin_(['done', 'cancelled'])
    ).count()
    return item


@app.route('/projects', methods=['GET'])
def get_projects():
    try:
        search_query = request.args.get('search')
        status = request.args.get('status')
        query = ResearchProject.query
        if status:
            query = query.filter(ResearchProject.status == status)
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(or_(
                ResearchProject.name.ilike(search_term),
                ResearchProject.description.ilike(search_term),
                ResearchProject.owner.ilike(search_term)
            ))
        projects = query.order_by(ResearchProject.updated_at.desc()).all()
        return jsonify({'status': 'success', 'data': {'projects': [get_project_summary(item) for item in projects]}}), 200
    except Exception as e:
        logger.error(f"Failed to get projects: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to get projects: {str(e)}'}), 500


@app.route('/projects', methods=['POST'])
def create_project():
    try:
        payload = normalize_project_payload(request.get_json() or {})
        project = ResearchProject(**payload)
        db.session.add(project)
        db.session.flush()
        log_user_action('create_project', 'project', project.id, {'name': project.name})
        db.session.commit()
        return jsonify({'status': 'success', 'data': get_project_summary(project)}), 201
    except ValueError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create project: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to create project: {str(e)}'}), 500


@app.route('/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    try:
        project = ResearchProject.query.get(project_id)
        if not project:
            return jsonify({'status': 'error', 'message': 'Project not found'}), 404
        payload = normalize_project_payload(request.get_json() or {}, partial=True)
        for key, value in payload.items():
            setattr(project, key, value)
        project.updated_at = datetime.utcnow() + timedelta(hours=8)
        log_user_action('update_project', 'project', project.id, {'name': project.name})
        db.session.commit()
        return jsonify({'status': 'success', 'data': get_project_summary(project)}), 200
    except ValueError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to update project: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to update project: {str(e)}'}), 500


@app.route('/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    try:
        project = ResearchProject.query.get(project_id)
        if not project:
            return jsonify({'status': 'error', 'message': 'Project not found'}), 404
        TaskItem.query.filter_by(project_id=project.id).update({'project_id': None})
        log_user_action('delete_project', 'project', project.id, {'name': project.name})
        db.session.delete(project)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Project deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to delete project: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to delete project: {str(e)}'}), 500


@app.route('/projects/<int:project_id>/overview', methods=['GET'])
def get_project_overview(project_id):
    try:
        project = ResearchProject.query.get(project_id)
        if not project:
            return jsonify({'status': 'error', 'message': 'Project not found'}), 404
        tasks = TaskItem.query.filter_by(project_id=project.id).order_by(TaskItem.updated_at.desc()).all()
        document_ids = [task.related_document_id for task in tasks if task.related_document_id]
        documents = Document.query.filter(Document.id.in_(document_ids)).all() if document_ids else []
        return jsonify({
            'status': 'success',
            'data': {
                'project': get_project_summary(project),
                'tasks': [get_task_with_document(task) for task in tasks],
                'documents': [doc.to_dict() for doc in documents],
            }
        }), 200
    except Exception as e:
        logger.error(f"Failed to get project overview: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to get project overview: {str(e)}'}), 500


@app.route('/projects/<int:project_id>/upload-task', methods=['POST'])
def upload_project_document_task(project_id):
    try:
        project = ResearchProject.query.get(project_id)
        if not project:
            return jsonify({'status': 'error', 'message': 'Project not found'}), 404
        file = request.files.get('file')
        related_document_id = request.form.get('related_document_id', type=int)

        library_type = request.form.get('library_type') or 'ceramic_papers'
        if file:
            saved_file, error = save_file(file, library_type)
            if error:
                return jsonify({'status': 'error', 'message': error}), 400
        elif related_document_id:
            saved_file = Document.query.get(related_document_id)
            if not saved_file:
                return jsonify({'status': 'error', 'message': 'Related document not found'}), 404
        else:
            return jsonify({'status': 'error', 'message': 'No file or related document provided'}), 400

        task_data = {
            'title': request.form.get('title') or f"处理文献：{saved_file.display_title or saved_file.name}",
            'description': request.form.get('description') or '用户上传文献后自动创建的科研任务',
            'task_type': request.form.get('task_type') or 'literature',
            'status': request.form.get('status') or 'pending',
            'priority': request.form.get('priority') or 'medium',
            'assignee': request.form.get('assignee') or None,
            'due_date': request.form.get('due_date') or None,
            'related_document_id': saved_file.id,
            'project_id': project.id,
            'template_id': request.form.get('template_id') or None,
            'created_by': request.form.get('created_by') or 'user',
        }
        payload = normalize_task_payload(task_data)
        task = TaskItem(**payload)
        db.session.add(task)
        db.session.flush()
        log_user_action('upload_document_create_task', 'task', task.id, {
            'project_id': project.id,
            'document_id': saved_file.id,
            'file_name': saved_file.name,
        })
        log_user_action('project_task_change', 'project', project.id, {
            'task_id': task.id,
            'document_id': saved_file.id,
            'action': 'upload_or_link_document_create_task',
        })
        db.session.commit()
        return jsonify({
            'status': 'success',
            'data': {
                'document': saved_file.to_dict(),
                'task': get_task_with_document(task),
            }
        }), 201
    except ValueError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to upload project document task: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to upload project document task: {str(e)}'}), 500


@app.route('/logs', methods=['GET'])
def get_user_logs():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        action = request.args.get('action')
        target_type = request.args.get('target_type')
        target_id = request.args.get('target_id', type=int)
        query = UserLog.query
        if action:
            query = query.filter(UserLog.action == action)
        if target_type:
            query = query.filter(UserLog.target_type == target_type)
        if target_id is not None:
            query = query.filter(UserLog.target_id == target_id)
        query = query.order_by(UserLog.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            'status': 'success',
            'data': {
                'logs': [item.to_dict() for item in pagination.items],
                'pagination': {
                    'page': page,
                    'pages': pagination.pages,
                    'per_page': per_page,
                    'total': pagination.total,
                }
            }
        }), 200
    except Exception as e:
        logger.error(f"Failed to get logs: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to get logs: {str(e)}'}), 500


def get_document_status_text(status):
    return {0: '待审核', 1: '已审核', 2: '已删除'}.get(status, '未知')


def document_to_governance_item(doc):
    repository = None
    for key, value in LIBRARY_TYPE_MAP.items():
        if value == doc.file_type:
            repository = key
            break

    return {
        'id': doc.id,
        'name': doc.display_title or doc.name,
        'file_path': doc.file_path,
        'pdf_path': doc.pdf_path or doc.file_path,
        'json_file_path': doc.json_file_path,
        'image_file_path': None,
        'status': doc.status if doc.status is not None else 0,
        'status_text': get_document_status_text(doc.status if doc.status is not None else 0),
        'upload_time': doc.upload_time.isoformat() if doc.upload_time else None,
        'update_time': doc.update_time.isoformat() if doc.update_time else None,
        'upload_user': 'admin',
        'can_review': (doc.status if doc.status is not None else 0) != 2,
        'can_delete': (doc.status if doc.status is not None else 0) != 2,
        'repository': repository,
        'file_size': doc.file_size,
        'es_code': doc.es_code,
        'doi': doc.doi or doc.recovered_doi,
        'original_name': doc.original_name,
    }


def load_review_json_data(doc):
    json_path = resolve_stored_file_path(doc.json_file_path) if doc.json_file_path else None
    if json_path and os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, list) else [data]
        except Exception as exc:
            logger.warning(f"Failed to load review JSON for document {doc.id}: {exc}")

    return [{
        'type': 'metadata',
        'content': {
            'title': doc.display_title or doc.name,
            'original_name': doc.original_name,
            'doi': doc.doi or doc.recovered_doi,
            'authors': doc.authors,
            'journal': doc.journal,
            'publish_year': doc.publish_year,
            'abstract': doc.abstract,
            'keywords': doc.keywords,
            'es_code': doc.es_code,
        }
    }]


def save_review_json_data(doc, json_data):
    review_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'review_json')
    os.makedirs(review_dir, exist_ok=True)
    json_path = os.path.join(review_dir, f'document_{doc.id}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    doc.json_file_path = make_upload_relative_path(json_path)


@app.route('/api/document-governance/documents', methods=['GET'])
def governance_get_documents():
    try:
        status = request.args.get('status', type=int)
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        query = Document.query
        if status is not None:
            query = query.filter(Document.status == status)
        query = query.order_by(Document.id.desc()).offset(offset).limit(limit)
        return jsonify([document_to_governance_item(doc) for doc in query.all()]), 200
    except Exception as exc:
        logger.error(f"Failed to get governance documents: {exc}", exc_info=True)
        return jsonify({'detail': '获取文档列表失败'}), 500


@app.route('/api/document-governance/documents/count', methods=['GET'])
def governance_get_documents_count():
    try:
        status = request.args.get('status', type=int)
        query = Document.query
        if status is not None:
            query = query.filter(Document.status == status)
        return jsonify({'total': query.count()}), 200
    except Exception as exc:
        logger.error(f"Failed to count governance documents: {exc}", exc_info=True)
        return jsonify({'detail': '获取文档总数失败'}), 500


@app.route('/api/document-governance/documents/<int:document_id>/review', methods=['GET'])
def governance_get_document_for_review(document_id):
    try:
        doc = Document.query.get(document_id)
        if not doc:
            return jsonify({'detail': '文档不存在'}), 404

        item = document_to_governance_item(doc)
        item['json_data'] = load_review_json_data(doc)
        return jsonify(item), 200
    except Exception as exc:
        logger.error(f"Failed to get document review detail: {exc}", exc_info=True)
        return jsonify({'detail': '获取文档详情失败'}), 500


@app.route('/api/document-governance/documents/<int:document_id>/review/save', methods=['POST'])
def governance_save_review_changes(document_id):
    try:
        doc = Document.query.get(document_id)
        if not doc:
            return jsonify({'success': False, 'message': '文档不存在'}), 404

        payload = request.get_json() or {}
        save_review_json_data(doc, payload.get('json_data') or [])
        doc.update_time = datetime.utcnow() + timedelta(hours=8)
        log_user_action('save_document_review', 'document', doc.id, {'name': doc.name})
        db.session.commit()
        return jsonify({'success': True, 'message': '修改已保存'}), 200
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to save review changes: {exc}", exc_info=True)
        return jsonify({'success': False, 'message': '保存修改失败'}), 500


@app.route('/api/document-governance/documents/<int:document_id>/review/complete', methods=['POST'])
def governance_complete_review(document_id):
    try:
        doc = Document.query.get(document_id)
        if not doc:
            return jsonify({'success': False, 'message': '文档不存在'}), 404

        payload = request.get_json() or {}
        save_review_json_data(doc, payload.get('json_data') or [])
        doc.status = 1
        doc.update_time = datetime.utcnow() + timedelta(hours=8)
        log_user_action('complete_document_review', 'document', doc.id, {'name': doc.name})
        db.session.commit()
        return jsonify({'success': True, 'message': '审核完成'}), 200
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to complete review: {exc}", exc_info=True)
        return jsonify({'success': False, 'message': '审核完成失败'}), 500


@app.route('/api/document-governance/documents/<int:document_id>/review/undo', methods=['POST'])
def governance_undo_review_changes(document_id):
    return jsonify({'success': True, 'message': '撤销成功'}), 200


@app.route('/api/document-governance/documents/<int:document_id>', methods=['DELETE'])
def governance_delete_document(document_id):
    try:
        doc = Document.query.get(document_id)
        if not doc:
            return jsonify({'success': False, 'message': '文档不存在'}), 404

        force_delete = request.args.get('force_delete', 'false').lower() in {'1', 'true', 'yes'}
        if force_delete:
            physical_path = resolve_stored_file_path(doc.file_path)
            if physical_path and os.path.exists(physical_path):
                os.remove(physical_path)
            db.session.delete(doc)
            message = '文档删除成功'
        else:
            doc.status = 2
            doc.update_time = datetime.utcnow() + timedelta(hours=8)
            message = '文档标记为删除'
        log_user_action('delete_document', 'document', document_id, {'force_delete': force_delete})
        db.session.commit()
        return jsonify({'success': True, 'message': message}), 200
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to delete governance document: {exc}", exc_info=True)
        return jsonify({'success': False, 'message': '删除文档失败'}), 500


@app.route('/api/document-governance/files/pdf', methods=['GET'])
def governance_get_pdf_file():
    path = request.args.get('path')
    if not path:
        return jsonify({'detail': 'Missing file path'}), 400

    physical_path = resolve_stored_file_path(path)
    if not physical_path or not os.path.exists(physical_path):
        return jsonify({'detail': 'PDF file not found'}), 404

    response = send_from_directory(
        os.path.dirname(physical_path),
        os.path.basename(physical_path),
        mimetype='application/pdf',
        as_attachment=False,
    )
    response.headers['Content-Disposition'] = f'inline; filename="{os.path.basename(physical_path)}"'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return response


@app.route('/api/document-governance/health', methods=['GET'])
def governance_health_check():
    return jsonify({'status': 'healthy', 'service': 'document-governance'}), 200


@app.route('/files/<library_type>/<file_id>/preview', methods=['GET'])
def preview_file(library_type, file_id):
    """文件预览接口（返回文件流）"""
    if library_type not in LIBRARY_TYPE_MAP:
        return jsonify({'status': 'error', 'message': 'Invalid library type'}), 400

    # 查询文件记录
    file_record = Document.query.filter_by(id=file_id, file_type=LIBRARY_TYPE_MAP[library_type]).first()
    if not file_record:
        return jsonify({'status': 'error', 'message': 'File not found'}), 404

    try:
        # 验证文件是否存在
        physical_path = resolve_stored_file_path(file_record.file_path)
        if not os.path.exists(physical_path):
            return jsonify({'status': 'error', 'message': 'File does not exist on server'}), 404

        # 提取目录和文件名（用于send_from_directory）
        directory = os.path.dirname(physical_path)
        filename = os.path.basename(physical_path)

        # 明确指定PDF的MIME类型，确保浏览器能正确预览而非下载
        mimetype = None
        if filename.lower().endswith('.pdf'):
            mimetype = 'application/pdf'

        # 返回文件流（前端通过iframe预览）
        return send_from_directory(
            directory,
            filename,
            mimetype=mimetype
        )

    except Exception as e:
        logger.error(f"预览文件失败: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Could not access file'}), 500


@app.route('/files/<library_type>/<file_id>/download', methods=['GET'])
def download_file(library_type, file_id):
    """文件下载接口（带中文文件名支持）"""
    if library_type not in LIBRARY_TYPE_MAP:
        return jsonify({'status': 'error', 'message': 'Invalid library type'}), 400

    file_record = Document.query.filter_by(id=file_id, file_type=LIBRARY_TYPE_MAP[library_type]).first()
    if not file_record:
        return jsonify({'status': 'error', 'message': 'File not found'}), 404

    try:
        # 验证文件存在性
        physical_path = resolve_stored_file_path(file_record.file_path)
        if not os.path.exists(physical_path):
            return jsonify({'status': 'error', 'message': 'File does not exist on server'}), 404

        # 提取目录和物理文件名
        directory = os.path.dirname(physical_path)
        physical_filename = os.path.basename(physical_path)

        # 处理中文文件名（RFC 5987编码，避免乱码）
        from urllib.parse import quote
        download_name = file_record.name
        if physical_filename.lower().endswith(".pdf") and not download_name.lower().endswith(".pdf"):
            download_name = f"{download_name}.pdf"
        safe_filename = quote(download_name)  # 对显示文件名编码

        # 构造下载响应
        response = send_from_directory(
            directory,
            physical_filename,
            as_attachment=True,  # 强制下载（而非预览）
            download_name=download_name,  # 显示给用户的文件名
            mimetype=None  # 自动识别文件类型
        )

        # 修复中文文件名下载问题
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{safe_filename}"
        # 跨域相关头
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition, Content-Type'

        logger.info(f"文件下载成功: {file_record.name}")
        return response

    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Could not download file',
            'error': str(e)
        }), 500


@app.route('/files/<library_type>/<file_id>', methods=['PUT'])
def update_file(library_type, file_id):
    """更新文件信息（支持：文件名、量化索引码、所属库迁移）"""
    # 开启数据库事务：确保数据迁移与文件迁移原子性
    db.session.begin_nested()  # 嵌套事务，方便局部回滚
    try:
        # -------------------------- 1. 基础参数验证 --------------------------
        # 获取旧库模型（当前文件所在的库）
        if library_type not in LIBRARY_TYPE_MAP:
            return jsonify({'status': 'error', 'message': f'Invalid old library_type: {library_type}'}), 400

        # 查询旧库中的原文件记录
        old_file = Document.query.filter_by(id=file_id, file_type=LIBRARY_TYPE_MAP[library_type]).first()
        if not old_file:
            return jsonify({'status': 'error', 'message': 'File not found in old library'}), 404

        # 获取前端传入的更新数据（含新文件名、新所属库等）
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No update data provided'}), 400

        # -------------------------- 2. 处理“所属库迁移”（核心新增） --------------------------
        new_library_type = data.get('repository')  # 前端传入的新所属库类型（如"operation"）
        file_moved = False  # 标记文件是否已迁移
        new_file = None     # 存储新库中的文件记录

        # 仅当“新所属库”存在且与“旧所属库”不同时，才执行迁移
        if new_library_type and new_library_type != library_type:
            # 2.1 验证新库类型合法性
            if new_library_type not in LIBRARY_TYPE_MAP:
                raise ValueError(f'Invalid new library_type: {new_library_type}')

            # 2.2 迁移物理文件（本地目录移动）
            # 旧文件路径（如 "uploads/maintenance/xxx.pdf"）
            old_file_path = resolve_stored_file_path(old_file.file_path)
            # 新文件路径（新库目录 + 原物理文件名，如 "uploads/operation/xxx.pdf"）
            new_library_dir = os.path.join(app.config['UPLOAD_FOLDER'], new_library_type)
            os.makedirs(new_library_dir, exist_ok=True)  # 确保新库目录存在
            new_file_name = os.path.basename(old_file_path)  # 保留原物理文件名（避免重名）
            new_file_path = os.path.join(new_library_dir, new_file_name)

            # 移动文件（若目标路径已存在，先删除旧文件避免冲突）
            if os.path.exists(new_file_path):
                os.remove(new_file_path)
            shutil.move(old_file_path, new_file_path)  # 核心：移动物理文件
            file_moved = True
            logger.info(f"物理文件迁移完成: {old_file_path} -> {new_file_path}")

            # 2.3 更新数据库记录
            new_relative_path = make_upload_relative_path(new_file_path)
            old_file.file_path = new_relative_path
            old_file.relative_path = new_relative_path
            old_file.pdf_path = new_relative_path if new_file_name.lower().endswith(".pdf") else None
            old_file.file_type = LIBRARY_TYPE_MAP[new_library_type]
            old_file.update_time = datetime.utcnow() + timedelta(hours=8)
            logger.info(f"数据库记录迁移完成: {file_id} -> {new_library_type}")

        # -------------------------- 3. 处理“文件名修改”（原有逻辑保留） --------------------------
        if 'file_name' in data:
            new_filename = data['file_name'].strip()
            # 验证文件名合法性（非空、无非法字符）
            if not new_filename:
                raise ValueError('File name cannot be empty')
            if any(char in new_filename for char in ['\\', '/', ':', '*', '?', '"', '<', '>']):
                raise ValueError('File name contains invalid characters (\\ / : * ? " < >)')
            
            # 确定要更新的文件记录
            old_file.name = new_filename  # 更新文件名
            old_file.update_time = datetime.utcnow() + timedelta(hours=8)
            logger.info(f"文件名更新完成: {old_file.id} -> {new_filename}")

        # -------------------------- 4. 处理"量化索引码修改"（原有逻辑保留） --------------------------
        if 'es_code' in data:
            es_code = data['es_code'].strip()
            old_file.es_code = es_code
            old_file.update_time = datetime.utcnow() + timedelta(hours=8)
            logger.info(f"量化索引码更新完成: {old_file.id} -> {es_code}")

        # -------------------------- 5. 提交事务（所有操作生效） --------------------------
        db.session.commit()
        logger.info(f"文件信息更新成功: {'迁移至' + new_library_type if new_library_type else '未迁移'}")

        # 构造返回数据（返回更新后的完整信息，含新所属库）
        response_data = old_file.to_dict()

        return jsonify({
            'status': 'success',
            'message': 'File updated successfully (including library migration if needed)',
            'data': response_data
        }), 200

    # -------------------------- 6. 异常处理（回滚所有操作） --------------------------
    except ValueError as ve:
        # 业务逻辑错误（如非法参数）
        db.session.rollback()
        logger.error(f"文件更新业务错误: {str(ve)}")
        return jsonify({'status': 'error', 'message': str(ve)}), 400
    except Exception as e:
        # 系统错误（如文件移动失败、数据库异常）
        db.session.rollback()
        # 若文件已迁移但事务回滚，需删除新路径的文件（避免残留）
        if file_moved and 'new_file_path' in locals() and os.path.exists(new_file_path):
            os.remove(new_file_path)
            logger.warning(f"回滚：删除残留的迁移文件: {new_file_path}")
        logger.error(f"文件更新系统错误: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to update file: {str(e)}'}), 500

@app.route('/files/<library_type>/<file_id>', methods=['DELETE'])
def delete_file(library_type, file_id):
    """删除文件（同时删除数据库记录和本地物理文件）"""
    try:
        if library_type not in LIBRARY_TYPE_MAP:
            return jsonify({'status': 'error', 'message': f'Invalid library_type: {library_type}'}), 400

        file_record = Document.query.filter_by(id=file_id, file_type=LIBRARY_TYPE_MAP[library_type]).first()
        if not file_record:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404

        # 1. 先删除本地物理文件（避免数据库记录删除后文件残留）
        physical_file_path = resolve_stored_file_path(file_record.file_path)
        if os.path.exists(physical_file_path):
            os.remove(physical_file_path)
            logger.info(f"本地物理文件删除成功: {physical_file_path}")
        else:
            logger.warning(f"本地物理文件不存在，跳过删除: {physical_file_path}")

        # 2. 再删除数据库记录
        db.session.delete(file_record)
        db.session.commit()
        logger.info(f"数据库文件记录删除成功: {file_id}（{file_record.name}）")

        return jsonify({'status': 'success', 'message': 'File deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"删除文件失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Failed to delete file: {str(e)}'}), 500


with app.app_context():
    try:
        bootstrap_app()
    except Exception as e:
        logger.warning(f"Bootstrap optional step failed (db might not be ready): {e}")


# --- 应用启动入口（确保最后执行）---
if __name__ == '__main__':
    # 初始化目录和数据库（便于本地直接运行）
    init_upload_dirs()
    init_db_schema()

    # 启动服务（0.0.0.0 允许局域网访问，端口8001与前端配置一致）
    logger.info("=" * 50)
    logger.info("Flask File Management Service 启动成功")
    port = int(os.getenv("PORT", "8001"))
    debug_env = os.getenv("FLASK_DEBUG", "false").lower()
    debug = debug_env in {"1", "true", "yes", "y"}
    logger.info(f"服务地址: http://0.0.0.0:{port}")
    logger.info(f"允许上传文件类型: {', '.join(ALLOWED_EXTENSIONS)}")
    logger.info(f"最大文件大小: {MAX_FILE_SIZE // (1024*1024)} MB")
    logger.info("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=debug)  # 生产环境需关闭debug
