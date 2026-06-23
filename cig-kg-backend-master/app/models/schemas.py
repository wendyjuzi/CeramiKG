from pydantic import BaseModel, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# 返回给前端的本体节点
class OntologyNode(BaseModel):
    id: int
    name: str
    description: str

# 构建知识图谱请求
class BuildRequest(BaseModel):
    ontology_id: int
    prompt: str
    database_name: str



# 文档模型
class Document(BaseModel):
    id: str
    name: str
    content: Optional[str] = None
    file_path: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @validator('id', pre=True)
    def convert_id_to_string(cls, v):
        """将数字类型的id自动转换为字符串"""
        if isinstance(v, int):
            return str(v)
        return v

# 术语模型
class Term(BaseModel):
    id: int
    name: str
    type: str  # 实体/关系
    description: Optional[str] = None

# 实体位置模型
class EntityPosition(BaseModel):
    start: int
    end: int
    context: Optional[str] = None

# 实体模型
class Entity(BaseModel):
    entity_id: Optional[str] = None  # 实体ID
    entity_name: str  # 实体名称
    type: Optional[str] = None  # 实体类型
    attributes: Optional[Dict[str, Any]] = None  # 属性值
    description: Optional[str] = None  # 描述
    confidence: float = 1.0  # 置信度
    position: Optional[List[EntityPosition]] = None  # 在文档中的位置
    occurrence_count: int = 0  # 出现次数
    
    # 保持向后兼容性
    @property
    def id(self) -> Optional[int]:
        return self.entity_id
    
    @property  
    def name(self) -> str:
        return self.entity_name
    
    @property
    def positions(self) -> Optional[List[EntityPosition]]:
        return self.position

# 关系模型（异常13修复 - 符合新的返回格式要求，异常17修复 - 添加完整字段，异常39修复 - 支持字符串ID格式）
class Relation(BaseModel):
    id: Optional[Union[int, str]] = None  # 序号（异常39修复：支持字符串和整数ID格式）
    relation_id: Optional[str] = None  # 关系ID
    relation_name: str  # 关系名
    head_entity: str  # 头实体名
    tail_entity: str  # 尾实体名
    
    # 异常17新增字段
    confidence: float = 1.0  # 置信度
    description: Optional[str] = None  # 关系描述
    evidence_text: Optional[str] = None  # 证据文本
    
    # 保持向后兼容性（异常36修复：支持字符串和整数ID格式）
    head_entity_id: Optional[Union[int, str]] = None
    head_entity_name: Optional[str] = None 
    tail_entity_id: Optional[Union[int, str]] = None
    tail_entity_name: Optional[str] = None
    
    # 向后兼容的name属性
    @property
    def name(self) -> str:
        return self.relation_name
    
    def __init__(self, **data):
        # 处理新旧字段的兼容性
        if 'name' in data and 'relation_name' not in data:
            data['relation_name'] = data['name']
        if 'head_entity_name' in data and 'head_entity' not in data:
            data['head_entity'] = data['head_entity_name']
        if 'tail_entity_name' in data and 'tail_entity' not in data:
            data['tail_entity'] = data['tail_entity_name']
            
        super().__init__(**data)

# 实体识别请求（异常14修改：添加document_id支持缓存机制）
class EntityExtractionRequest(BaseModel):
    document: Document
    terms: List[Term]
    document_id: Optional[str] = None  # 新增：用于缓存机制的文档ID

# 关系抽取请求（异常13修复 - terms改为可选，异常14添加document_id支持缓存）
class RelationExtractionRequest(BaseModel):
    entities: List[Entity]
    terms: Optional[List[Term]] = None  # 术语为可选，支持无术语的通用关系抽取
    document_content: Optional[str] = None
    document_id: Optional[str] = None  # 新增：用于缓存机制的文档ID

# 实体存储请求（异常14新增）
class EntityStorageRequest(BaseModel):
    document_id: str
    entities: List[Entity]

# 关系存储请求（异常14新增）
class RelationStorageRequest(BaseModel):
    document_id: str
    relations: List[Relation]

# 知识存储请求（异常14修改：添加document_id支持新的缓存机制）
class KnowledgeStorageRequest(BaseModel):
    document_name: str  # 保持向后兼容
    relations: List[Relation]
    document_id: Optional[str] = None  # 新增：用于缓存机制的文档ID

# 新的知识存储请求（异常14新增）
class KnowledgeStorageRequestNew(BaseModel):
    document_id: str
    relations: List[Relation]

class ExtractedKGImportRequest(BaseModel):
    root_path: Optional[str] = None
    limit: Optional[int] = None
    clear_existing: bool = False

# 知识图谱节点
class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    properties: Optional[Dict[str, Any]] = None

# 知识图谱边
class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    relation_type: Optional[str] = None  # 异常25修复：添加relation_type字段用于前端兼容性
    properties: Optional[Dict[str, Any]] = None

# 知识图谱响应
class KnowledgeGraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: Optional[Dict[str, Any]] = None

# 知识图谱选项模型（异常51修复）
class KnowledgeGraphOption(BaseModel):
    document_id: str
    display_name: str
    description: Optional[str] = None
    table_count: Optional[int] = None  # 相关表的数量
    is_legacy: bool = False  # 是否为旧格式

# 通用响应模型
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None

# 文档摘要模型 (用于文档列表)
class DocumentSummary(BaseModel):
    document_id: int
    name: str
    created_at: Optional[datetime] = None
    _id: Optional[str] = None

# 文档详情模型 (用于单个文档)
class DocumentDetail(BaseModel):
    document_id: int
    name: str
    json_data: Optional[List[Dict[str, Any]]] = None
    content: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    _id: Optional[str] = None

# 术语筛选请求
class TermFilterRequest(BaseModel):
    type: Optional[str] = None  # 实体/关系
    search: Optional[str] = None  # 搜索关键字

# 异常41修复：术语管理请求模型
class TermCreateRequest(BaseModel):
    name: str
    type: str  # 实体/关系
    description: Optional[str] = None

class TermUpdateRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None  # 实体/关系
    description: Optional[str] = None

# ==================== 文档治理功能相关模型 ====================

# 文档治理表模型
class DocumentGovernance(BaseModel):
    id: int
    name: str
    file_path: Optional[str] = None  # 文件夹绝对路径
    pdf_path: Optional[str] = None  # PDF文件绝对路径
    status: int = 0  # 0=待审核, 1=已审核, 2=已删除
    upload_time: datetime
    update_time: datetime
    json_file_path: Optional[str] = None
    image_file_path: Optional[str] = None
    upload_user: Optional[str] = None

# 创建文档请求
class DocumentGovernanceCreate(BaseModel):
    name: str
    file_path: Optional[str] = None  # 文件夹绝对路径
    pdf_path: Optional[str] = None  # PDF文件绝对路径
    json_file_path: Optional[str] = None
    image_file_path: Optional[str] = None
    upload_user: Optional[str] = None

# 更新文档请求
class DocumentGovernanceUpdate(BaseModel):
    name: Optional[str] = None
    file_path: Optional[str] = None  # 文件夹绝对路径
    pdf_path: Optional[str] = None  # PDF文件绝对路径
    status: Optional[int] = None
    json_file_path: Optional[str] = None
    image_file_path: Optional[str] = None
    upload_user: Optional[str] = None

# 文档列表响应模型（包含操作按钮）
class DocumentGovernanceListItem(BaseModel):
    id: int  # 序号
    name: str  # 文档名
    file_path: Optional[str] = None  # 文件夹绝对路径
    pdf_path: Optional[str] = None  # PDF文件绝对路径
    status: int  # 状态
    status_text: str  # 状态文本（待审核/已审核/已删除）
    upload_time: datetime  # 上传时间
    update_time: datetime  # 最近更新时间
    upload_user: Optional[str] = None  # 上传用户
    can_review: bool = True  # 是否可以审核
    can_delete: bool = True  # 是否可以删除

# 文档审核请求
class DocumentReviewRequest(BaseModel):
    document_id: int
    json_data: List[Dict[str, Any]]  # 修改后的JSON数据

# 文档审核完成请求
class DocumentReviewCompleteRequest(BaseModel):
    document_id: int
    json_data: List[Dict[str, Any]]  # 最终审核后的JSON数据

# 文档详情（用于审核面板）
class DocumentGovernanceDetail(BaseModel):
    id: int
    name: str
    file_path: Optional[str] = None  # 文件夹绝对路径
    pdf_path: Optional[str] = None  # PDF文件绝对路径
    json_file_path: Optional[str] = None
    image_file_path: Optional[str] = None
    status: int
    upload_time: datetime
    update_time: datetime
    upload_user: Optional[str] = None
    json_data: Optional[List[Dict[str, Any]]] = None  # 从文件系统读取的JSON数据
    image_files: Optional[List[str]] = None  # 从文件系统读取的图片文件列表

# 文档删除请求
class DocumentDeleteRequest(BaseModel):
    document_id: int
    force_delete: bool = False  # 是否强制删除（物理删除）
