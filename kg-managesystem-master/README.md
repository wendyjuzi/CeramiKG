# 陶瓷材料知识图谱构建与可视化系统前端

基于 Vue 3 + Vite 实现的知识图谱管理平台前端，支持图谱构建、本体管理等功能。

## 目录
- [目录结构](#目录结构)
- [安装指南](#安装指南)
- [使用说明](#使用说明)
- [特别说明](#特别说明)
---

## 目录结构
### 根目录
- `README.md`：项目说明文档
- `package.json`：项目依赖配置
- `vite.config.js`：Vite 构建配置
- `.env`：环境配置文件（可选）

### `src/` - 核心前端代码
- `main.js`：Vue 应用主入口
- `App.vue`：根组件
- `router/`：路由配置
  - `index.js`：Vue Router 路由定义
- `views/pages/`：页面组件
  - `BuildView.vue`：知识图谱构建页面
  - `ManageView.vue`：图谱管理页面
  - `OntologyView.vue`：本体管理页面
- `components/`：公共组件
  - `asideNav.vue`：侧边导航组件
- `assets/`：静态资源
  - `css/global.css`：全局样式文件
- `api/`：接口模块
  - `axios.js`：Axios 请求封装

---

## 安装指南
### 环境要求
- Node.js 16+
- npm/yarn

### 安装步骤
```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 生产环境构建
npm run build
```

---

## 使用说明
1. 启动neo4j数据库
2. 启动后端服务
3. 启动前端服务

## 特别说明
前端各界面有跳过后端直接通过neo4j-driver与neo4j数据库连接部分。初次使用时需在neo4j中创建一个名为ontology的数据库用于存储本体（多数据库可能需要Neo4j Desktop）
