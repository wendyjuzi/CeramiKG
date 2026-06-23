<template>
  <div class="build-container">
    <div class="build-header">
      <h1>🏗️ 知识图谱构建</h1>
      <p class="build-description">通过6个步骤轻松构建知识图谱：选择文档、选择术语、识别实体、抽取关系、存储知识、展示图谱</p>
    </div>

    <!-- 新的步骤指示器设计 -->
    <div class="custom-steps-container">
      <div
        v-for="(step, index) in steps"
        :key="index"
        class="custom-step"
        :class="{
          'is-active': currentStep === index + 1,
          'is-completed': currentStep > index + 1,
          'is-clickable': index + 1 === 1 || index + 1 === 6
        }"
        @click="handleStepClick(index + 1)"
      >
        <div class="step-circle">
          <span class="step-number">{{ index + 1 }}</span>
        </div>
        <div class="step-content">
          <div class="step-title">{{ step.title }}</div>
          <div class="step-description">{{ step.description }}</div>
        </div>
        <div v-if="index < steps.length - 1" class="step-line"></div>
      </div>
    </div>

    <div class="step-content">
      <!-- 步骤1: 文档选择 -->
      <div v-show="currentStep === 1" class="step-panel">
        <DocumentSelector
          @document-selected="handleDocumentSelected"
          @document-changed="handleDocumentChanged"
        />
      </div>

      <!-- 步骤2: 术语选择 -->
      <div v-show="currentStep === 2" class="step-panel">
        <TermSelector
          @terms-selected="handleTermsSelected"
          @terms-changed="handleTermsChanged"
        />
      </div>

      <!-- 步骤3: 实体识别 -->
      <div v-show="currentStep === 3" class="step-panel">
        <EntityEvaluator
          :selected-document="selectedDocument"
          :selected-terms="selectedTerms"
          @entities-confirmed="handleEntitiesConfirmed"
          @entities-changed="handleEntitiesChanged"
        />
      </div>

      <!-- 步骤4: 关系抽取 -->
      <div v-show="currentStep === 4" class="step-panel">
        <RelationEvaluator
          ref="relationEvaluatorRef"
          :selected-document="selectedDocument"
          :selected-terms="selectedTerms"
          :confirmed-entities="confirmedEntities"
          @knowledge-saved="handleKnowledgeSaved"
          @relations-changed="handleRelationsChanged"
        />
      </div>

      <!-- 步骤5: 知识存储 -->
      <div v-show="currentStep === 5" class="step-panel">
        <div class="knowledge-storage">
          <div class="storage-header">
            <h3>💾 知识存储</h3>
            <p>关系数据已保存到数据库，可以进行图谱可视化</p>
          </div>

          <div v-if="storageResult" class="storage-summary">
            <el-result
              :icon="storageResult.success ? 'success' : 'error'"
              :title="storageResult.success ? '知识保存成功' : '知识保存失败'"
              :sub-title="storageResult.message || ''"
            >
              <template #extra>
                <div v-if="storageResult.success && storageResult.data" class="storage-details">
                  <el-descriptions :column="2" border>
                    <el-descriptions-item label="文档名称">
                      {{ storageResult.document_name || storageResult.data.document_name || selectedDocument?.name }}
                    </el-descriptions-item>
                    <el-descriptions-item label="关系数量">
                      {{ storageResult.data.relations_count || storageResult.data.knowledges_count || storageResult.relations?.length || 0 }}
                    </el-descriptions-item>
                    <el-descriptions-item label="表名" v-if="storageResult.data.table_info || storageResult.data.table_name">
                      {{ storageResult.data.table_info?.table_name || storageResult.data.table_name }}
                    </el-descriptions-item>
                    <el-descriptions-item label="存储时间">
                      {{ new Date().toLocaleString('zh-CN') }}
                    </el-descriptions-item>
                  </el-descriptions>
                </div>
              </template>
            </el-result>
          </div>

          <div v-else class="empty-storage">
            <el-empty description="请先完成关系抽取并保存知识">
              <el-button @click="prevStep">返回关系抽取</el-button>
            </el-empty>
          </div>
        </div>
      </div>

      <!-- 步骤6: 图谱展示 -->
      <div v-show="currentStep === 6" class="step-panel">
        <KnowledgeGraph
          :document-id="selectedDocument?.document_id || ''"
          :document-name="selectedDocument?.name || ''"
          @update:document-id="handleDocumentIdUpdate"
          @node-selected="handleNodeSelected"
          @graph-loaded="handleGraphLoaded"
        />
      </div>
    </div>

    <div class="step-actions">
      <el-button
        v-if="currentStep > 1"
        @click="prevStep"
        :disabled="isProcessing"
        size="large"
      >
        <el-icon><ArrowLeft /></el-icon>
        上一步
      </el-button>

      <div class="step-info">
        <span class="step-number">{{ currentStep }} / 6</span>
        <span class="step-title">{{ getStepTitle(currentStep) }}</span>
      </div>

      <el-button
        v-if="currentStep < 6"
        type="primary"
        @click="nextStep"
        :disabled="!canProceed || isProcessing"
        size="large"
      >
        下一步
        <el-icon><ArrowRight /></el-icon>
      </el-button>

      <el-button
        v-if="currentStep === 6"
        @click="resetBuild"
        type="success"
        size="large"
      >
        <el-icon><RefreshLeft /></el-icon>
        重新构建
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onBeforeUnmount, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowRight, RefreshLeft } from '@element-plus/icons-vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import axios from 'axios'
import DocumentSelector from '@/components/DocumentSelector.vue'
import TermSelector from '@/components/TermSelector.vue'
import EntityEvaluator from '@/components/EntityEvaluator.vue'
import RelationEvaluator from '@/components/RelationEvaluator.vue'
import KnowledgeGraph from '@/components/KnowledgeGraph.vue'
import { useBuildStore } from '@/stores/buildStore.js'

// 步骤配置
const steps = [
  { title: '文档选择', description: '选择要分析的文档' },
  { title: '术语选择', description: '选择相关的术语库' },
  { title: '实体识别', description: '识别文档中的实体' },
  { title: '关系抽取', description: '抽取实体间的关系' },
  { title: '知识存储', description: '保存知识到数据库' },
  { title: '图谱展示', description: '可视化知识图谱' }
]

// 初始化构建状态管理器
const {
  startBuild,
  updateBuildStep,
  updateBuildData,
  completeBuild,
  resetBuild: resetBuildStore,
  shouldShowLeaveConfirmation,
  hasLoadedGraph
} = useBuildStore()

// 当前步骤
const currentStep = ref(1)

// 组件引用
const relationEvaluatorRef = ref(null)
const route = useRoute()

// 数据状态
const selectedDocument = ref(null)
const selectedTerms = ref([])
const confirmedEntities = ref([])
const confirmedRelations = ref([])
const hasSelectedRelations = ref(false)
const storageResult = ref(null)
const knowledgeGraphData = ref(null)

// 加载状态
const isProcessing = ref(false)

// 计算属性
const canProceed = computed(() => {
  switch (currentStep.value) {
    case 1:
      return selectedDocument.value !== null
    case 2:
      return true
    case 3:
      return confirmedEntities.value.length > 0
    case 4:
      return hasSelectedRelations.value || confirmedRelations.value.length > 0
    case 5:
      return storageResult.value && storageResult.value.success
    case 6:
      return true
    default:
      return false
  }
})

// 获取步骤标题
const getStepTitle = (step) => {
  const titles = {
    1: '文档选择',
    2: '术语选择',
    3: '实体识别',
    4: '关系抽取',
    5: '知识存储',
    6: '图谱展示'
  }
  return titles[step] || ''
}

// 处理步骤点击（第1步和第6步可点击）
const handleStepClick = (step) => {
  if (step === 1) {
    currentStep.value = 1
    ElMessage.success('已跳转到文档选择')
  } else if (step === 6) {
    currentStep.value = 6
    ElMessage.success('已跳转到图谱展示')
  }
}

// 事件处理函数
const handleDocumentSelected = (document) => {
  selectedDocument.value = document
  console.log('文档选择:', document)
}

const handleDocumentChanged = (document) => {
  selectedDocument.value = document
}

const handleTermsSelected = (terms) => {
  selectedTerms.value = terms
  console.log('术语选择:', terms.length, '个')
}

const handleTermsChanged = (terms) => {
  selectedTerms.value = terms
}

const handleEntitiesConfirmed = (entities) => {
  confirmedEntities.value = entities
  console.log('实体确认:', entities.length, '个')
  nextStep()
}

const handleEntitiesChanged = (entities) => {
  confirmedEntities.value = entities
}

const handleRelationsChanged = (relations) => {
  confirmedRelations.value = relations
  hasSelectedRelations.value = relations && relations.length > 0
}

const handleKnowledgeSaved = (result) => {
  storageResult.value = result
  console.log('知识保存结果:', result)
  nextStep()
}

const handleNodeSelected = (node) => {
  console.log('选中节点:', node)
}

const handleGraphLoaded = (graphData) => {
  knowledgeGraphData.value = graphData
  console.log('图谱加载完成:', graphData)
}

const handleDocumentIdUpdate = (newDocumentId) => {
  console.log('文档ID更新:', newDocumentId)
}

// 步骤导航
const nextStep = async () => {
  if (currentStep.value === 4 && canProceed.value) {
    if (!storageResult.value || !storageResult.value.success) {
      try {
        if (relationEvaluatorRef.value && relationEvaluatorRef.value.saveKnowledge) {
          await relationEvaluatorRef.value.saveKnowledge()
        } else {
          ElMessage.error('关系抽取组件未正确加载')
        }
      } catch (error) {
        console.log('用户取消保存或保存失败')
      }
    } else {
      currentStep.value++
    }
  } else if (canProceed.value && currentStep.value < 6) {
    currentStep.value++

    if (currentStep.value === 5 && (!storageResult.value || !storageResult.value.success)) {
      ElMessage.warning('请先完成关系抽取并保存知识')
      currentStep.value = 4
    }
  } else if (!canProceed.value) {
    const messages = {
      1: '请先选择要分析的文档',
      2: '可以直接进入下一步，术语选择为可选项',
      3: '请先确认识别的实体',
      4: '请先抽取并选择关系（选择关系后即可进入下一步）',
      5: '请先完成知识存储'
    }
    ElMessage.warning(messages[currentStep.value] || '请完成当前步骤')
  }
}

const prevStep = () => {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

// 重置构建流程
const resetBuild = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要重新开始构建流程吗？这将清空所有当前数据。',
      '确认重置',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    currentStep.value = 1
    selectedDocument.value = null
    selectedTerms.value = []
    confirmedEntities.value = []
    confirmedRelations.value = []
    hasSelectedRelations.value = false
    storageResult.value = null
    knowledgeGraphData.value = null

    resetBuildStore()
    startBuild()

    ElMessage.success('已重置构建流程，可以重新开始')
  } catch {
    // 用户取消操作
  }
}

// 路由守卫
onBeforeRouteLeave(async (to, from, next) => {
  console.log('BuildView: onBeforeRouteLeave triggered', 'to:', to.path, 'from:', from.path)

  if (window.__buildViewLeavingLock) {
    console.log('BuildView: Already handling route leave, skipping')
    return
  }
  window.__buildViewLeavingLock = true

  const cleanup = () => {
    window.__buildViewLeavingLock = false
    resetBuildStore()
  }

  try {
    if (isProcessing.value) {
      try {
        await ElMessageBox.confirm(
          '当前有操作正在进行中，确定要离开吗？',
          '确认离开',
          {
            confirmButtonText: '确定离开',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        console.log('BuildView: User confirmed to leave during processing')
        cleanup()
        next()
      } catch (error) {
        console.log('BuildView: User cancelled leaving during processing:', error)
        window.__buildViewLeavingLock = false
        next(false)
      }
      return
    }

    const shouldShowConfirmation = shouldShowLeaveConfirmation() && !hasLoadedGraph()

    if (shouldShowConfirmation) {
      try {
        await ElMessageBox.confirm(
          '当前有未完成的构建流程，离开页面将丢失进度，确定要离开吗？',
          '确认离开',
          {
            confirmButtonText: '确定离开',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        console.log('BuildView: User confirmed to leave with unsaved data')
        cleanup()
        next()
      } catch (error) {
        console.log('BuildView: User cancelled leaving with unsaved data:', error)
        window.__buildViewLeavingLock = false
        next(false)
      }
      return
    }

    console.log('BuildView: Allowing navigation without confirmation')
    cleanup()
    next()
  } catch (error) {
    console.error('BuildView: Unexpected error in route guard:', error)
    cleanup()
    next()
  }
})

// 组件挂载时初始化
onMounted(() => {
  console.log('BuildView: Component mounted, starting build process')
  startBuild()
  const requestedDocumentId = Array.isArray(route.query.document_id)
    ? route.query.document_id[0]
    : route.query.document_id
  if (requestedDocumentId) {
    selectedDocument.value = {
      document_id: String(requestedDocumentId),
      name: String(requestedDocumentId)
    }
    currentStep.value = 6
  }
  updateBuildStep(currentStep.value)
})

// 监听数据变化
watch(currentStep, (newStep) => {
  updateBuildStep(newStep)

  if (newStep === 6 && knowledgeGraphData.value && knowledgeGraphData.value.nodes && knowledgeGraphData.value.nodes.length > 0) {
    completeBuild()
  }
}, { immediate: true })

watch(selectedDocument, (newDoc) => {
  updateBuildData('selectedDocument', newDoc)
}, { deep: true })

watch(selectedTerms, (newTerms) => {
  updateBuildData('selectedTerms', newTerms)
}, { deep: true })

watch(confirmedEntities, (newEntities) => {
  updateBuildData('confirmedEntities', newEntities)
}, { deep: true })

watch(confirmedRelations, (newRelations) => {
  updateBuildData('confirmedRelations', newRelations)
}, { deep: true })

watch(storageResult, (newResult) => {
  updateBuildData('storageResult', newResult)
}, { deep: true })

watch(knowledgeGraphData, (newGraphData) => {
  updateBuildData('knowledgeGraphData', newGraphData)

  if (newGraphData && newGraphData.nodes && newGraphData.nodes.length > 0 && currentStep.value === 6) {
    completeBuild()
  }
}, { deep: true })

// 组件卸载前清理
onBeforeUnmount(() => {
  console.log('BuildView: Component is being unmounted')
  isProcessing.value = false
  resetBuildStore()
})
</script>

<style scoped>
.build-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  width: 95%;
}

.build-header {
  text-align: center;
  margin: 0 auto 40px auto;
  max-width: 1200px;
}

.build-header h1 {
  margin: 0 0 12px 0;
  color: #303133;
  font-size: 32px;
  font-weight: 700;
}

.build-description {
  margin: 0;
  color: #606266;
  font-size: 16px;
  line-height: 1.5;
}

/* 新的自定义步骤指示器样式 */
.custom-steps-container {
  width: 100%;
  max-width: 1200px;
  margin: 30px auto 40px auto;
  padding: 20px 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  position: relative;
  gap: 10px;
  text-align: center;
}

.custom-step {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  z-index: 1;
  min-width: 0;
}

.custom-step.is-clickable {
  cursor: pointer;
  transition: transform 0.2s ease;
}

.custom-step.is-clickable:hover .step-circle {
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
}

.custom-step.is-clickable:hover .step-title {
  color: #409eff;
}

.step-circle {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background-color: #d3dce6;
  color: #909399;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 10px;
  transition: all 0.3s ease;
  border: 3px solid #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  flex-shrink: 0;
}

.custom-step.is-active .step-circle {
  background: linear-gradient(135deg, #409eff 0%, #5cadff 100%);
  color: #fff;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.4);
  animation: pulse 1.5s ease-in-out infinite;
}

.custom-step.is-completed .step-circle {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(103, 194, 58, 0.3);
}

.custom-step.is-completed .step-circle::after {
  content: '✓';
  font-size: 22px;
  position: absolute;
}

.custom-step.is-completed .step-number {
  display: none;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}



.step-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
  transition: color 0.3s ease;
  white-space: nowrap;
}

.custom-step.is-active .step-title {
  color: #409eff;
}

.custom-step.is-completed .step-title {
  color: #67c23a;
}

.step-description {
  font-size: 12px;
  color: #909399;
  line-height: 1.3;
  text-align: center;
  word-break: keep-all;
  white-space: normal;
}

.custom-step.is-active .step-description {
  color: #606266;
}

.step-line {
  position: absolute;
  top: 23px;
  left: 50%;
  width: 100%;
  height: 3px;
  background-color: #e4e7ed;
  z-index: -1;
  transition: background-color 0.3s ease;
}

.custom-step.is-completed .step-line {
  background: linear-gradient(90deg, #67c23a 0%, #85ce61 100%);
}

.step-content {
  margin: 30px auto;
  max-width: 1200px;
}

.step-panel {
  padding: 30px;
  border-radius: 12px;
  background-color: #fff;
  box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.08);
  border: 1px solid #e4e7ed;
  min-height: 400px;
  animation: fadeInUp 0.5s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.step-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 30px auto 40px auto;
  max-width: 1200px;
  padding: 20px 30px;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  border: 1px solid #e4e7ed;
}

.step-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.step-info .step-number {
  font-size: 18px;
  font-weight: 600;
  color: #409eff;
}

.step-info .step-title {
  font-size: 14px;
  color: #606266;
}

/* 知识存储步骤样式 */
.knowledge-storage {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 300px;
  justify-content: center;
}

.storage-header {
  text-align: center;
  margin-bottom: 30px;
}

.storage-header h3 {
  margin: 0 0 12px 0;
  color: #409eff;
  font-size: 24px;
}

.storage-header p {
  margin: 0;
  color: #606266;
  font-size: 16px;
}

.storage-summary {
  width: 100%;
  max-width: 600px;
}

.storage-details {
  margin-top: 20px;
}

.empty-storage {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

/* 按钮样式增强 */
.el-button--large {
  padding: 12px 24px;
  font-size: 16px;
  border-radius: 8px;
  font-weight: 500;
}

.el-button--large .el-icon {
  font-size: 18px;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .build-container {
    width: 100%;
    padding: 15px;
  }

  .step-panel {
    padding: 20px;
  }

  .custom-steps-container {
    padding: 30px 20px;
  }
}

@media (max-width: 768px) {
  .build-header h1 {
    font-size: 24px;
  }

  .build-description {
    font-size: 14px;
  }

  .custom-steps-container {
    padding: 20px 15px;
    flex-direction: column;
    gap: 20px;
  }

  .custom-step {
    flex-direction: row;
    width: 100%;
    justify-content: flex-start;
    align-items: center;
  }

  .step-circle {
    margin-right: 15px;
    margin-bottom: 0;
  }

  .step-content {
    text-align: left;
  }

  .step-description {
    max-width: none;
  }

  .step-line {
    display: none;
  }

  .step-actions {
    flex-direction: column;
    gap: 16px;
    padding: 16px;
  }

  .step-info {
    order: -1;
  }
}

@media (max-width: 480px) {
  .build-container {
    padding: 10px;
  }

  .step-panel {
    padding: 15px;
    margin: 15px 0;
  }

  .build-header h1 {
    font-size: 20px;
  }

  .step-circle {
    width: 40px;
    height: 40px;
    font-size: 16px;
  }

  .step-title {
    font-size: 14px;
  }

  .step-description {
    font-size: 12px;
  }
}

/* 成功状态样式 */
.el-result--success .el-result__icon svg {
  color: #67c23a;
}

.el-result--error .el-result__icon svg {
  color: #f56c6c;
}
</style>
