<template>
  <div class="json-editor">
    <div class="editor-header">
      <div class="header-left">
        <span class="editor-title">结构化内容编辑</span>
        <!-- 翻页控件 -->
        <div v-if="viewMode === 'editor' && totalPages > 1" class="page-navigation">
          <el-button-group size="small">
            <el-button 
              :icon="ArrowLeft" 
              @click="goToPreviousPage"
              :disabled="currentPage <= 1"
            >
              上一页
            </el-button>
            <el-button disabled>
              第 {{ currentPage }} 页 / 共 {{ totalPages }} 页 (页码: {{ getCurrentPageNumber() }})
            </el-button>
            <el-button 
              :icon="ArrowRight" 
              @click="goToNextPage"
              :disabled="currentPage >= totalPages"
            >
              下一页
            </el-button>
          </el-button-group>
        </div>
      </div>
      <div class="editor-controls">
        <el-button-group>
          <el-button 
            size="small" 
            :type="viewMode === 'editor' ? 'primary' : ''"
            @click="viewMode = 'editor'"
          >
            编辑器
          </el-button>
          <el-button 
            size="small" 
            :type="viewMode === 'preview' ? 'primary' : ''"
            @click="viewMode = 'preview'"
          >
            预览
          </el-button>
          <el-button 
            size="small" 
            :type="viewMode === 'code' ? 'primary' : ''"
            @click="viewMode = 'code'"
          >
            源码
          </el-button>
        </el-button-group>
      </div>
    </div>

    <div class="editor-content" v-loading="loading">
      <!-- 编辑器模式 -->
      <div v-if="viewMode === 'editor'" class="editor-mode">
        <div class="chunks-container">
          <!-- 完全没有数据的空状态 -->
          <div v-if="internalJsonData.length === 0" class="completely-empty-section">
            <el-empty 
              description="还没有任何内容"
              :image-size="150"
            >
              <template #default>
                <p>开始创建第一个内容块吧</p>
                <el-button-group>
                  <el-button 
                    type="primary" 
                    :icon="Plus" 
                    @click="addChunk('text')"
                    size="large"
                  >
                    添加文本
                  </el-button>
                  <el-button 
                    type="primary" 
                    :icon="Grid" 
                    @click="addChunk('table')"
                    size="large"
                  >
                    添加表格
                  </el-button>
                  <el-button 
                    type="primary" 
                    :icon="Picture" 
                    @click="addChunk('image')"
                    size="large"
                  >
                    添加图片
                  </el-button>
                </el-button-group>
              </template>
            </el-empty>
          </div>
          
          <!-- 有数据时显示页码信息 -->
          <div v-else-if="totalPages > 0" class="page-info">
            <el-alert 
              :title="`第 ${getCurrentPageNumber()} 页内容 (共 ${currentPageChunks.length} 个内容块)`"
              type="info" 
              :closable="false"
              show-icon
            />
          </div>
          
          <!-- 当前页的内容块 -->
          <template v-if="internalJsonData.length > 0">
            <div 
              v-for="(item, index) in currentPageChunks" 
              :key="`${item.originalIndex}-${item.chunk.page_idx}`"
              class="chunk-item"
              :class="{ 'chunk-selected': selectedChunkIndex === index }"
              @click="selectChunk(index)"
            >
            <div class="chunk-header">
              <span class="chunk-type">{{ getChunkTypeLabel(item.chunk.type) }}</span>
              <span class="chunk-page">第 {{ item.chunk.page_idx || 1 }} 页</span>
              <div class="chunk-actions">
                <el-button 
                  size="small" 
                  :icon="Edit" 
                  @click.stop="editChunk(index)"
                />
                <el-button 
                  size="small" 
                  type="danger" 
                  :icon="Delete" 
                  @click.stop="deleteChunk(index)"
                />
              </div>
            </div>
            
            <!-- 文本类型 -->
            <div v-if="item.chunk.type === 'text'" class="chunk-content">
              <el-input
                v-model="item.chunk.text"
                type="textarea"
                :rows="3"
                placeholder="请输入文本内容"
                @input="handleChunkChange"
              />
            </div>

            <!-- 表格类型 -->
            <div v-else-if="item.chunk.type === 'table'" class="chunk-content">
              <div class="table-editor">
                <el-input
                  v-model="item.chunk.table_caption"
                  placeholder="表格标题"
                  class="table-caption"
                  @input="handleChunkChange"
                />
                <div class="table-html-editor">
                  <el-input
                    v-model="item.chunk.table_body"
                    type="textarea"
                    :rows="6"
                    placeholder="表格HTML内容"
                    @input="handleChunkChange"
                  />
                </div>
                <el-input
                  v-model="item.chunk.table_footnote"
                  placeholder="表格注释"
                  @input="handleChunkChange"
                />
              </div>
            </div>

            <!-- 图片类型 -->
            <div v-else-if="item.chunk.type === 'image'" class="chunk-content">
              <div class="image-editor">
                <div class="image-preview" v-if="item.chunk.img_path">
                  <img 
                    :src="getImageUrl(item.chunk.img_path)" 
                    :alt="item.chunk.img_caption"
                    class="preview-image"
                    @error="handleImageError"
                  />
                </div>
                <el-input
                  v-model="item.chunk.img_path"
                  placeholder="图片路径"
                  @input="handleChunkChange"
                />
                <el-input
                  v-model="item.chunk.img_caption"
                  placeholder="图片标题"
                  @input="handleChunkChange"
                />
                <el-input
                  v-model="item.chunk.img_footnote"
                  placeholder="图片注释"
                  @input="handleChunkChange"
                />
              </div>
            </div>

            <!-- 每个内容块后的添加按钮 -->
            <div class="chunk-add-actions">
              <el-divider>在此位置添加内容</el-divider>
              <el-button-group size="small">
                <el-button 
                  type="primary" 
                  :icon="Plus" 
                  @click.stop="insertChunk('text', index + 1)"
                >
                  文本
                </el-button>
                <el-button 
                  type="primary" 
                  :icon="Grid" 
                  @click.stop="insertChunk('table', index + 1)"
                >
                  表格
                </el-button>
                <el-button 
                  type="primary" 
                  :icon="Picture" 
                  @click.stop="insertChunk('image', index + 1)"
                >
                  图片
                </el-button>
              </el-button-group>
            </div>
            </div>
            
            <!-- 空状态或页面底部添加按钮 -->
            <div v-if="currentPageChunks.length === 0" class="empty-page-section">
            <el-empty 
              description="当前页暂无内容"
              :image-size="120"
            >
              <template #default>
                <p>这是第 {{ getCurrentPageNumber() }} 页，还没有内容块</p>
                <el-button-group>
                  <el-button 
                    type="primary" 
                    :icon="Plus" 
                    @click="addChunk('text')"
                  >
                    添加文本
                  </el-button>
                  <el-button 
                    type="primary" 
                    :icon="Grid" 
                    @click="addChunk('table')"
                  >
                    添加表格
                  </el-button>
                  <el-button 
                    type="primary" 
                    :icon="Picture" 
                    @click="addChunk('image')"
                  >
                    添加图片
                  </el-button>
                </el-button-group>
              </template>
            </el-empty>
          </div>
          
          <!-- 页面底部添加按钮（当页面有内容时） -->
          <div v-else class="add-chunk-section">
            <el-divider>在本页末尾添加内容</el-divider>
            <el-button-group>
              <el-button 
                type="primary" 
                :icon="Plus" 
                @click="addChunk('text')"
              >
                添加文本
              </el-button>
              <el-button 
                type="primary" 
                :icon="Grid" 
                @click="addChunk('table')"
              >
                添加表格
              </el-button>
              <el-button 
                type="primary" 
                :icon="Picture" 
                @click="addChunk('image')"
              >
                添加图片
              </el-button>
            </el-button-group>
          </div>
          </template>
        </div>
      </div>

      <!-- 预览模式 -->
      <div v-else-if="viewMode === 'preview'" class="preview-mode">
        <div class="preview-container">
          <!-- 显示当前页码信息 -->
          <div v-if="totalPages > 0" class="page-info">
            <el-alert 
              :title="`第 ${getCurrentPageNumber()} 页预览 (共 ${currentPageChunks.length} 个内容块)`"
              type="success" 
              :closable="false"
              show-icon
            />
          </div>
          
          <div 
            v-for="(item, index) in currentPageChunks" 
            :key="`preview-${item.originalIndex}-${item.chunk.page_idx}`"
            class="preview-chunk"
          >
            <!-- 文本预览 -->
            <div v-if="item.chunk.type === 'text'" class="preview-text">
              <p>{{ item.chunk.text }}</p>
            </div>

            <!-- 表格预览 -->
            <div v-else-if="item.chunk.type === 'table'" class="preview-table">
              <h4 v-if="item.chunk.table_caption">{{ item.chunk.table_caption }}</h4>
              <div v-html="item.chunk.table_body" class="table-content"></div>
              <p v-if="item.chunk.table_footnote" class="footnote">{{ item.chunk.table_footnote }}</p>
            </div>

            <!-- 图片预览 -->
            <div v-else-if="item.chunk.type === 'image'" class="preview-image">
              <img 
                v-if="item.chunk.img_path"
                :src="getImageUrl(item.chunk.img_path)" 
                :alt="item.chunk.img_caption"
                class="preview-img"
              />
              <h4 v-if="item.chunk.img_caption">{{ item.chunk.img_caption }}</h4>
              <p v-if="item.chunk.img_footnote" class="footnote">{{ item.chunk.img_footnote }}</p>
            </div>

            <div class="chunk-meta">
              <small>页码: {{ item.chunk.page_idx || 1 }} | 类型: {{ getChunkTypeLabel(item.chunk.type) }}</small>
            </div>
          </div>
        </div>
      </div>

      <!-- 源码模式 -->
      <div v-else-if="viewMode === 'code'" class="code-mode">
        <el-input
          v-model="jsonCodeString"
          type="textarea"
          :rows="20"
          placeholder="JSON源码"
          @input="handleCodeChange"
          class="code-editor"
        />
        <div class="code-actions">
          <el-button @click="formatJson">格式化</el-button>
          <el-button @click="validateJson">验证</el-button>
          <el-button @click="applyCodeChanges" type="primary">应用更改</el-button>
        </div>
      </div>
    </div>

    <!-- 状态栏 -->
    <div class="editor-footer">
      <span class="status-info">
        <span v-if="totalPages > 0">
          第 {{ getCurrentPageNumber() }} 页: {{ currentPageChunks.length }} 个内容块 | 
          总计: {{ internalJsonData.length }} 个内容块 ({{ totalPages }} 页)
        </span>
        <span v-else>暂无内容</span>
        <span v-if="hasChanges" class="change-indicator">• 已修改</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Edit,
  Delete,
  Plus,
  Grid,
  Picture,
  ArrowLeft,
  ArrowRight
} from '@element-plus/icons-vue'

// Props
const props = defineProps({
  jsonData: {
    type: Array,
    default: () => []
  },
  originalData: {
    type: Array,
    default: () => []
  },
  documentImagePath: {
    type: String,
    default: ''
  }
})

// Emits
const emit = defineEmits(['update:jsonData', 'change'])

// 响应式数据
const loading = ref(false)
const viewMode = ref('editor')
const selectedChunkIndex = ref(-1)
const internalJsonData = ref([])
const jsonCodeString = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

// 方法定义 - 必须在watch之前定义
const updateCodeString = () => {
  jsonCodeString.value = JSON.stringify(internalJsonData.value, null, 2)
}

const handleChunkChange = () => {
  nextTick(() => {
    emit('update:jsonData', internalJsonData.value)
    emit('change', internalJsonData.value)
  })
}

// 处理单个内容块的数据变化
const handleSingleChunkChange = (chunkIndex) => {
  // 通过原始索引更新数据
  const currentChunks = currentPageChunks.value
  if (chunkIndex < currentChunks.length) {
    const originalIndex = currentChunks[chunkIndex].originalIndex
    // 触发响应式更新
    handleChunkChange()
  }
}

// 计算属性
const hasChanges = computed(() => {
  if (!props.originalData) return false
  return JSON.stringify(internalJsonData.value) !== JSON.stringify(props.originalData)
})

// 按页码分组的内容块
const groupedByPage = computed(() => {
  const groups = {}
  internalJsonData.value.forEach((chunk, originalIndex) => {
    const pageIdx = chunk.page_idx || 1
    if (!groups[pageIdx]) {
      groups[pageIdx] = []
    }
    // 创建包装对象，包含原始chunk的引用和当前索引
    groups[pageIdx].push({
      chunk: chunk, // 直接引用原始chunk
      originalIndex: originalIndex // 当前正确的索引
    })
  })
  return groups
})

// 页码列表（排序）
const pageNumbers = computed(() => {
  const pages = Object.keys(groupedByPage.value).map(Number).sort((a, b) => a - b)
  totalPages.value = pages.length
  return pages
})

// 当前页的内容块
const currentPageChunks = computed(() => {
  const pages = pageNumbers.value
  if (pages.length === 0) return []
  
  // 确保当前页在有效范围内
  if (currentPage.value > pages.length) {
    currentPage.value = pages.length
  }
  if (currentPage.value < 1) {
    currentPage.value = 1
  }
  
  const actualPageNumber = pages[currentPage.value - 1]
  return groupedByPage.value[actualPageNumber] || []
})

// 监听外部数据变化
watch(() => props.jsonData, (newData) => {
  if (newData) {
    internalJsonData.value = JSON.parse(JSON.stringify(newData))
    updateCodeString()
  }
}, { immediate: true, deep: true })

// 监听视图模式变化
watch(viewMode, (newMode) => {
  if (newMode === 'code') {
    updateCodeString()
  }
})

// 翻页控制方法
const goToPreviousPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    selectedChunkIndex.value = -1 // 重置选中状态
  }
}

const goToNextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    selectedChunkIndex.value = -1 // 重置选中状态
  }
}

const goToPage = (pageNum) => {
  if (pageNum >= 1 && pageNum <= totalPages.value) {
    currentPage.value = pageNum
    selectedChunkIndex.value = -1 // 重置选中状态
  }
}

const getCurrentPageNumber = () => {
  const pages = pageNumbers.value
  return pages[currentPage.value - 1] || 1
}

const selectChunk = (index) => {
  selectedChunkIndex.value = index
}

const editChunk = (index) => {
  selectedChunkIndex.value = index
  // 可以在这里添加更详细的编辑逻辑
}

const deleteChunk = async (index) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个内容块吗？',
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    // 获取当前页的内容块，找到原始索引
    const currentChunks = currentPageChunks.value
    if (index < currentChunks.length) {
      const originalIndex = currentChunks[index].originalIndex
      internalJsonData.value.splice(originalIndex, 1)
      handleChunkChange()
      ElMessage.success('内容块已删除')
    }
  } catch {
    // 用户取消删除
  }
}

const addChunk = (type) => {
  // 获取当前页码，如果没有页面则默认为1
  const currentPageNumber = totalPages.value > 0 ? getCurrentPageNumber() : 1
  
  let newChunk = {
    type,
    page_idx: currentPageNumber
  }

  switch (type) {
    case 'text':
      newChunk.text = ''
      break
    case 'table':
      newChunk.table_caption = ''
      newChunk.table_body = '<table><tr><td>单元格内容</td></tr></table>'
      newChunk.table_footnote = ''
      break
    case 'image':
      newChunk.img_path = ''
      newChunk.img_caption = ''
      newChunk.img_footnote = ''
      break
  }

  // 添加到当前页的末尾
  const currentChunks = currentPageChunks.value
  let insertIndex = internalJsonData.value.length // 默认插入到末尾
  
  if (currentChunks.length > 0) {
    // 在当前页最后一个元素之后插入
    insertIndex = currentChunks[currentChunks.length - 1].originalIndex + 1
  }

  internalJsonData.value.splice(insertIndex, 0, newChunk)
  selectedChunkIndex.value = currentChunks.length // 选中新添加的元素
  handleChunkChange()
  ElMessage.success(`已在第${currentPageNumber}页添加${getChunkTypeLabel(type)}块`)
}

const insertChunk = (type, position) => {
  // 获取当前页码
  const currentPageNumber = getCurrentPageNumber()
  
  let newChunk = {
    type,
    page_idx: currentPageNumber
  }

  switch (type) {
    case 'text':
      newChunk.text = ''
      break
    case 'table':
      newChunk.table_caption = ''
      newChunk.table_body = '<table><tr><td>单元格内容</td></tr></table>'
      newChunk.table_footnote = ''
      break
    case 'image':
      newChunk.img_path = ''
      newChunk.img_caption = ''
      newChunk.img_footnote = ''
      break
  }

  // 计算在原始数组中的插入位置
  const currentChunks = currentPageChunks.value
  let insertIndex = internalJsonData.value.length // 默认插入到末尾
  
  if (position < currentChunks.length) {
    // 在指定位置之后插入
    insertIndex = currentChunks[position].originalIndex + 1
  } else if (currentChunks.length > 0) {
    // 在当前页最后一个元素之后插入
    insertIndex = currentChunks[currentChunks.length - 1].originalIndex + 1
  }

  internalJsonData.value.splice(insertIndex, 0, newChunk)
  selectedChunkIndex.value = position
  handleChunkChange()
  ElMessage.success(`已在第${currentPageNumber}页插入${getChunkTypeLabel(type)}块`)
}

const getCurrentPageIndex = (position) => {
  // 获取插入位置前一个元素的页码，如果没有则使用1
  if (position > 0 && internalJsonData.value[position - 1]) {
    return internalJsonData.value[position - 1].page_idx || 1
  }
  return 1
}

const getNextPageIndex = () => {
  const lastChunk = internalJsonData.value[internalJsonData.value.length - 1]
  return lastChunk ? (lastChunk.page_idx || 1) : 1
}

const getChunkTypeLabel = (type) => {
  const typeMap = {
    text: '文本',
    table: '表格',
    image: '图片'
  }
  return typeMap[type] || type
}

const getImageUrl = (imagePath) => {
  if (!imagePath) return ''
  
  // 构建图片URL
  // 生产环境推荐留空走同源；需要时可通过 VITE_API_BASE_URL 覆盖
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  
  // 如果有文档的图片路径基础路径，且当前路径是相对路径（如："images/filename.jpg"）
  if (props.documentImagePath && !imagePath.match(/^[a-zA-Z]:|^\//)) {
    // 从JSON中的img_path提取文件名
    const fileName = imagePath.split('/').pop() // 获取最后一部分作为文件名
    
    // 构建完整的绝对路径：MySQL中的image_file_path + 文件名
    const fullImagePath = `${props.documentImagePath.replace(/\/$/, '')}/${fileName}`
    
    // 通过后端API访问绝对路径文件
    const encodedPath = encodeURIComponent(fullImagePath)
    return `${baseUrl}/api/document-governance/files/image?path=${encodedPath}`
  }
  
  // 处理绝对路径（兼容原有逻辑）
  if (imagePath.match(/^[a-zA-Z]:|^\//)) {
    // 通过后端API访问绝对路径文件
    const encodedPath = encodeURIComponent(imagePath)
    return `${baseUrl}/api/document-governance/files/image?path=${encodedPath}`
  }
  
  // 如果是相对路径，构建完整URL（兼容原有逻辑）
  if (imagePath.startsWith('/')) {
    return `${baseUrl}/files${imagePath}`
  }
  
  return imagePath
}

const handleImageError = (event) => {
  const target = event.target
  target.src = '/placeholder-image.png' // 设置占位图片
}

// 源码模式相关方法
const handleCodeChange = () => {
  // 这里不立即应用更改，等用户点击"应用更改"按钮
}

const formatJson = () => {
  try {
    const parsed = JSON.parse(jsonCodeString.value)
    jsonCodeString.value = JSON.stringify(parsed, null, 2)
    ElMessage.success('JSON格式化成功')
  } catch (error) {
    ElMessage.error('JSON格式错误，无法格式化')
  }
}

const validateJson = () => {
  try {
    JSON.parse(jsonCodeString.value)
    ElMessage.success('JSON格式正确')
  } catch (error) {
    ElMessage.error('JSON格式错误: ' + error.message)
  }
}

const applyCodeChanges = () => {
  try {
    const parsed = JSON.parse(jsonCodeString.value)
    if (!Array.isArray(parsed)) {
      throw new Error('JSON数据必须是数组格式')
    }
    
    internalJsonData.value = parsed
    handleChunkChange()
    ElMessage.success('源码更改已应用')
  } catch (error) {
    ElMessage.error('应用更改失败: ' + error.message)
  }
}
</script>

<style scoped>
.json-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  /* 移除边界，由父容器控制 */
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-navigation {
  margin-left: 20px;
}

.page-info {
  margin-bottom: 16px;
}

.page-info .el-alert {
  border-radius: 4px;
}

.editor-title {
  font-weight: 500;
  color: #333;
}

.editor-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.editor-footer {
  padding: 8px 16px;
  background-color: #f8f9fa;
  border-top: 1px solid #e4e7ed;
  font-size: 12px;
  color: #666;
}

.change-indicator {
  color: #f56c6c;
  font-weight: bold;
}

/* 编辑器模式样式 */
.chunks-container {
  space-y: 16px;
}

.chunk-item {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  margin-bottom: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.chunk-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.chunk-selected {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.2);
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
}

.chunk-type {
  font-weight: 500;
  color: #409eff;
}

.chunk-page {
  font-size: 12px;
  color: #666;
}

.chunk-actions {
  display: flex;
  gap: 8px;
}

.chunk-content {
  padding: 16px;
}

.table-editor {
  space-y: 12px;
}

.table-caption,
.table-html-editor {
  margin-bottom: 12px;
}

.image-editor {
  space-y: 12px;
}

.image-preview {
  margin-bottom: 12px;
}

.preview-image {
  max-width: 200px;
  max-height: 150px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}

.chunk-add-actions {
  padding: 12px 16px;
  background-color: #f8f9fa;
  border-top: 1px solid #e4e7ed;
  text-align: center;
  opacity: 0.7;
  transition: opacity 0.3s ease;
}

.chunk-item:hover .chunk-add-actions {
  opacity: 1;
}

.chunk-add-actions .el-divider {
  margin: 8px 0;
  font-size: 12px;
  color: #999;
}

.completely-empty-section {
  padding: 60px 20px;
  text-align: center;
}

.completely-empty-section p {
  margin: 20px 0;
  color: #666;
  font-size: 16px;
}

.empty-page-section {
  padding: 40px 20px;
  text-align: center;
}

.empty-page-section p {
  margin: 16px 0;
  color: #666;
  font-size: 14px;
}

.add-chunk-section {
  padding: 20px;
  text-align: center;
  border: 2px dashed #e4e7ed;
  border-radius: 6px;
  margin-top: 16px;
}

.add-chunk-section .el-divider {
  margin: 12px 0 16px 0;
  font-size: 12px;
  color: #999;
}

/* 预览模式样式 */
.preview-container {
  background-color: #fff;
}

.preview-chunk {
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
}

.preview-text p {
  margin: 0;
  line-height: 1.6;
}

.preview-table h4 {
  margin: 0 0 12px 0;
  color: #333;
}

.table-content {
  margin: 12px 0;
}

.table-content table {
  width: 100%;
  border-collapse: collapse;
}

.table-content td,
.table-content th {
  border: 1px solid #e4e7ed;
  padding: 8px 12px;
  text-align: left;
}

.preview-image h4 {
  margin: 12px 0 8px 0;
  color: #333;
}

.preview-img {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.footnote {
  font-size: 12px;
  color: #666;
  margin-top: 8px;
  font-style: italic;
}

.chunk-meta {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}

/* 源码模式样式 */
.code-mode {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.code-editor {
  flex: 1;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.code-actions {
  margin-top: 12px;
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .chunk-header {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }
  
  .chunk-actions {
    align-self: flex-end;
  }
  
  .editor-controls {
    margin-top: 8px;
  }
}
</style>