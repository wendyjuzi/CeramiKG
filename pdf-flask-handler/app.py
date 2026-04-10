import os
import uuid
import logging
import shutil  # 新增：用于移动物理文件
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
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


def parse_and_index_with_rag(file_path: str, doc_name: str):
    """使用 RAGFlow DeepDoc 解析并索引文件"""
    if not rag_adapter:
        raise RuntimeError("RAG service not available")
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
        logger.info("数据库模型同步完成（新增字段已创建）")


def bootstrap_app():
    """首次请求前初始化资源（兼容 Gunicorn/Docker）"""
    init_upload_dirs()
    init_db_schema()

# Manually run bootstrap within app context (since Flask 2.3+ removed before_first_request)
with app.app_context():
    try:
        bootstrap_app()
    except Exception as e:
        logger.warning(f"Bootstrap optional step failed (db might not be ready): {e}")


# --- 数据库模型 ---

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
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
        return {
            'id': self.id,
            'file_name': self.name,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'upload_time': self.upload_time.isoformat() if self.upload_time else None,
            'es_code': self.es_code,
            'repository': self.file_type
        }


# --- 辅助函数 ---

# 库类型映射
LIBRARY_TYPE_MAP = {
    'maintenance': '维修库',
    'experience': '经验库', 
    'operation': '操作库'
}

# --- 新增：生成唯一索引码的工具函数 ---
def generate_es_code(file_content: bytes, file_id: str) -> str:
    import hashlib
    try:
        # 检查 ES 客户端是否可用
        if es_client is None:
            raise Exception("Elasticsearch 服务不可用，无法生成索引码")
        
        # 1. 计算文件内容+文件ID的MD5哈希（确保唯一性）
        combined_data = file_content + file_id.encode("utf-8")
        md5_hash = hashlib.md5(combined_data).hexdigest()  # 32位哈希值
        
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
        logger.error(f"ES 操作失败（索引码生成终止）: {str(e)}", exc_info=True)
        raise  # 抛出异常，让上层判定为上传失败
    except Exception as e:
        logger.error(f"索引码生成异常: {str(e)}", exc_info=True)
        raise

def get_model_by_library_type(library_type):
    """根据库类型获取对应的数据库模型 - 现在统一使用Document模型"""
    if library_type in LIBRARY_TYPE_MAP:
        return Document
    return None


def allowed_file(filename):
    """验证文件后缀是否在允许列表内"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_with_mineru(file_path: str, file_id: str) -> tuple[str, str]:
    """使用 MinerU 解析文件，返回 (json_file_path, json_content)"""
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
        f_dump_md=False,
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

    return json_file_path, json_content


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

        # 5. MinerU 解析（仅支持 PDF/图片）
        json_file_path = None
        if MINERU_ENABLED and file_extension.lower() in MINERU_ALLOWED_EXTENSIONS:
            json_file_path, _ = parse_with_mineru(file_path, file_id)

        parse_and_index_with_rag(file_path, original_filename)

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


@app.route('/files', methods=['GET'])
def get_files():
    """获取文件列表（支持搜索、库类型过滤）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search_query = request.args.get('search')
        library_type = request.args.get('library_type')  # 按库类型过滤

        # 构建查询
        query = Document.query

        # 库类型过滤
        if library_type and library_type in LIBRARY_TYPE_MAP:
            query = query.filter(Document.file_type == LIBRARY_TYPE_MAP[library_type])

        # 搜索过滤（文件名或量化索引码）
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(or_(
                Document.name.ilike(search_term),  # 文件名模糊搜索（不区分大小写）
                Document.es_code.ilike(search_term)  # 量化索引码模糊搜索
            ))

        # 排序（按上传时间倒序）
        query = query.order_by(Document.upload_time.desc())

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
                'file_size': doc.file_size,
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
        if not os.path.exists(file_record.file_path):
            return jsonify({'status': 'error', 'message': 'File does not exist on server'}), 404

        # 提取目录和文件名（用于send_from_directory）
        directory = os.path.dirname(file_record.file_path)
        filename = os.path.basename(file_record.file_path)

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
        if not os.path.exists(file_record.file_path):
            return jsonify({'status': 'error', 'message': 'File does not exist on server'}), 404

        # 提取目录和物理文件名
        directory = os.path.dirname(file_record.file_path)
        physical_filename = os.path.basename(file_record.file_path)

        # 处理中文文件名（RFC 5987编码，避免乱码）
        from urllib.parse import quote
        safe_filename = quote(file_record.name)  # 对原始文件名编码

        # 构造下载响应
        response = send_from_directory(
            directory,
            physical_filename,
            as_attachment=True,  # 强制下载（而非预览）
            download_name=file_record.name,  # 显示给用户的文件名
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
            old_file_path = old_file.file_path
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
            old_file.file_path = new_file_path
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
        physical_file_path = file_record.file_path
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