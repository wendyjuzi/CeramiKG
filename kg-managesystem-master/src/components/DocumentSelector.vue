<template>
  <div class="document-selector">
    <div class="selector-header">
      <h3>📄 文档选择</h3>
      <el-switch
        v-model="useJuanyanDb"
        @change="handleDbSourceChange"
        inline-prompt
        active-text="Juanyan"
        inactive-text="默认"
        style="--el-switch-on-color: #13ce66"
      />
    </div>

    <!-- 文档选择下拉框 -->
    <div class="document-select-container">
      <el-select
        v-model="selectedDocument"
        placeholder="请选择要分析的文档"
        @change="handleDocumentChange"
        style="width: 100%"
        :loading="loading"
        clearable
        filterable
      >
        <el-option-group
          v-if="documents.length > 0"
          :label="`共 ${documents.length} 个文档`"
        >
          <el-option
            v-for="doc in documents"
            :key="doc.document_id"
            :label="`${doc.name} (ID: ${doc.document_id})`"
            :value="doc"
          >
            <div class="option-content">
              <span class="doc-name">{{ doc.name }}</span>
              <span class="doc-id">{{ doc.document_id }}</span>
            </div>
          </el-option>
        </el-option-group>
        <el-option v-else disabled label="暂无可用文档" value="" />
      </el-select>
    </div>

    <!-- 文档详情和预览 -->
    <div v-if="selectedDocument" class="document-details">
      <el-card class="document-preview-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="document-title">{{ selectedDocument.name }}</span>
            <el-tag :type="useJuanyanDb ? 'success' : 'info'" size="small">
              {{ useJuanyanDb ? 'Juanyan数据库' : '默认数据库' }}
            </el-tag>
          </div>
        </template>

        <!-- 文档基本信息 -->
        <div class="document-info">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="文档ID">
              <el-tag size="small">{{ selectedDocument.document_id }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ formatDate(selectedDocument.created_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- JSON数据预览 -->
        <div v-if="selectedDocument.json_data" class="json-data-section">
          <h4>📊 结构化数据</h4>
          <el-collapse v-model="activeCollapse">
            <el-collapse-item 
              v-if="selectedDocument.json_data.sections" 
              title="文档章节" 
              name="sections"
            >
              <div class="sections-list">
                <el-tag
                  v-for="(section, index) in selectedDocument.json_data.sections"
                  :key="index"
                  type="primary"
                  style="margin: 4px"
                >
                  {{ section.title }}
                </el-tag>
              </div>
            </el-collapse-item>
            <el-collapse-item 
              v-if="selectedDocument.json_data.keywords" 
              title="关键词" 
              name="keywords"
            >
              <div class="keywords-list">
                <el-tag
                  v-for="keyword in selectedDocument.json_data.keywords"
                  :key="keyword"
                  type="success"
                  style="margin: 4px"
                >
                  {{ keyword }}
                </el-tag>
              </div>
            </el-collapse-item>
            <el-collapse-item 
              v-if="selectedDocument.json_data.metadata" 
              title="元数据" 
              name="metadata"
            >
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item 
                  v-for="(value, key) in selectedDocument.json_data.metadata"
                  :key="key"
                  :label="key"
                >
                  {{ value }}
                </el-descriptions-item>
              </el-descriptions>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 文档内容预览 -->
        <div class="content-preview">
          <h4>📖 内容预览</h4>
          <el-scrollbar max-height="300px">
            <div class="content-text">
              {{ getPreviewContent() }}
            </div>
          </el-scrollbar>
        </div>
      </el-card>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <el-empty description="请选择一个文档开始分析">
        <el-button type="primary" @click="loadDocuments">
          刷新文档列表
        </el-button>
      </el-empty>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { safeExtractDocumentContent, safeJsonParse, setupAxiosInterceptors } from '@/utils/jsonUtils'

export default {
  name: 'DocumentSelector',
  emits: ['document-selected', 'document-changed'],
  setup(props, { emit }) {
    // 响应式数据
    const documents = ref([])
    const selectedDocument = ref(null)
    const loading = ref(false)
    const useJuanyanDb = ref(false)
    const activeCollapse = ref(['sections', 'keywords'])

    // API基础URL
    const API_BASE_URL = '/api/graph'

    // 加载文档列表
    const loadDocuments = async () => {
      loading.value = true
      try {
        const response = await axios.get(`${API_BASE_URL}/documents`, {
          params: {
            use_juanyan: useJuanyanDb.value
          }
        })
        
        if (response.data && Array.isArray(response.data)) {
          documents.value = response.data
          ElMessage.success(`成功加载 ${documents.value.length} 个文档`)
        } else {
          documents.value = []
          ElMessage.warning('文档数据格式异常')
        }
      } catch (error) {
        console.error('加载文档失败:', error)
        ElMessage.error('加载文档失败: ' + (error.response?.data?.detail || error.message))
        documents.value = []
      } finally {
        loading.value = false
      }
    }

    // 处理数据源切换
    const handleDbSourceChange = () => {
      selectedDocument.value = null
      emit('document-changed', null)
      loadDocuments()
    }

    // 处理文档选择
    const handleDocumentChange = async (document) => {
      if (!document) {
        selectedDocument.value = null
        emit('document-changed', null)
        return
      }

      try {
        // 获取文档详情
        const response = await axios.get(
          `${API_BASE_URL}/documents/${document.document_id}`,
          {
            params: {
              use_juanyan: useJuanyanDb.value
            }
          }
        )
        
        if (response.data) {
          selectedDocument.value = response.data
          emit('document-selected', response.data)
          emit('document-changed', response.data)
          ElMessage.success('文档加载成功')
        }
      } catch (error) {
        console.error('获取文档详情失败:', error)
        ElMessage.error('获取文档详情失败: ' + (error.response?.data?.detail || error.message))
      }
    }

    // 格式化日期
    const formatDate = (dateStr) => {
      if (!dateStr) return '未知'
      try {
        return new Date(dateStr).toLocaleString('zh-CN')
      } catch {
        return dateStr
      }
    }

    // 获取预览内容 (异常12修复)
    const getPreviewContent = () => {
      if (!selectedDocument.value) return ''
      
      // 使用安全的内容提取函数
      return safeExtractDocumentContent(selectedDocument.value)
    }

    // 组件挂载时加载文档
    onMounted(() => {
      loadDocuments()
    })

    return {
      documents,
      selectedDocument,
      loading,
      useJuanyanDb,
      activeCollapse,
      loadDocuments,
      handleDbSourceChange,
      handleDocumentChange,
      formatDate,
      getPreviewContent
    }
  }
}
</script>

<style scoped>
.document-selector {
  width: 100%;
}

.selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.selector-header h3 {
  margin: 0;
  color: #409eff;
}

.document-select-container {
  margin-bottom: 20px;
}

.option-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.doc-name {
  font-weight: 500;
  color: #303133;
}

.doc-id {
  font-size: 12px;
  color: #909399;
}

.document-details {
  margin-top: 20px;
}

.document-preview-card {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.document-title {
  font-weight: 600;
  color: #303133;
}

.document-info {
  margin-bottom: 20px;
}

.json-data-section {
  margin-bottom: 20px;
}

.json-data-section h4 {
  margin-bottom: 10px;
  color: #606266;
  font-size: 14px;
}

.sections-list,
.keywords-list {
  line-height: 2;
}

.content-preview h4 {
  margin-bottom: 10px;
  color: #606266;
  font-size: 14px;
}

.content-text {
  padding: 12px;
  background-color: #f8f9fa;
  border-radius: 4px;
  line-height: 1.6;
  color: #606266;
  white-space: pre-wrap;
  word-break: break-word;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
}
</style>