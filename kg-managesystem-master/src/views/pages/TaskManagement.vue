<template>
  <div class="task-page">
    <div class="page-header">
      <div>
        <h2>{{ t.title }}</h2>
        <p>{{ t.subtitle }}</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreateDialog">{{ t.create }}</el-button>
    </div>

    <div class="stats-grid">
      <div class="stat-panel"><span>{{ t.all }}</span><strong>{{ stats.total || 0 }}</strong></div>
      <div class="stat-panel"><span>{{ t.running }}</span><strong>{{ stats.by_status?.in_progress || 0 }}</strong></div>
      <div class="stat-panel"><span>{{ t.blocked }}</span><strong>{{ stats.by_status?.blocked || 0 }}</strong></div>
      <div class="stat-panel danger"><span>{{ t.overdue }}</span><strong>{{ stats.overdue || 0 }}</strong></div>
    </div>

    <div class="task-toolbar">
      <el-input v-model="filters.search" class="search-input" :placeholder="t.search" :prefix-icon="Search" clearable @keyup.enter="fetchTasks" @clear="fetchTasks" />
      <el-select v-model="filters.project_id" :placeholder="t.project" clearable filterable @change="refreshTasks">
        <el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>
      <el-select v-model="filters.status" :placeholder="t.status" clearable @change="refreshTasks">
        <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="filters.task_type" :placeholder="t.type" clearable @change="refreshTasks">
        <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-button :icon="Refresh" @click="refreshTasks">{{ t.refresh }}</el-button>
    </div>

    <div class="task-table-wrap">
      <el-table :data="taskList" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="title" :label="t.task" min-width="260">
          <template #default="scope">
            <div class="task-title-cell">
              <span class="task-title">{{ scope.row.title }}</span>
              <span class="task-desc">{{ scope.row.description || t.noDescription }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="project" :label="t.project" min-width="150" show-overflow-tooltip>
          <template #default="scope">{{ scope.row.project?.name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="template" :label="t.template" min-width="160" show-overflow-tooltip>
          <template #default="scope">{{ scope.row.template?.name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="task_type" :label="t.type" width="110">
          <template #default="scope">{{ typeMap[scope.row.task_type] || scope.row.task_type }}</template>
        </el-table-column>
        <el-table-column prop="priority" :label="t.priority" width="100" align="center">
          <template #default="scope"><el-tag :type="priorityTagType(scope.row.priority)" size="small">{{ priorityMap[scope.row.priority] }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="status" :label="t.status" width="135" align="center">
          <template #default="scope">
            <el-select v-model="scope.row.status" size="small" class="status-select" @change="changeStatus(scope.row)">
              <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column prop="assignee" :label="t.assignee" width="120" show-overflow-tooltip>
          <template #default="scope">{{ scope.row.assignee || '-' }}</template>
        </el-table-column>
        <el-table-column prop="due_date" :label="t.dueDate" width="165">
          <template #default="scope"><span :class="{ overdue: isOverdue(scope.row) }">{{ formatDate(scope.row.due_date) }}</span></template>
        </el-table-column>
        <el-table-column prop="related_document" :label="t.document" min-width="200" show-overflow-tooltip>
          <template #default="scope">{{ scope.row.related_document?.title || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t.actions" width="150" fixed="right" align="center">
          <template #default="scope">
            <el-button type="primary" link @click="openEditDialog(scope.row)">{{ t.edit }}</el-button>
            <el-button type="danger" link @click="deleteTask(scope.row)">{{ t.delete }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.per_page" :page-sizes="[10, 20, 50, 100]" :total="pagination.total" layout="total, sizes, prev, pager, next, jumper" background @size-change="handleSizeChange" @current-change="fetchTasks" />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingTaskId ? t.editTask : t.newTask" width="660px">
      <el-form ref="taskFormRef" :model="taskForm" :rules="rules" label-width="96px">
        <el-form-item :label="t.taskTitle" prop="title"><el-input v-model="taskForm.title" maxlength="120" show-word-limit /></el-form-item>
        <el-form-item :label="t.description"><el-input v-model="taskForm.description" type="textarea" :rows="4" maxlength="1000" show-word-limit /></el-form-item>
        <div class="form-grid">
          <el-form-item :label="t.project"><el-select v-model="taskForm.project_id" class="full-width" clearable filterable><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
          <el-form-item :label="t.template"><el-select v-model="taskForm.template_id" class="full-width" clearable filterable><el-option v-for="item in templates" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
          <el-form-item :label="t.type" prop="task_type"><el-select v-model="taskForm.task_type" class="full-width"><el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item :label="t.priority" prop="priority"><el-select v-model="taskForm.priority" class="full-width"><el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item :label="t.status" prop="status"><el-select v-model="taskForm.status" class="full-width"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item :label="t.assignee"><el-input v-model="taskForm.assignee" /></el-form-item>
        </div>
        <el-form-item :label="t.dueDate"><el-date-picker v-model="taskForm.due_date" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" class="full-width" /></el-form-item>
        <el-form-item :label="t.document">
          <el-select
            v-model="taskForm.related_document_id"
            class="full-width"
            clearable
            filterable
            remote
            reserve-keyword
            :remote-method="searchDocuments"
            :loading="documentLoading"
            :placeholder="t.documentPlaceholder"
          >
            <el-option
              v-for="item in documentOptions"
              :key="item.id"
              :label="formatDocumentLabel(item)"
              :value="item.id"
            >
              <div class="document-option">
                <span class="document-title">{{ item.display_title || item.file_name }}</span>
                <span class="document-meta">ID {{ item.id }} · {{ item.doi || item.recovered_doi || item.original_name || '无 DOI' }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t.cancel }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveTask">{{ t.save }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'

const API_BASE_URL = '/pdf'
const t = {
  title: '\u4efb\u52a1\u7ba1\u7406',
  subtitle: '\u8ddf\u8e2a\u6587\u732e\u6574\u7406\u3001\u56fe\u8c31\u6784\u5efa\u3001\u5ba1\u6838\u548c\u95ee\u7b54\u76f8\u5173\u5de5\u4f5c',
  create: '\u65b0\u5efa\u4efb\u52a1',
  all: '\u5168\u90e8\u4efb\u52a1',
  running: '\u8fdb\u884c\u4e2d',
  blocked: '\u5df2\u963b\u585e',
  overdue: '\u5df2\u903e\u671f',
  search: '\u641c\u7d22\u6807\u9898\u3001\u8bf4\u660e\u3001\u8d1f\u8d23\u4eba',
  project: '\u9879\u76ee',
  template: '\u6a21\u677f',
  status: '\u72b6\u6001',
  type: '\u7c7b\u578b',
  priority: '\u4f18\u5148\u7ea7',
  refresh: '\u5237\u65b0',
  task: '\u4efb\u52a1',
  noDescription: '\u65e0\u8bf4\u660e',
  assignee: '\u8d1f\u8d23\u4eba',
  dueDate: '\u622a\u6b62\u65f6\u95f4',
  document: '\u5173\u8054\u6587\u732e',
  documentId: '\u6587\u732eID',
  documentPlaceholder: '\u8f93\u5165\u6807\u9898\u3001DOI\u6216\u6587\u4ef6\u540d\u641c\u7d22\u6587\u732e',
  actions: '\u64cd\u4f5c',
  edit: '\u7f16\u8f91',
  delete: '\u5220\u9664',
  editTask: '\u7f16\u8f91\u4efb\u52a1',
  newTask: '\u65b0\u5efa\u4efb\u52a1',
  taskTitle: '\u4efb\u52a1\u6807\u9898',
  description: '\u4efb\u52a1\u8bf4\u660e',
  cancel: '\u53d6\u6d88',
  save: '\u4fdd\u5b58'
}

const statusOptions = [
  { label: '\u5f85\u5904\u7406', value: 'pending' },
  { label: '\u8fdb\u884c\u4e2d', value: 'in_progress' },
  { label: '\u5df2\u5b8c\u6210', value: 'done' },
  { label: '\u5df2\u963b\u585e', value: 'blocked' },
  { label: '\u5df2\u53d6\u6d88', value: 'cancelled' }
]
const priorityOptions = [
  { label: '\u4f4e', value: 'low' },
  { label: '\u4e2d', value: 'medium' },
  { label: '\u9ad8', value: 'high' },
  { label: '\u7d27\u6025', value: 'urgent' }
]
const typeOptions = [
  { label: '\u6587\u732e\u6574\u7406', value: 'literature' },
  { label: '\u56fe\u8c31\u6784\u5efa', value: 'kg_build' },
  { label: '\u6587\u6863\u5ba1\u6838', value: 'review' },
  { label: '\u77e5\u8bc6\u95ee\u7b54', value: 'qa' },
  { label: '\u7cfb\u7edf\u7ef4\u62a4', value: 'system' },
  { label: '\u5176\u4ed6', value: 'other' }
]
const priorityMap = Object.fromEntries(priorityOptions.map((item) => [item.value, item.label]))
const typeMap = Object.fromEntries(typeOptions.map((item) => [item.value, item.label]))

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingTaskId = ref(null)
const taskFormRef = ref(null)
const taskList = ref([])
const stats = ref({})
const projects = ref([])
const templates = ref([])
const documentOptions = ref([])
const documentLoading = ref(false)

const filters = reactive({ search: '', status: '', task_type: '', project_id: null })
const pagination = reactive({ page: 1, per_page: 10, total: 0 })
const taskForm = reactive({ title: '', description: '', task_type: 'literature', status: 'pending', priority: 'medium', assignee: '', due_date: '', related_document_id: null, project_id: null, template_id: null })
const rules = {
  title: [{ required: true, message: '\u8bf7\u8f93\u5165\u4efb\u52a1\u6807\u9898', trigger: 'blur' }],
  task_type: [{ required: true, message: '\u8bf7\u9009\u62e9\u4efb\u52a1\u7c7b\u578b', trigger: 'change' }],
  status: [{ required: true, message: '\u8bf7\u9009\u62e9\u72b6\u6001', trigger: 'change' }],
  priority: [{ required: true, message: '\u8bf7\u9009\u62e9\u4f18\u5148\u7ea7', trigger: 'change' }]
}

onMounted(() => {
  fetchStats()
  fetchProjects()
  fetchTemplates()
  fetchTasks()
})

const fetchStats = async () => {
  const response = await axios.get(`${API_BASE_URL}/tasks/stats`)
  if (response.data.status === 'success') stats.value = response.data.data
}
const fetchProjects = async () => {
  const response = await axios.get(`${API_BASE_URL}/projects`)
  if (response.data.status === 'success') projects.value = response.data.data.projects
}
const fetchTemplates = async () => {
  const response = await axios.get(`${API_BASE_URL}/task-templates`)
  if (response.data.status === 'success') templates.value = response.data.data.templates
}
const searchDocuments = async (query) => {
  const keyword = (query || '').trim()
  documentLoading.value = true
  try {
    const response = await axios.get(`${API_BASE_URL}/files`, {
      params: {
        search: keyword || undefined,
        page: 1,
        per_page: 20,
        sort: 'id_desc'
      }
    })
    if (response.data.status === 'success') {
      documentOptions.value = response.data.data.files
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('\u6587\u732e\u641c\u7d22\u5931\u8d25')
  } finally {
    documentLoading.value = false
  }
}
const fetchTasks = async () => {
  loading.value = true
  try {
    const response = await axios.get(`${API_BASE_URL}/tasks`, { params: { page: pagination.page, per_page: pagination.per_page, search: filters.search || undefined, status: filters.status || undefined, task_type: filters.task_type || undefined, project_id: filters.project_id || undefined } })
    if (response.data.status === 'success') {
      taskList.value = response.data.data.tasks
      pagination.total = response.data.data.pagination.total
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('\u4efb\u52a1\u5217\u8868\u52a0\u8f7d\u5931\u8d25')
  } finally {
    loading.value = false
  }
}
const refreshTasks = () => {
  pagination.page = 1
  fetchStats()
  fetchTasks()
}
const handleSizeChange = (size) => {
  pagination.per_page = size
  pagination.page = 1
  fetchTasks()
}
const resetForm = () => Object.assign(taskForm, { title: '', description: '', task_type: 'literature', status: 'pending', priority: 'medium', assignee: '', due_date: '', related_document_id: null, project_id: null, template_id: null })
const openCreateDialog = () => {
  editingTaskId.value = null
  resetForm()
  searchDocuments('')
  dialogVisible.value = true
}
const openEditDialog = (task) => {
  editingTaskId.value = task.id
  Object.assign(taskForm, { title: task.title, description: task.description || '', task_type: task.task_type, status: task.status, priority: task.priority, assignee: task.assignee || '', due_date: task.due_date ? task.due_date.slice(0, 19) : '', related_document_id: task.related_document_id || null, project_id: task.project_id || null, template_id: task.template_id || null })
  if (task.related_document) {
    documentOptions.value = [{
      id: task.related_document.id,
      display_title: task.related_document.title,
      file_name: task.related_document.title,
      original_name: task.related_document.original_name,
      doi: task.related_document.doi
    }]
  } else {
    searchDocuments('')
  }
  dialogVisible.value = true
}
const buildPayload = () => ({ ...taskForm, due_date: taskForm.due_date || null, related_document_id: taskForm.related_document_id || null, project_id: taskForm.project_id || null, template_id: taskForm.template_id || null })
const saveTask = async () => {
  await taskFormRef.value?.validate()
  saving.value = true
  try {
    if (editingTaskId.value) await axios.put(`${API_BASE_URL}/tasks/${editingTaskId.value}`, buildPayload())
    else await axios.post(`${API_BASE_URL}/tasks`, buildPayload())
    ElMessage.success('\u4efb\u52a1\u5df2\u4fdd\u5b58')
    dialogVisible.value = false
    refreshTasks()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '\u4efb\u52a1\u4fdd\u5b58\u5931\u8d25')
  } finally {
    saving.value = false
  }
}
const changeStatus = async (task) => {
  try {
    await axios.patch(`${API_BASE_URL}/tasks/${task.id}/status`, { status: task.status })
    fetchStats()
  } catch (error) {
    ElMessage.error('\u72b6\u6001\u66f4\u65b0\u5931\u8d25')
    fetchTasks()
  }
}
const deleteTask = async (task) => {
  try {
    await ElMessageBox.confirm(`\u786e\u5b9a\u5220\u9664\u4efb\u52a1\u201c${task.title}\u201d\u5417\uff1f`, '\u5220\u9664\u786e\u8ba4', { type: 'warning' })
    await axios.delete(`${API_BASE_URL}/tasks/${task.id}`)
    ElMessage.success('\u4efb\u52a1\u5df2\u5220\u9664')
    refreshTasks()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('\u4efb\u52a1\u5220\u9664\u5931\u8d25')
  }
}
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-') : '-'
const formatDocumentLabel = (item) => {
  const title = item.display_title || item.file_name || `文献 ${item.id}`
  const meta = item.doi || item.recovered_doi || item.original_name || item.es_code || ''
  return meta ? `${title}（${meta}）` : title
}
const isOverdue = (task) => task.due_date && !['done', 'cancelled'].includes(task.status) && new Date(task.due_date).getTime() < Date.now()
const priorityTagType = (priority) => ({ low: 'info', medium: '', high: 'warning', urgent: 'danger' }[priority] || '')
</script>

<style scoped>
.task-page { min-height: 100vh; padding: 24px; background: #f6f7f9; color: #303133; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.page-header p { margin: 6px 0 0; color: #606266; font-size: 13px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 16px; }
.stat-panel { display: flex; align-items: center; justify-content: space-between; min-height: 72px; padding: 16px 18px; border: 1px solid #e6ebf5; border-radius: 4px; background: #ffffff; }
.stat-panel span { color: #606266; font-size: 13px; }
.stat-panel strong { font-size: 28px; line-height: 1; color: #1f6feb; }
.stat-panel.danger strong, .overdue { color: #d93026; font-weight: 600; }
.task-toolbar { display: flex; gap: 10px; align-items: center; padding: 16px; margin-bottom: 16px; border: 1px solid #e6ebf5; border-radius: 4px; background: #ffffff; }
.search-input { width: 300px; }
.task-table-wrap { padding: 18px; border: 1px solid #e6ebf5; border-radius: 4px; background: #ffffff; }
.task-title-cell { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.task-title { font-weight: 600; color: #303133; }
.task-desc { color: #909399; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-select { width: 112px; }
.pagination-wrapper { display: flex; justify-content: flex-end; padding-top: 18px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 12px; }
.full-width { width: 100%; }
.document-option { display: flex; flex-direction: column; gap: 2px; min-width: 0; padding: 4px 0; }
.document-title { color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.document-meta { color: #909399; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 980px) { .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .task-toolbar { flex-wrap: wrap; } .search-input { width: 100%; } }
</style>
