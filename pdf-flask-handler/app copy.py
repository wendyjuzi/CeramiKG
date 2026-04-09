import os
import uuid
import logging
import shutil  # 新增：用于移动物理文件
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_cors import CORS
from datetime import datetime, timedelta  # 需确保导入 timedelta（用于时间偏移）

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- CORS 配置 ---
CORS(app,
     origins=["http://localhost:5173", "http://localhost:3000"],
     expose_headers=["Content-Disposition", "Content-Type"],
     supports_credentials=True)

# --- 数据库配置 ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root2333@localhost/file_management'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}

# --- 上传配置 ---
UPLOAD_FOLDER = os.path.abspath('uploads')  # 使用绝对路径更可靠
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx','png', 'jpg', 'jpeg'}  # 匹配前端支持的文件类型

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

db = SQLAlchemy(app)


# --- 数据库模型 ---

class BaseFile(db.Model):
    __abstract__ = True
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_name = db.Column(db.String(255), nullable=False, comment='文件名（含后缀）')
    file_path = db.Column(db.String(500), nullable=False, comment='文件物理路径')
    file_size = db.Column(db.Integer, nullable=True, comment='文件大小 (bytes)')  # 解决前端file_size字段报错问题
    upload_time = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=8),
                            comment='上传时间（北京时间）')
    es_code = db.Column(db.String(255), nullable=True, comment='量化索引码')

    def to_dict(self):
        return {
            'id': self.id,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'upload_time': self.upload_time.isoformat() if self.upload_time else None,
            'es_code': self.es_code
        }


class MaintenanceFile(BaseFile):
    __tablename__ = 'maintenance_files'


class ExperienceFile(BaseFile):
    __tablename__ = 'experience_files'


class OperationFile(BaseFile):
    __tablename__ = 'operation_files'


# --- 辅助函数 ---

LIBRARY_MODELS = {
    'maintenance': MaintenanceFile,
    'experience': ExperienceFile,
    'operation': OperationFile
}


def get_model_by_library_type(library_type):
    """根据库类型获取对应的数据库模型"""
    return LIBRARY_MODELS.get(library_type)


def allowed_file(filename):
    """验证文件后缀是否在允许列表内"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_file(file, library_type):
    """保存文件到本地和数据库"""
    try:
        if not file or file.filename == '':
            return None, 'No file selected'
        if not allowed_file(file.filename):
            allowed_ext_str = ', '.join(ALLOWED_EXTENSIONS)
            return None, f'Only {allowed_ext_str} files are allowed'

        model = get_model_by_library_type(library_type)
        if not model:
            return None, f'Invalid library_type: {library_type}'

        original_filename = file.filename
        file_extension = os.path.splitext(original_filename)[1]  # 保留原始后缀（如.pdf）
        unique_filename = f"{uuid.uuid4()}{file_extension}"  # 生成唯一文件名（避免重名）

        # 按库类型分目录存储（如uploads/maintenance/xxx.pdf）
        library_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], library_type)
        os.makedirs(library_upload_folder, exist_ok=True)
        file_path = os.path.join(library_upload_folder, unique_filename)

        # 获取文件大小（bytes）
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # 重置文件指针，确保后续保存完整

        # 保存文件到本地
        file.save(file_path)

        # 写入数据库
        db_file = model(
            file_name=original_filename,  # 存储原始文件名（含后缀）
            file_path=file_path,  # 存储绝对路径（方便后续读取）
            file_size=file_size  # 存储文件大小（解决前端报错）
        )
        db.session.add(db_file)
        db.session.flush()  # 暂不提交，等待批量上传统一提交

        logger.info(f"文件保存成功: {original_filename} -> {library_type} 库, 大小: {file_size} bytes")
        return db_file, None

    except Exception as e:
        logger.error(f"保存文件失败: {str(e)}")
        db.session.rollback()
        return None, f'Failed to save file: {str(e)}'


# --- 路由 ---

@app.route('/upload/batch', methods=['POST'])
def upload_batch_pdfs():
    """批量上传文件接口"""
    try:
        files = request.files.getlist('files')
        library_type = request.form.get('library_type')

        # 参数校验
        if not library_type or library_type not in LIBRARY_MODELS:
            return jsonify({'status': 'error', 'message': 'Missing or invalid library_type.'}), 400
        if not files:
            return jsonify({'status': 'error', 'message': 'No files provided'}), 400

        success_count = 0
        failed_details = []
        for file in files:
            saved_file, error = save_file(file, library_type)
            if error:
                failed_details.append({'filename': file.filename, 'error': error})
            else:
                success_count += 1

        # 批量提交（确保要么全部成功，要么全部回滚）
        if success_count > 0:
            db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Upload finished.',
            'data': {
                'success_count': success_count,
                'failed_count': len(failed_details),
                'failed_details': failed_details
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

        # 确定要查询的模型（全部库或指定库）
        target_models = LIBRARY_MODELS
        if library_type and library_type in LIBRARY_MODELS:
            target_models = {library_type: LIBRARY_MODELS[library_type]}

        # 构建各库的查询语句（统一字段名，方便union）
        queries = []
        for lib_name, model in target_models.items():
            query = db.session.query(
                model.id,
                model.file_name,
                model.file_size,  # 返回file_size（解决前端报错）
                model.upload_time.label('upload_time'),
                model.es_code,
                db.literal(lib_name).label('repository')  # 标记文件所属库
            )

            # 搜索过滤（文件名或量化索引码）
            if search_query:
                search_term = f"%{search_query}%"
                query = query.filter(db.or_(
                    model.file_name.ilike(search_term),  # 文件名模糊搜索（不区分大小写）
                    model.es_code.ilike(search_term)  # 量化索引码模糊搜索
                ))
            queries.append(query)

        # 合并查询结果（union_all 保留所有结果，不去重）
        if not queries:
            return jsonify({
                'status': 'success',
                'data': {
                    'files': [],
                    'pagination': {'page': page, 'pages': 0, 'per_page': per_page, 'total': 0}
                }
            }), 200

        # 合并查询并排序（按上传时间倒序）
        union_query = queries[0].union_all(*queries[1:]) if len(queries) > 1 else queries[0]
        ordered_query = union_query.order_by(db.desc(text('upload_time')))

        # 分页处理
        pagination = ordered_query.paginate(page=page, per_page=per_page, error_out=False)
        results = pagination.items

        # 格式化返回数据
        files_list = [
            {
                'id': r.id,
                'file_name': r.file_name,
                'file_size': r.file_size,
                'upload_time': r.upload_time.isoformat() if r.upload_time else None,
                'es_code': r.es_code,
                'repository': r.repository
            } for r in results
        ]

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
    model = get_model_by_library_type(library_type)
    if not model:
        return jsonify({'status': 'error', 'message': 'Invalid library type'}), 400

    # 查询文件记录
    file_record = model.query.get(file_id)
    if not file_record:
        return jsonify({'status': 'error', 'message': 'File not found'}), 404

    try:
        # 验证文件是否存在
        if not os.path.exists(file_record.file_path):
            return jsonify({'status': 'error', 'message': 'File does not exist on server'}), 404

        # 提取目录和文件名（用于send_from_directory）
        directory = os.path.dirname(file_record.file_path)
        filename = os.path.basename(file_record.file_path)

        # 返回文件流（前端通过iframe预览）
        return send_from_directory(
            directory,
            filename,
            mimetype=None  # 自动识别MIME类型（适配多种文件格式）
        )

    except Exception as e:
        logger.error(f"预览文件失败: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Could not access file'}), 500


@app.route('/files/<library_type>/<file_id>/download', methods=['GET'])
def download_file(library_type, file_id):
    """文件下载接口（带中文文件名支持）"""
    model = get_model_by_library_type(library_type)
    if not model:
        return jsonify({'status': 'error', 'message': 'Invalid library type'}), 400

    file_record = model.query.get(file_id)
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
        safe_filename = quote(file_record.file_name)  # 对原始文件名编码

        # 构造下载响应
        response = send_from_directory(
            directory,
            physical_filename,
            as_attachment=True,  # 强制下载（而非预览）
            download_name=file_record.file_name,  # 显示给用户的文件名
            mimetype=None  # 自动识别文件类型
        )

        # 修复中文文件名下载问题
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{safe_filename}"
        # 跨域相关头
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition, Content-Type'

        logger.info(f"文件下载成功: {file_record.file_name}")
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
        old_model = get_model_by_library_type(library_type)
        if not old_model:
            return jsonify({'status': 'error', 'message': f'Invalid old library_type: {library_type}'}), 400

        # 查询旧库中的原文件记录
        old_file = old_model.query.get(file_id)
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
            new_model = get_model_by_library_type(new_library_type)
            if not new_model:
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

            # 2.3 迁移数据库记录（跨表复制）
            # 创建新库表的记录（复制原记录的核心字段，ID重新生成）
            new_file = new_model(
                file_name=old_file.file_name,    # 保留原文件名（后续可单独修改）
                file_path=new_file_path,         # 更新为新文件路径
                file_size=old_file.file_size,    # 保留原文件大小
                upload_time=old_file.upload_time,# 保留原上传时间
                es_code=old_file.es_code         # 保留原量化索引码
            )
            db.session.add(new_file)  # 新增到新库表
            db.session.delete(old_file)  # 删除旧库表的原记录
            logger.info(f"数据库记录迁移完成: {old_model.__tablename__}.{file_id} -> {new_model.__tablename__}.{new_file.id}")

        # -------------------------- 3. 处理“文件名修改”（原有逻辑保留） --------------------------
        if 'file_name' in data:
            new_filename = data['file_name'].strip()
            # 验证文件名合法性（非空、无非法字符）
            if not new_filename:
                raise ValueError('File name cannot be empty')
            if any(char in new_filename for char in ['\\', '/', ':', '*', '?', '"', '<', '>']):
                raise ValueError('File name contains invalid characters (\\ / : * ? " < >)')
            
            # 确定要更新的文件记录（迁移后用新记录，未迁移用旧记录）
            target_file = new_file if new_file else old_file
            target_file.file_name = new_filename  # 更新文件名
            logger.info(f"文件名更新完成: {target_file.id} -> {new_filename}")

        # -------------------------- 4. 处理“量化索引码修改”（原有逻辑保留） --------------------------
        if 'es_code' in data:
            es_code = data['es_code'].strip()
            target_file = new_file if new_file else old_file
            target_file.es_code = es_code
            logger.info(f"量化索引码更新完成: {target_file.id} -> {es_code}")

        # -------------------------- 5. 提交事务（所有操作生效） --------------------------
        db.session.commit()
        logger.info(f"文件信息更新成功: {'迁移至' + new_library_type if new_library_type else '未迁移'}")

        # 构造返回数据（返回更新后的完整信息，含新所属库）
        result_file = new_file if new_file else old_file
        response_data = result_file.to_dict()
        response_data['repository'] = new_library_type if new_library_type else library_type

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
        model = get_model_by_library_type(library_type)
        if not model:
            return jsonify({'status': 'error', 'message': f'Invalid library_type: {library_type}'}), 400

        file_record = model.query.get(file_id)
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
        logger.info(f"数据库文件记录删除成功: {file_id}（{file_record.file_name}）")

        return jsonify({'status': 'success', 'message': 'File deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"删除文件失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Failed to delete file: {str(e)}'}), 500


# --- 应用启动入口（确保最后执行）---
if __name__ == '__main__':
    # 1. 确保上传目录及各库子目录存在（避免首次上传时报错）
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    for lib_type in LIBRARY_MODELS.keys():
        lib_upload_dir = os.path.join(UPLOAD_FOLDER, lib_type)
        os.makedirs(lib_upload_dir, exist_ok=True)
        logger.info(f"初始化上传目录: {lib_upload_dir}")

    # 2. 同步数据库模型（创建新增字段或表，需确保数据库连接正常）
    with app.app_context():
        # 注意：如果是首次运行或模型有变更，会自动创建/更新表结构
        # 生产环境建议使用迁移工具（如Flask-Migrate），避免直接drop_all()
        db.create_all()
        logger.info("数据库模型同步完成（新增字段已创建）")

    # 3. 启动服务（0.0.0.0 允许局域网访问，端口8001与前端配置一致）
    logger.info("=" * 50)
    logger.info("Flask File Management Service 启动成功")
    logger.info(f"服务地址: http://0.0.0.0:8001")
    logger.info(f"允许上传文件类型: {', '.join(ALLOWED_EXTENSIONS)}")
    logger.info(f"最大文件大小: {MAX_FILE_SIZE // (1024*1024)} MB")
    logger.info("=" * 50)
    app.run(host='0.0.0.0', port=8001, debug=True)  # 生产环境需关闭debug