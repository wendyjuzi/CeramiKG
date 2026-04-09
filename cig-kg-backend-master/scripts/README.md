# 数据库初始化脚本

## 概述

本目录包含用于初始化项目数据库的脚本，用于创建必要的表结构并插入示例数据。

## 使用方法

### 1. 环境准备

确保已安装项目依赖：
```bash
pip install -r requirements.txt
```

确保数据库服务正在运行：
- MySQL服务 (端口3306)
- MongoDB服务 (端口27017)

### 2. 配置数据库连接

检查 `.env` 文件中的数据库配置：

```bash
# MongoDB 配置
MONGO_URI=mongodb://localhost:27017
MONGO_DB=cigarette_kg
MONGO_COLLECTION=documents

# MySQL 配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=admin123
MYSQL_DATABASE=documents
```

### 3. 运行初始化脚本

```bash
cd cig-kg-backend-master
python scripts/init_db.py
```

## 脚本功能

### MySQL初始化 (`init_mysql_data`)

1. **创建terms表**
   - 自动创建术语库表结构
   - 包含索引优化

2. **插入示例术语数据**
   - 实体类型：设备、原料、工艺、质量指标、人员、时间、地点、数据
   - 关系类型：包含、使用、生产、控制、影响、属于、位于、负责、检测、配备

### MongoDB初始化 (`init_mongodb_data`)

1. **插入示例文档数据**
   - 卷烟生产工艺流程说明
   - 设备维护手册  
   - 质量检测标准

2. **文档结构**
   ```json
   {
     "document_id": "doc_001",
     "name": "文档名称",
     "content": "文档内容（JSON格式）",
     "json_data": {
       "sections": [...],
       "keywords": [...],
       "metadata": {...}
     },
     "file_path": "/docs/xxx.pdf",
     "created_at": "2024-01-01T00:00:00"
   }
   ```

## 验证初始化结果

### 检查MySQL数据
```sql
-- 查看术语表
SELECT * FROM terms;

-- 查看表结构
DESCRIBE terms;
```

### 检查MongoDB数据
```javascript
// MongoDB shell
use cigarette_kg
db.documents.find().pretty()
db.documents.count()
```

### 通过API验证
启动服务后访问：
- `GET /api/graph/terms` - 获取术语列表
- `GET /api/graph/documents` - 获取文档列表

## 故障排除

### 常见问题

1. **连接失败**
   - 检查数据库服务是否启动
   - 验证连接配置信息
   - 确认防火墙设置

2. **权限错误**  
   - 确保MySQL用户有创建表的权限
   - 检查MongoDB访问权限

3. **数据重复**
   - 脚本会跳过已存在的数据
   - 如需重新初始化，先清空相关表/集合

### 清理数据
```sql
-- MySQL
DROP TABLE IF EXISTS terms;

-- MongoDB
db.documents.deleteMany({})
```

## 开发说明

### 添加新的初始化数据

编辑 `init_db.py` 文件中的数据数组：
- `terms_data`: 添加新的术语
- `documents_data`: 添加新的示例文档

### 扩展功能

可以在脚本中添加其他初始化任务：
- 创建索引
- 设置用户权限
- 导入大批量数据
- 数据验证检查

## 相关文件

- `init_db.py` - 主初始化脚本
- `../app/services/mysql_service.py` - MySQL服务类
- `../app/services/mongo_service.py` - MongoDB服务类
- `../.env` - 数据库配置文件