/**
 * 图谱构建状态管理器（异常52修复）
 * 用于跟踪图谱构建进度，实现页面跳转确认功能
 */

import { ref } from 'vue'

// 构建状态
const isBuildInProgress = ref(false)
const currentStep = ref(1)
const hasCompletedBuild = ref(false)
const buildData = ref({
  selectedDocument: null,
  selectedTerms: [],
  confirmedEntities: [],
  confirmedRelations: [],
  storageResult: null,
  knowledgeGraphData: null
})

// 开始构建流程
export function startBuild() {
  isBuildInProgress.value = true
  hasCompletedBuild.value = false
  currentStep.value = 1
  console.log('构建流程已开始')
}

// 更新构建步骤
export function updateBuildStep(step) {
  currentStep.value = step
  console.log(`构建步骤更新: ${step}`)
}

// 更新构建数据
export function updateBuildData(key, value) {
  buildData.value[key] = value
  console.log(`构建数据更新: ${key}`)
}

// 完成构建流程
export function completeBuild() {
  isBuildInProgress.value = false
  hasCompletedBuild.value = true
  console.log('构建流程已完成')
}

// 重置构建状态
export function resetBuild() {
  isBuildInProgress.value = false
  hasCompletedBuild.value = false
  currentStep.value = 1
  buildData.value = {
    selectedDocument: null,
    selectedTerms: [],
    confirmedEntities: [],
    confirmedRelations: [],
    storageResult: null,
    knowledgeGraphData: null
  }
  console.log('构建状态已重置')
}

// 检查是否需要显示离开确认
export function shouldShowLeaveConfirmation() {
  // 如果在构建过程中且还没完成，则显示确认
  return isBuildInProgress.value && !hasCompletedBuild.value
}

// 检查是否在图谱展示阶段且已加载图谱
export function hasLoadedGraph() {
  return currentStep.value === 6 && buildData.value.knowledgeGraphData !== null
}

// 导出状态
export function useBuildStore() {
  return {
    isBuildInProgress,
    currentStep,
    hasCompletedBuild,
    buildData,
    startBuild,
    updateBuildStep,
    updateBuildData,
    completeBuild,
    resetBuild,
    shouldShowLeaveConfirmation,
    hasLoadedGraph
  }
}