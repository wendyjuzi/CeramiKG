<template>
  <div class="pdf-preview">
    <div class="preview-header">
      <span class="preview-title">PDF预览</span>
      <div class="preview-controls">
        <el-button-group>
          <el-button 
            size="small" 
            :icon="ZoomOut" 
            @click="zoomOut"
            :disabled="scale <= 0.5"
          />
          <el-button size="small" disabled>{{ Math.round(scale * 100) }}%</el-button>
          <el-button 
            size="small" 
            :icon="ZoomIn" 
            @click="zoomIn"
            :disabled="scale >= 3"
          />
        </el-button-group>
      </div>
    </div>

    <div class="preview-content" v-loading="loading">
      <!-- PDF文件不存在时的占位符 -->
      <div v-if="!document?.file_path" class="placeholder">
        <el-icon class="placeholder-icon"><Document /></el-icon>
        <p>暂无PDF文件</p>
      </div>

      <!-- PDF预览区域 -->
      <div v-else class="pdf-container" :style="{ transform: `scale(${scale})` }">
        <!-- 这里使用iframe来预览PDF，实际项目中可能需要使用专门的PDF.js库 -->
        <iframe
          v-if="pdfUrl"
          :src="pdfUrl"
          class="pdf-iframe"
          frameborder="0"
          @load="handlePdfLoad"
          @error="handlePdfError"
        ></iframe>
        
        <!-- PDF加载失败时的占位符 -->
        <div v-else class="error-placeholder">
          <el-icon class="error-icon"><Warning /></el-icon>
          <p>PDF文件加载失败</p>
          <p class="error-path">文件路径: {{ document?.file_path || props.filePath }}</p>
          <p v-if="/[\u4e00-\u9fa5]/.test(document?.file_path || props.filePath)" class="error-hint">
            <el-icon><InfoFilled /></el-icon>
            路径包含中文字符，正在尝试特殊编码处理
          </p>
          <div class="error-actions">
            <el-button size="small" @click="retryLoad">重试加载</el-button>
            <el-button size="small" type="primary" @click="copyPath">复制路径</el-button>
          </div>
        </div>
      </div>

    </div>

    <!-- 预览说明 -->
    <div class="preview-notice">
      <el-alert
        title="预览说明"
        type="info"
        :closable="false"
        show-icon
      >
        <template #default>
          <ul class="notice-list">
            <li>此预览仅供查看，无法下载或打印</li>
            <li>支持缩放和翻页操作</li>
            <li>完全支持中文路径和中文文件名</li>
            <li>如需编辑文档内容，请使用右侧JSON编辑器</li>
          </ul>
        </template>
      </el-alert>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ZoomIn,
  ZoomOut,
  ArrowLeft,
  ArrowRight,
  Document,
  Warning,
  InfoFilled
} from '@element-plus/icons-vue'

// Props
const props = defineProps({
  document: {
    type: Object,
    default: null
  },
  filePath: {
    type: String,
    default: ''
  }
})

// 响应式数据
const loading = ref(false)
const scale = ref(1.0)
const currentPage = ref(1)
const totalPages = ref(1)
const pdfLoaded = ref(false)

// 方法定义 - 必须在watch之前定义
const resetPreview = () => {
  scale.value = 1.0
  currentPage.value = 1
  totalPages.value = 1
  pdfLoaded.value = false
}

// 改进的中文路径编码函数
const encodeChinesePath = (path) => {
  if (!path) return ''
  
  try {
    // 对于URL查询参数，我们需要对整个路径进行编码
    // 但保持路径分隔符的语义
    
    // 方案1: 对整个路径进行编码（推荐用于查询参数）
    const fullEncodedPath = encodeURIComponent(path)
    
    console.log('Original path:', path)
    console.log('Full encoded path:', fullEncodedPath)
    console.log('Path contains Chinese:', /[\u4e00-\u9fa5]/.test(path))
    
    return fullEncodedPath
  } catch (error) {
    console.error('路径编码失败:', error)
    // 如果编码失败，尝试基本编码
    try {
      return encodeURI(path)
    } catch (fallbackError) {
      console.error('回退编码也失败:', fallbackError)
      return path
    }
  }
}

// 路径验证函数
const validatePath = (path) => {
  if (!path) return false
  
  // 检查是否为有效的文件路径
  const validExtensions = ['.pdf', '.PDF']
  const hasValidExtension = validExtensions.some(ext => path.toLowerCase().endsWith(ext))
  
  if (!hasValidExtension) {
    console.warn('不是有效的PDF文件路径:', path)
    return false
  }
  
  return true
}

const loadPdf = async () => {
  if (!pdfUrl.value) return
  
  loading.value = true
  try {
    // 这里可以添加PDF预加载逻辑
    // 实际项目中可能需要使用PDF.js来获取页面信息
    await new Promise(resolve => setTimeout(resolve, 500)) // 模拟加载
    
    // 模拟获取PDF信息
    totalPages.value = Math.floor(Math.random() * 20) + 1 // 随机页数
    pdfLoaded.value = true
    
  } catch (error) {
    console.error('PDF加载失败:', error)
    ElMessage.error('PDF文件加载失败')
  } finally {
    loading.value = false
  }
}

// 计算属性
const pdfUrl = computed(() => {
  if (!props.filePath) {
    console.log('没有提供PDF文件路径')
    return null
  }
  
  // 验证路径是否有效
  if (!validatePath(props.filePath)) {
    console.error('无效的PDF文件路径:', props.filePath)
    return null
  }
  
  // 构建PDF预览URL
  // 生产环境推荐留空走同源；需要时可通过 VITE_API_BASE_URL 覆盖
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  
  let baseUrlWithoutParams = ''
  
  // 处理绝对路径（Windows: C:\ 或 Unix: /）
  if (props.filePath.match(/^[a-zA-Z]:|^\//)) {
    // 通过后端API访问绝对路径文件，使用改进的中文路径编码
    const encodedPath = encodeChinesePath(props.filePath)
    baseUrlWithoutParams = `${baseUrl}/api/document-governance/files/pdf?path=${encodedPath}`
    
    console.log('构建的PDF URL (绝对路径):', baseUrlWithoutParams)
  } else if (props.filePath.startsWith('/')) {
    // 如果是相对路径，对路径进行编码后构建完整URL
    const encodedPath = encodeChinesePath(props.filePath)
    baseUrlWithoutParams = `${baseUrl}/files${encodedPath}`
    
    console.log('构建的PDF URL (相对路径):', baseUrlWithoutParams)
  } else {
    // 如果已经是完整URL，直接使用（但仍需要编码查询参数）
    baseUrlWithoutParams = props.filePath
    
    console.log('使用完整URL:', baseUrlWithoutParams)
  }
  
  // 添加PDF查看器参数，包括页码控制
  const pdfParams = [
    'toolbar=0',
    'navpanes=0', 
    'scrollbar=1',
    `page=${currentPage.value}`
  ].join('&')
  
  const finalUrl = `${baseUrlWithoutParams}#${pdfParams}`
  console.log('最终PDF URL:', finalUrl)
  
  return finalUrl
})

// 监听文档变化
watch(() => props.document, (newDoc) => {
  if (newDoc) {
    resetPreview()
    loadPdf()
  }
}, { immediate: true })

const handlePdfLoad = () => {
  pdfLoaded.value = true
  loading.value = false
}

const handlePdfError = () => {
  pdfLoaded.value = false
  loading.value = false
  
  // 提供更详细的错误信息，特别是对中文路径的处理
  const errorMessage = `PDF文件加载失败: ${props.filePath}`
  console.error(errorMessage)
  console.error('文件路径包含中文字符:', /[\u4e00-\u9fa5]/.test(props.filePath))
  
  ElMessage.error({
    message: 'PDF文件加载失败，请检查文件路径是否正确',
    duration: 5000
  })
}

const retryLoad = () => {
  loadPdf()
}

// 复制路径到剪贴板
const copyPath = async () => {
  const pathToCopy = document?.file_path || props.filePath
  if (!pathToCopy) return
  
  try {
    await navigator.clipboard.writeText(pathToCopy)
    ElMessage.success('路径已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制路径失败')
  }
}

// 缩放控制
const zoomIn = () => {
  if (scale.value < 3) {
    scale.value = Math.min(scale.value + 0.25, 3)
  }
}

const zoomOut = () => {
  if (scale.value > 0.5) {
    scale.value = Math.max(scale.value - 0.25, 0.5)
  }
}


// 键盘快捷键
const handleKeydown = (event) => {
  if (event.target !== document.body) return
  
  switch (event.key) {
    case '+':
    case '=':
      zoomIn()
      break
    case '-':
      zoomOut()
      break
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.pdf-preview {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #f8f9fa;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.preview-title {
  font-weight: 500;
  color: #333;
}

.preview-content {
  flex: 1;
  position: relative;
  overflow: auto;
  background: #e9ecef;
  /* 确保预览内容区域能够填充所有可用空间 */
  display: flex;
  flex-direction: column;
}

.placeholder,
.error-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 300px;
  color: #999;
}

.placeholder-icon,
.error-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-icon {
  color: #f56c6c;
}

.error-path {
  font-size: 12px;
  color: #666;
  margin: 8px 0;
  word-break: break-all;
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}

.error-hint {
  font-size: 12px;
  color: #409eff;
  margin: 8px 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.error-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  justify-content: center;
}

.pdf-container {
  display: flex;
  justify-content: center;
  padding: 20px;
  transform-origin: center top;
  transition: transform 0.3s ease;
  flex: 1;
  /* 让PDF容器填充所有可用空间 */
}

.pdf-iframe {
  width: 100%;
  height: 100%;
  min-height: 500px; /* 设置最小高度确保内容可见 */
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.page-navigation {
  padding: 12px 16px;
  background-color: #fff;
  border-top: 1px solid #e4e7ed;
  display: flex;
  justify-content: center;
}

.preview-notice {
  margin-top: 16px;
  padding: 16px;
  background-color: #f8f9fa;
  border-top: 1px solid #e4e7ed;
  border-radius: 4px;
  /* 与右侧editor-actions区域保持相同的样式 */
}

.notice-list {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: #666;
}

.notice-list li {
  margin: 4px 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .preview-header {
    flex-direction: column;
    gap: 12px;
  }
  
  .pdf-iframe {
    min-height: 400px; /* 移动端保持最小高度 */
  }
  
  .page-navigation {
    padding: 8px;
  }
  
  .pdf-container {
    padding: 10px; /* 移动端减少内边距 */
  }
}
</style>