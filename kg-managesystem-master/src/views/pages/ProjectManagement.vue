<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>{{ t.title }}</h2>
        <p>{{ t.subtitle }}</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openProjectDialog()">{{ t.createProject }}</el-button>
    </div>

    <div class="layout">
      <div class="left-pane">
        <div class="toolbar">
          <el-input v-model="projectSearch" :placeholder="t.searchProject" :prefix-icon="Search" clearable @keyup.enter="fetchProjects" @clear="fetchProjects" />
          <el-button :icon="Refresh" @click="fetchProjects">{{ t.refresh }}</el-button>
        </div>
        <el-table :data="projects" v-loading="loadingProjects" highlight-current-row stripe @row-click="selectProject">
          <el-table-column prop="name" :label="t.project" min-width="160" show-overflow-tooltip />
          <el-table-column prop="owner" :label="t.owner" width="90" show-overflow-tooltip />
          <el-table-column prop="task_count" :label="t.tasks" width="70" align="center" />
          <el-table-column :label="t.actions" width="120" align="center">
            <template #default="scope">
              <el-button type="primary" link @click.stop="openProjectDialog(scope.row)">{{ t.edit }}</el-button>
              <el-button type="danger" link @click.stop="deleteProject(scope.row)">{{ t.delete }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="right-pane">
        <template v-if="currentProject">
          <div class="project-summary">
            <div>
              <h3>{{ currentProject.name }}</h3>
              <p>{{ currentProject.description || t.noDescription }}</p>
            </div>
            <div class="summary-actions">
              <el-tag>{{ statusMap[currentProject.status] || currentProject.status }}</el-tag>
              <el-button type="primary" :icon="Upload" @click="openUploadTaskDialog('upload')">{{ t.uploadCreateTask }}</el-button>
              <el-button :icon="Link" @click="openUploadTaskDialog('existing')">{{ t.linkDocumentCreateTask }}</el-button>
              <el-button :icon="Refresh" @click="refreshCurrentProject">{{ t.refresh }}</el-button>
            </div>
          </div>

          <div class="stat-grid">
            <div class="stat"><span>{{ t.documents }}</span><strong>{{ overview.documents.length }}</strong></div>
            <div class="stat"><span>{{ t.tasks }}</span><strong>{{ overview.tasks.length }}</strong></div>
            <div class="stat"><span>{{ t.openTasks }}</span><strong>{{ currentProject.open_task_count || 0 }}</strong></div>
          </div>

          <div class="project-health">
            <div class="health-header">
              <span>{{ t.projectProgress }}</span>
              <strong>{{ projectProgress }}%</strong>
            </div>
            <el-progress :percentage="projectProgress" :status="projectProgress === 100 ? 'success' : undefined" />
            <div class="risk-tags">
              <el-tag :type="projectRisk.type">{{ projectRisk.label }}</el-tag>
              <el-tag type="info">待处理 {{ statusCount.pending || 0 }}</el-tag>
              <el-tag type="warning">进行中 {{ statusCount.in_progress || 0 }}</el-tag>
              <el-tag type="danger">阻塞 {{ statusCount.blocked || 0 }}</el-tag>
            </div>
          </div>

          <el-tabs v-model="activeTab" class="tabs">
            <el-tab-pane :label="t.resourceTab" name="documents">
              <el-table :data="overview.documents" stripe>
                <el-table-column prop="file_name" :label="t.document" min-width="260" show-overflow-tooltip />
                <el-table-column prop="doi" label="DOI" min-width="160" show-overflow-tooltip>
                  <template #default="scope">{{ scope.row.doi || scope.row.recovered_doi || '-' }}</template>
                </el-table-column>
                <el-table-column prop="upload_time" :label="t.uploadTime" width="170">
                  <template #default="scope">{{ formatDate(scope.row.upload_time) }}</template>
                </el-table-column>
                <el-table-column :label="t.actions" width="140" align="center">
                  <template #default="scope">
                    <el-button type="primary" link @click="previewDocument(scope.row)">{{ t.preview }}</el-button>
                    <el-button type="primary" link @click="downloadDocument(scope.row)">{{ t.download }}</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            <el-tab-pane :label="t.taskTab" name="tasks">
              <el-table :data="overview.tasks" stripe>
                <el-table-column prop="title" :label="t.task" min-width="240" show-overflow-tooltip />
                <el-table-column prop="status" :label="t.status" width="135">
                  <template #default="scope">
                    <el-select v-model="scope.row.status" size="small" class="status-select" @change="changeTaskStatus(scope.row)">
                      <el-option v-for="item in taskStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </template>
                </el-table-column>
                <el-table-column prop="template" :label="t.template" min-width="160" show-overflow-tooltip>
                  <template #default="scope">{{ scope.row.template?.name || '-' }}</template>
                </el-table-column>
                <el-table-column prop="related_document" :label="t.document" min-width="180" show-overflow-tooltip>
                  <template #default="scope">{{ scope.row.related_document?.title || '-' }}</template>
                </el-table-column>
                <el-table-column prop="assignee" :label="t.owner" width="110">
                  <template #default="scope">{{ scope.row.assignee || '-' }}</template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            <el-tab-pane :label="t.logTab" name="logs">
              <el-table :data="logs" v-loading="loadingLogs" stripe>
                <el-table-column prop="actor" :label="t.actor" width="100" />
                <el-table-column prop="action" :label="t.action" min-width="180" />
                <el-table-column prop="target_type" :label="t.target" width="110" />
                <el-table-column prop="detail" :label="t.detail" min-width="260" show-overflow-tooltip />
                <el-table-column prop="created_at" :label="t.time" width="170">
                  <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </template>
        <el-empty v-else :description="t.empty" />
      </div>
    </div>

    <el-dialog v-model="projectDialogVisible" :title="editingProjectId ? t.editProject : t.newProject" width="560px">
      <el-form ref="projectFormRef" :model="projectForm" :rules="projectRules" label-width="92px">
        <el-form-item :label="t.projectName" prop="name"><el-input v-model="projectForm.name" /></el-form-item>
        <el-form-item :label="t.description"><el-input v-model="projectForm.description" type="textarea" :rows="4" /></el-form-item>
        <el-form-item :label="t.owner"><el-input v-model="projectForm.owner" /></el-form-item>
        <el-form-item :label="t.status"><el-select v-model="projectForm.status" class="full-width"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="projectDialogVisible = false">{{ t.cancel }}</el-button>
        <el-button type="primary" :loading="savingProject" @click="saveProject">{{ t.save }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="uploadDialogVisible" :title="t.uploadCreateTask" width="680px">
      <el-form :model="uploadForm" label-width="100px">
        <el-form-item :label="t.source">
          <el-segmented v-model="uploadSource" :options="sourceOptions" />
        </el-form-item>
        <el-form-item v-if="uploadSource === 'upload'" :label="t.file"><el-upload ref="uploadRef" drag :auto-upload="false" :limit="1" :on-change="handleFileChange" :on-remove="handleFileRemove"><el-icon><Upload /></el-icon><div>{{ t.dropFile }}</div></el-upload></el-form-item>
        <el-form-item v-else :label="t.document">
          <el-select
            v-model="uploadForm.related_document_id"
            class="full-width"
            clearable
            filterable
            remote
            reserve-keyword
            :remote-method="searchDocuments"
            :loading="documentLoading"
            :placeholder="t.documentPlaceholder"
          >
            <el-option v-for="item in documentOptions" :key="item.id" :label="formatDocumentLabel(item)" :value="item.id">
              <div class="document-option">
                <span class="document-title">{{ item.display_title || item.file_name }}</span>
                <span class="document-meta">ID {{ item.id }} · {{ item.doi || item.recovered_doi || item.original_name || '无 DOI' }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item :label="t.taskTitle"><el-input v-model="uploadForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item :label="t.template"><el-select v-model="uploadForm.template_id" class="full-width" clearable filterable><el-option v-for="item in templates" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
          <el-form-item :label="t.taskType"><el-select v-model="uploadForm.task_type" class="full-width"><el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item :label="t.priority"><el-select v-model="uploadForm.priority" class="full-width"><el-option label="低" value="low" /><el-option label="中" value="medium" /><el-option label="高" value="high" /><el-option label="紧急" value="urgent" /></el-select></el-form-item>
          <el-form-item :label="t.owner"><el-input v-model="uploadForm.assignee" /></el-form-item>
        </div>
        <el-form-item :label="t.description"><el-input v-model="uploadForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">{{ t.cancel }}</el-button>
        <el-button type="primary" :loading="uploading" @click="uploadAndCreateTask">{{ t.submit }}</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="previewVisible" :title="previewDocumentTitle" size="80%">
      <iframe v-if="previewUrl" :src="previewUrl" class="preview-frame" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search, Upload, Link } from '@element-plus/icons-vue'

const API_BASE_URL = '/pdf'
const t = {
  title: '\u4efb\u52a1\u72b6\u6001\u4e0e\u9879\u76ee\u7ba1\u7406',
  subtitle: '\u7edf\u4e00\u7ba1\u7406\u9879\u76ee\u3001\u6587\u732e\u8d44\u6e90\u3001\u5173\u8054\u4efb\u52a1\u548c\u7528\u6237\u65e5\u5fd7',
  createProject: '\u65b0\u5efa\u9879\u76ee',
  searchProject: '\u641c\u7d22\u9879\u76ee',
  refresh: '\u5237\u65b0',
  project: '\u9879\u76ee',
  owner: '\u8d1f\u8d23\u4eba',
  tasks: '\u4efb\u52a1',
  actions: '\u64cd\u4f5c',
  edit: '\u7f16\u8f91',
  delete: '\u5220\u9664',
  noDescription: '\u65e0\u8bf4\u660e',
  uploadCreateTask: '\u4e0a\u4f20\u6587\u732e\u521b\u5efa\u4efb\u52a1',
  linkDocumentCreateTask: '\u5173\u8054\u5df2\u6709\u6587\u732e',
  documents: '\u6587\u732e\u8d44\u6e90',
  openTasks: '\u672a\u5b8c\u6210',
  resourceTab: '\u6587\u732e\u8d44\u6e90',
  taskTab: '\u5173\u8054\u4efb\u52a1',
  logTab: '\u7528\u6237\u65e5\u5fd7',
  document: '\u6587\u732e',
  uploadTime: '\u4e0a\u4f20\u65f6\u95f4',
  task: '\u4efb\u52a1',
  status: '\u72b6\u6001',
  template: '\u6a21\u677f',
  actor: '\u7528\u6237',
  action: '\u64cd\u4f5c',
  target: '\u5bf9\u8c61',
  detail: '\u8be6\u60c5',
  time: '\u65f6\u95f4',
  empty: '\u8bf7\u5148\u9009\u62e9\u6216\u521b\u5efa\u9879\u76ee',
  editProject: '\u7f16\u8f91\u9879\u76ee',
  newProject: '\u65b0\u5efa\u9879\u76ee',
  projectName: '\u9879\u76ee\u540d\u79f0',
  description: '\u8bf4\u660e',
  cancel: '\u53d6\u6d88',
  save: '\u4fdd\u5b58',
  file: '\u6587\u732e\u6587\u4ef6',
  dropFile: '\u62d6\u62fd\u6216\u70b9\u51fb\u9009\u62e9\u6587\u4ef6',
  taskTitle: '\u4efb\u52a1\u6807\u9898',
  taskType: '\u4efb\u52a1\u7c7b\u578b',
  priority: '\u4f18\u5148\u7ea7',
  source: '\u6587\u732e\u6765\u6e90',
  documentPlaceholder: '\u8f93\u5165\u6807\u9898\u3001DOI\u6216\u6587\u4ef6\u540d\u641c\u7d22\u6587\u732e',
  preview: '\u9884\u89c8',
  download: '\u4e0b\u8f7d',
  submit: '\u63d0\u4ea4'
}
const projectStatusOptions = [{ label: '\u8fdb\u884c\u4e2d', value: 'active' }, { label: '\u5df2\u6682\u505c', value: 'paused' }, { label: '\u5df2\u5f52\u6863', value: 'archived' }]
const statusMap = Object.fromEntries(projectStatusOptions.map((item) => [item.value, item.label]))
const taskStatusOptions = [{ label: '\u5f85\u5904\u7406', value: 'pending' }, { label: '\u8fdb\u884c\u4e2d', value: 'in_progress' }, { label: '\u5df2\u5b8c\u6210', value: 'done' }, { label: '\u5df2\u963b\u585e', value: 'blocked' }, { label: '\u5df2\u53d6\u6d88', value: 'cancelled' }]
const taskStatusMap = Object.fromEntries(taskStatusOptions.map((item) => [item.value, item.label]))
const sourceOptions = [{ label: '\u4e0a\u4f20\u65b0\u6587\u732e', value: 'upload' }, { label: '\u5173\u8054\u5df2\u6709\u6587\u732e', value: 'existing' }]
const typeOptions = [{ label: '\u6587\u732e\u6574\u7406', value: 'literature' }, { label: '\u56fe\u8c31\u6784\u5efa', value: 'kg_build' }, { label: '\u6587\u6863\u5ba1\u6838', value: 'review' }, { label: '\u77e5\u8bc6\u95ee\u7b54', value: 'qa' }, { label: '\u7cfb\u7edf\u7ef4\u62a4', value: 'system' }, { label: '\u5176\u4ed6', value: 'other' }]

const projects = ref([])
const templates = ref([])
const overview = reactive({ documents: [], tasks: [] })
const logs = ref([])
const documentOptions = ref([])
const currentProject = ref(null)
const activeTab = ref('documents')
const projectSearch = ref('')
const loadingProjects = ref(false)
const loadingLogs = ref(false)
const documentLoading = ref(false)
const projectDialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const previewVisible = ref(false)
const previewUrl = ref('')
const previewDocumentTitle = ref('')
const savingProject = ref(false)
const uploading = ref(false)
const editingProjectId = ref(null)
const uploadSource = ref('upload')
const uploadFile = ref(null)
const uploadRef = ref(null)
const projectFormRef = ref(null)
const projectForm = reactive({ name: '', description: '', owner: '', status: 'active' })
const uploadForm = reactive({ title: '', description: '', task_type: 'literature', priority: 'medium', assignee: '', template_id: null, related_document_id: null })
const projectRules = { name: [{ required: true, message: '\u8bf7\u8f93\u5165\u9879\u76ee\u540d\u79f0', trigger: 'blur' }] }
const statusCount = computed(() => overview.tasks.reduce((acc, task) => {
  acc[task.status] = (acc[task.status] || 0) + 1
  return acc
}, { pending: 0, in_progress: 0, done: 0, blocked: 0, cancelled: 0 }))
const projectProgress = computed(() => {
  const effectiveTasks = overview.tasks.filter((task) => task.status !== 'cancelled')
  if (!effectiveTasks.length) return 0
  return Math.round((statusCount.value.done || 0) * 100 / effectiveTasks.length)
})
const projectRisk = computed(() => {
  if ((statusCount.value.blocked || 0) > 0) return { label: '存在阻塞', type: 'danger' }
  if ((statusCount.value.pending || 0) > (statusCount.value.done || 0)) return { label: '待处理较多', type: 'warning' }
  if (projectProgress.value === 100) return { label: '已完成', type: 'success' }
  return { label: '进展正常', type: 'primary' }
})

onMounted(() => {
  fetchProjects()
  fetchTemplates()
  fetchLogs()
})
const fetchProjects = async () => {
  loadingProjects.value = true
  try {
    const response = await axios.get(`${API_BASE_URL}/projects`, { params: { search: projectSearch.value || undefined } })
    if (response.data.status === 'success') {
      projects.value = response.data.data.projects
      if (!currentProject.value && projects.value.length) selectProject(projects.value[0])
    }
  } finally {
    loadingProjects.value = false
  }
}
const fetchTemplates = async () => {
  const response = await axios.get(`${API_BASE_URL}/task-templates`)
  if (response.data.status === 'success') templates.value = response.data.data.templates
}
const selectProject = async (project) => {
  currentProject.value = project
  const response = await axios.get(`${API_BASE_URL}/projects/${project.id}/overview`)
  if (response.data.status === 'success') {
    Object.assign(overview, { documents: response.data.data.documents, tasks: response.data.data.tasks })
    currentProject.value = response.data.data.project
    fetchLogs()
  }
}
const fetchLogs = async () => {
  loadingLogs.value = true
  try {
    const params = currentProject.value
      ? { page: 1, per_page: 50, target_type: 'project', target_id: currentProject.value.id }
      : { page: 1, per_page: 50 }
    const response = await axios.get(`${API_BASE_URL}/logs`, { params })
    if (response.data.status === 'success') logs.value = response.data.data.logs
  } finally {
    loadingLogs.value = false
  }
}
const refreshCurrentProject = async () => {
  if (!currentProject.value) return
  await selectProject(currentProject.value)
}
const openUploadTaskDialog = (source = 'upload') => {
  uploadSource.value = source
  Object.assign(uploadForm, { title: '', description: '', task_type: 'literature', priority: 'medium', assignee: '', template_id: null, related_document_id: null })
  uploadFile.value = null
  uploadRef.value?.clearFiles()
  uploadDialogVisible.value = true
  if (source === 'existing') searchDocuments('')
}
const searchDocuments = async (query) => {
  const keyword = (query || '').trim()
  documentLoading.value = true
  try {
    const response = await axios.get(`${API_BASE_URL}/files`, { params: { search: keyword || undefined, page: 1, per_page: 20, sort: 'id_asc' } })
    if (response.data.status === 'success') documentOptions.value = response.data.data.files
  } catch (error) {
    ElMessage.error('\u6587\u732e\u641c\u7d22\u5931\u8d25')
  } finally {
    documentLoading.value = false
  }
}
const openProjectDialog = (project) => {
  editingProjectId.value = project?.id || null
  Object.assign(projectForm, project ? { name: project.name, description: project.description || '', owner: project.owner || '', status: project.status } : { name: '', description: '', owner: '', status: 'active' })
  projectDialogVisible.value = true
}
const saveProject = async () => {
  await projectFormRef.value?.validate()
  savingProject.value = true
  try {
    if (editingProjectId.value) await axios.put(`${API_BASE_URL}/projects/${editingProjectId.value}`, projectForm)
    else await axios.post(`${API_BASE_URL}/projects`, projectForm)
    ElMessage.success('\u9879\u76ee\u5df2\u4fdd\u5b58')
    projectDialogVisible.value = false
    await fetchProjects()
    fetchLogs()
  } finally {
    savingProject.value = false
  }
}
const deleteProject = async (project) => {
  try {
    await ElMessageBox.confirm(`\u786e\u5b9a\u5220\u9664\u9879\u76ee\u201c${project.name}\u201d\u5417\uff1f`, '\u5220\u9664\u786e\u8ba4', { type: 'warning' })
    await axios.delete(`${API_BASE_URL}/projects/${project.id}`)
    ElMessage.success('\u9879\u76ee\u5df2\u5220\u9664')
    currentProject.value = null
    Object.assign(overview, { documents: [], tasks: [] })
    fetchProjects()
    fetchLogs()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('\u9879\u76ee\u5220\u9664\u5931\u8d25')
  }
}
const handleFileChange = (file) => { uploadFile.value = file.raw }
const handleFileRemove = () => { uploadFile.value = null }
const uploadAndCreateTask = async () => {
  if (!currentProject.value) {
    ElMessage.warning('\u8bf7\u5148\u9009\u62e9\u9879\u76ee')
    return
  }
  if (uploadSource.value === 'upload' && !uploadFile.value) {
    ElMessage.warning('\u8bf7\u5148\u9009\u62e9\u6587\u4ef6')
    return
  }
  if (uploadSource.value === 'existing' && !uploadForm.related_document_id) {
    ElMessage.warning('\u8bf7\u5148\u9009\u62e9\u5df2\u6709\u6587\u732e')
    return
  }
  uploading.value = true
  try {
    const data = new FormData()
    if (uploadSource.value === 'upload') data.append('file', uploadFile.value)
    Object.entries(uploadForm).forEach(([key, value]) => { if (value !== null && value !== '') data.append(key, value) })
    await axios.post(`${API_BASE_URL}/projects/${currentProject.value.id}/upload-task`, data)
    ElMessage.success(uploadSource.value === 'upload' ? '\u5df2\u4e0a\u4f20\u6587\u732e\u5e76\u521b\u5efa\u4efb\u52a1' : '\u5df2\u5173\u8054\u6587\u732e\u5e76\u521b\u5efa\u4efb\u52a1')
    uploadDialogVisible.value = false
    uploadRef.value?.clearFiles()
    uploadFile.value = null
    await selectProject(currentProject.value)
    fetchLogs()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '\u4e0a\u4f20\u521b\u5efa\u4efb\u52a1\u5931\u8d25')
  } finally {
    uploading.value = false
  }
}
const changeTaskStatus = async (task) => {
  try {
    await axios.patch(`${API_BASE_URL}/tasks/${task.id}/status`, { status: task.status })
    ElMessage.success('\u4efb\u52a1\u72b6\u6001\u5df2\u66f4\u65b0')
    await refreshCurrentProject()
  } catch (error) {
    ElMessage.error('\u4efb\u52a1\u72b6\u6001\u66f4\u65b0\u5931\u8d25')
    refreshCurrentProject()
  }
}
const previewDocument = (document) => {
  previewDocumentTitle.value = document.display_title || document.file_name
  previewUrl.value = `${API_BASE_URL}/files/${document.repository}/${document.id}/preview`
  previewVisible.value = true
}
const downloadDocument = async (document) => {
  const response = await axios.get(`${API_BASE_URL}/files/${document.repository}/${document.id}/download`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = window.document.createElement('a')
  link.href = url
  link.download = document.file_name
  window.document.body.appendChild(link)
  link.click()
  window.URL.revokeObjectURL(url)
  window.document.body.removeChild(link)
}
const formatDocumentLabel = (item) => {
  const title = item.display_title || item.file_name || `文献 ${item.id}`
  const meta = item.doi || item.recovered_doi || item.original_name || item.es_code || ''
  return meta ? `${title}（${meta}）` : title
}
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-') : '-'
</script>

<style scoped>
.page { min-height: 100vh; padding: 24px; background: #f6f7f9; color: #303133; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.page-header p { margin: 6px 0 0; color: #606266; font-size: 13px; }
.layout { display: grid; grid-template-columns: 420px minmax(0, 1fr); gap: 16px; }
.left-pane, .right-pane { background: #fff; border: 1px solid #e6ebf5; border-radius: 4px; padding: 16px; min-height: 680px; }
.toolbar { display: flex; gap: 10px; margin-bottom: 14px; }
.project-summary { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; padding-bottom: 14px; border-bottom: 1px solid #eef0f5; }
.project-summary h3 { margin: 0 0 6px; font-size: 18px; }
.project-summary p { margin: 0; color: #606266; }
.summary-actions { display: flex; gap: 10px; align-items: center; }
.stat-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 16px 0; }
.stat { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: #f8fafc; border: 1px solid #e6ebf5; border-radius: 4px; }
.stat span { color: #606266; font-size: 13px; }
.stat strong { font-size: 24px; color: #1f6feb; }
.project-health { margin: 0 0 16px; padding: 16px; border: 1px solid #e6ebf5; border-radius: 4px; background: #fbfcfe; }
.health-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; color: #303133; font-weight: 600; }
.risk-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.tabs { margin-top: 8px; }
.status-select { width: 112px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 12px; }
.full-width { width: 100%; }
.document-option { display: flex; flex-direction: column; gap: 2px; min-width: 0; padding: 4px 0; }
.document-title { color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.document-meta { color: #909399; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview-frame { width: 100%; height: calc(100vh - 110px); border: none; }
@media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } }
</style>
