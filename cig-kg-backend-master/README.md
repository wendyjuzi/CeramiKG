# 卷烟知识图谱管理平台后端

基于 FastAPI 实现的知识图谱管理平台后端，支持图谱构建、本体管理与图片查询等功能。

## 目录
- [目录结构](#目录结构)
- [安装指南](#安装指南)
- [使用说明](#使用说明)


---

## 目录结构
### 根目录
- `README.md`：项目说明文档
- `requirements.txt`：Python 依赖列表
- `.env`：环境配置文件，用于连接neo4j数据库与外部大模型

### `app/` - 核心应用代码
- `config.py`：项目配置文件
- `main.py`：FastAPI 主入口文件
- `utils/`：工具类模块
  - `id_assign.py`：ID 分配工具，用于为json中节点分配ID
  - `neo4j_importer.py`：Neo4j 数据导入工具
  - `text_split.py`：文本分割工具
- `services/`：业务服务模块
  - `img_service.py`：图像查询服务
  - `kg_build_service.py`：知识图谱构建服务
  - `neo4j_service.py`：Neo4j 数据库服务
  - `pdf_service.py`：PDF 预处理服务
  - `prompt_service.py`：提示词生成服务
- `routes/`：API 路由模块
  - `build.py`：知识图谱构建相关路由
  - `image.py`：图像查询相关路由
  - `ontology.py`：本体操作相关路由
- `dependencies/`：依赖项
  - `dependencies.py`：FastAPI 依赖注入项，用于提供neo4j_service实例

### `doc_preprocessed` - 存储文档预处理结果的文本部分
- kg_build_service将读取该文件夹下预处理文本进行知识抽取
- 
### `dump` - neo4j数据库备份，用于导入DBMS构建初始数据
- main.dump：全局知识图谱
- ontology.dump：本体管理

### `images` - 存储文档预处理结果的图片部分
- img_service读取该文件下的图片返回给前端展示

### `kg_output/` - 存储大模型知识抽取的输出
- 子目录（如 `x6_1/`, `x6_2/` 等）：每一个上传的pdf文件生成一个子目录，其下包含文本抽取结果，即多个json文件
- json文件：引导大模型输出json格式的纯文本后保存为json文件，json文件中的节点与关系将用于后续知识图谱构建

### `tests/` - 测试相关
- 测试脚本（如 `test.py`）
- HTTP 接口测试文件（如 `test_main.http`）
- 测试数据生成脚本（如 `ds1.py`, `save_X6.py`）

### `uploads/` - 存储上传文件的临时文件夹

---

## 安装指南
### 系统要求
- 需安装 Neo4j Desktop 1.6.1,以进行多数据库切换与APOC插件安装

### 安装步骤
```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务（开发模式）
uvicorn app.main:app --reload
```

---

## 使用说明
1. 配置 Neo4j 数据库连接信息（修改 `.env`）
2. 配置大模型调用接口（修改`.env`，API_KEY为在线大模型api，QWEN_API_KEY为本地大模型，切换时需修改KGBuildService的构造方法）
3. 使用自动化图谱构建功能时，“输入数据库”步骤需输入已经创建的数据库名称
4. Neo4j Desktop启动：断网模式启动或是开启VPN增强模式后启动。先Create Project后点击Add添加DBMS，点击start启动DBMS即可通过Create database创建新数据库（如ontology）。点击相应DBMS可在右侧Plugins部分安装APOC插件
