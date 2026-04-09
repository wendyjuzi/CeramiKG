<template>
  <div class="document-governance">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>文档治理</h1>
      <p>管理和审核文档信息，维护知识图谱数据质量</p>
    </div>

    <!-- 上半区域：文档信息列表 -->
    <div class="document-list-section">
      <el-card class="list-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>文档信息列表</span>
            <div class="header-actions">
              <!-- 状态筛选 -->
              <el-select
                v-model="statusFilter"
                placeholder="状态筛选"
                @change="loadDocuments"
                clearable
                style="width: 120px; margin-right: 10px;"
              >
                <el-option label="待审核" :value="0" />
                <el-option label="已审核" :value="1" />
                <el-option label="已删除" :value="2" />
              </el-select>
              
              <!-- 刷新按钮 -->
              <el-button 
                type="primary" 
                :icon="Refresh" 
                @click="refreshDocuments"
                :loading="loading"
              >
                刷新
              </el-button>
            </div>
          </div>
        </template>

        <!-- 文档列表表格 -->
        <el-table
          :data="documentList"
          v-loading="loading"
          stripe
          border
          style="width: 100%"
          @row-click="handleRowClick"
        >
          <el-table-column prop="id" label="序号" width="80" align="center" />
          <el-table-column prop="name" label="文档名" min-width="200" show-overflow-tooltip />
          <el-table-column prop="file_path" label="文档路径" min-width="180" show-overflow-tooltip />
          <el-table-column prop="status_text" label="状态" width="100" align="center">
            <template #default="scope">
              <el-tag 
                :type="getStatusType(scope.row.status)"
                size="small"
              >
                {{ scope.row.status_text }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="upload_time" label="上传时间" width="160" align="center">
            <template #default="scope">
              {{ formatDateTime(scope.row.upload_time) }}
            </template>
          </el-table-column>
          <el-table-column prop="update_time" label="最近更新时间" width="160" align="center">
            <template #default="scope">
              {{ formatDateTime(scope.row.update_time) }}
            </template>
          </el-table-column>
          <el-table-column prop="upload_user" label="上传用户" width="120" align="center" />
          <el-table-column label="操作" width="180" align="center" fixed="right">
            <template #default="scope">
              <el-button
                type="primary"
                size="small"
                :disabled="!scope.row.can_review"
                @click.stop="handleReview(scope.row)"
              >
                审核
              </el-button>
              <el-button
                type="danger"
                size="small"
                :disabled="!scope.row.can_delete"
                @click.stop="handleDelete(scope.row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="totalCount"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </el-card>
    </div>

    <!-- 下半区域：文档审核面板 (动态展示) -->
    <div v-if="reviewPanelVisible" class="review-panel-section">
      <el-card class="review-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>文档审核 - {{ currentDocument?.name }}</span>
            <div class="header-actions">
              <el-button
                type="success"
                :icon="Check"
                @click="confirmChanges"
                :disabled="!hasChanges"
                size="small"
              >
                确认修改
              </el-button>
              
              <el-button
                type="warning"
                :icon="RefreshLeft"
                @click="undoChanges"
                :disabled="undoStack.length === 0"
                size="small"
              >
                撤销修改 ({{ undoStack.length }}/5)
              </el-button>
              
              <el-button
                type="primary"
                :icon="Finished"
                @click="completeReview"
                :loading="completingReview"
                size="small"
              >
                审核完毕
              </el-button>

              <el-button 
                type="info" 
                :icon="Close" 
                @click="closeReviewPanel"
                size="small"
              >
                关闭审核
              </el-button>
            </div>
          </div>
        </template>

        <!-- 左右分栏布局 -->
        <div class="review-content">
          <!-- 左区：PDF预览 -->
          <div class="pdf-preview-section">
            <PDFPreview 
              :document="currentDocument"
              :file-path="currentDocument?.pdf_path"
            />
          </div>

          <!-- 右区：JSON编辑器 -->
          <div class="json-editor-section">
            <JSONEditor
              v-model:json-data="editingJsonData"
              :original-data="originalJsonData"
              :document-image-path="currentDocument?.image_file_path"
              @change="handleJsonChange"
            />
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Close,
  Check,
  RefreshLeft,
  Finished
} from '@element-plus/icons-vue'
import PDFPreview from '@/components/PDFPreview.vue'
import JSONEditor from '@/components/JSONEditor.vue'
import { documentGovernanceAPI } from '@/api/documentGovernance'

// 响应式数据
const loading = ref(false)
const documentList = ref([])
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const statusFilter = ref(null)

// 审核面板相关
const reviewPanelVisible = ref(false)
const currentDocument = ref(null)
const originalJsonData = ref([])
const editingJsonData = ref([])
const undoStack = ref([])
const completingReview = ref(false)

// 计算属性
const hasChanges = computed(() => {
  return JSON.stringify(editingJsonData.value) !== JSON.stringify(originalJsonData.value)
})

// 生命周期
onMounted(() => {
  loadDocuments()
})

// 方法
const loadDocuments = async () => {
  loading.value = true
  try {
    const params = {
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value
    }
    
    if (statusFilter.value !== null) {
      params.status = statusFilter.value
    }

    const response = await documentGovernanceAPI.getDocuments(params)
    documentList.value = response || []
    
    // 获取总数
    const countResponse = await documentGovernanceAPI.getDocumentsCount(
      statusFilter.value !== null ? { status: statusFilter.value } : {}
    )
    totalCount.value = countResponse?.total || 0
    
  } catch (error) {
    console.error('加载文档列表失败:', error)
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

const refreshDocuments = () => {
  currentPage.value = 1
  loadDocuments()
}

const handleSizeChange = (newSize) => {
  pageSize.value = newSize
  currentPage.value = 1
  loadDocuments()
}

const handleCurrentChange = (newPage) => {
  currentPage.value = newPage
  loadDocuments()
}

const handleRowClick = (row) => {
  // 可以添加行点击处理逻辑
  console.log('Row clicked:', row)
}

const handleReview = async (row) => {
  try {
    loading.value = true
    const response = await documentGovernanceAPI.getDocumentForReview(row.id)
    
    currentDocument.value = response
    originalJsonData.value = response.json_data || []
    editingJsonData.value = JSON.parse(JSON.stringify(originalJsonData.value))
    undoStack.value = []
    reviewPanelVisible.value = true
    
    ElMessage.success('文档审核面板已打开')
  } catch (error) {
    console.error('获取文档审核详情失败:', error)
    ElMessage.error('获取文档审核详情失败')
  } finally {
    loading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档 "${row.name}" 吗？此操作将进行逻辑删除。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await documentGovernanceAPI.deleteDocument(row.id)
    ElMessage.success('文档删除成功')
    loadDocuments()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除文档失败:', error)
      ElMessage.error('删除文档失败')
    }
  }
}

const closeReviewPanel = () => {
  if (hasChanges.value) {
    ElMessageBox.confirm(
      '您有未保存的修改，确定要关闭审核面板吗？',
      '确认关闭',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    ).then(() => {
      reviewPanelVisible.value = false
      currentDocument.value = null
    }).catch(() => {
      // 取消关闭
    })
  } else {
    reviewPanelVisible.value = false
    currentDocument.value = null
  }
}

const handleJsonChange = (newData) => {
  editingJsonData.value = newData
}

const confirmChanges = async () => {
  try {
    await documentGovernanceAPI.saveReviewChanges(currentDocument.value.id, {
      document_id: currentDocument.value.id,
      json_data: editingJsonData.value
    })
    
    // 保存到撤销栈
    if (undoStack.value.length >= 5) {
      undoStack.value.shift() // 移除最旧的
    }
    undoStack.value.push(JSON.parse(JSON.stringify(originalJsonData.value)))
    
    // 更新原始数据
    originalJsonData.value = JSON.parse(JSON.stringify(editingJsonData.value))
    
    ElMessage.success('修改已保存')
  } catch (error) {
    console.error('保存修改失败:', error)
    ElMessage.error('保存修改失败')
  }
}

const undoChanges = async () => {
  if (undoStack.value.length > 0) {
    try {
      await documentGovernanceAPI.undoReviewChanges(currentDocument.value.id)
      
      const previousData = undoStack.value.pop()
      editingJsonData.value = JSON.parse(JSON.stringify(previousData))
      originalJsonData.value = JSON.parse(JSON.stringify(previousData))
      
      ElMessage.success('撤销成功')
    } catch (error) {
      console.error('撤销失败:', error)
      ElMessage.error('撤销失败')
    }
  }
}

const completeReview = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要完成审核吗？审核完成后文档状态将变为"已审核"。',
      '确认完成审核',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info',
      }
    )
    
    completingReview.value = true
    
    await documentGovernanceAPI.completeReview(currentDocument.value.id, {
      document_id: currentDocument.value.id,
      json_data: editingJsonData.value
    })
    
    ElMessage.success('审核完成')
    reviewPanelVisible.value = false
    currentDocument.value = null
    loadDocuments() // 刷新列表
    
  } catch (error) {
    if (error !== 'cancel') {
      console.error('完成审核失败:', error)
      ElMessage.error('完成审核失败')
    }
  } finally {
    completingReview.value = false
  }
}

// 工具方法
const getStatusType = (status) => {
  const typeMap = {
    0: 'warning', // 待审核
    1: 'success', // 已审核
    2: 'danger'   // 已删除
  }
  return typeMap[status] || 'info'
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}
</script>

<style scoped>
.document-governance {
  padding: 20px;
  background-color: #f5f5f5;
  min-height: 100vh;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0 0 8px 0;
  color: #333;
  font-size: 24px;
}

.page-header p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.document-list-section {
  margin-bottom: 20px;
}

.list-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-wrapper {
  margin-top: 20px;
  text-align: center;
}

.review-panel-section {
  margin-top: 20px;
}

.review-card {
  border-radius: 8px;
}

.review-content {
  display: flex;
  gap: 20px;
  min-height: 700px;
  height: calc(100vh - 300px); /* 使用视口高度，预留空间给上下内容 */
}

.pdf-preview-section {
  flex: 1;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  /* 确保PDF预览区域能完全填充可用空间 */
}

.json-editor-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}


/* 响应式设计 */
@media (max-width: 1200px) {
  .review-content {
    flex-direction: column;
    height: auto; /* 小屏幕时使用自动高度 */
    min-height: 800px;
  }
  
  .pdf-preview-section,
  .json-editor-section {
    flex: none;
    min-height: 500px; /* 增加小屏幕时的最小高度 */
    height: auto;
  }
}

/* 超小屏幕优化 */
@media (max-width: 768px) {
  .review-content {
    min-height: 600px;
    gap: 15px;
  }
  
  .pdf-preview-section,
  .json-editor-section {
    min-height: 400px;
  }
}
</style>