<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>{{ t.title }}</h2>
        <p>{{ t.subtitle }}</p>
      </div>
      <div class="header-actions">
        <el-upload :show-file-list="false" accept=".json" :http-request="importTemplate">
          <el-button :icon="Upload">{{ t.import }}</el-button>
        </el-upload>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">{{ t.create }}</el-button>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card"><span>{{ t.totalTemplates }}</span><strong>{{ stats.total || 0 }}</strong></div>
      <div class="stat-card"><span>{{ t.builtinTemplates }}</span><strong>{{ stats.builtin || 0 }}</strong></div>
      <div class="stat-card"><span>{{ t.customTemplates }}</span><strong>{{ stats.custom || 0 }}</strong></div>
      <div class="stat-card"><span>{{ t.avgFields }}</span><strong>{{ stats.avg_fields || 0 }}</strong></div>
    </div>

    <div class="innovation-panel">
      <div>
        <h3>{{ t.innovationTitle }}</h3>
        <p>{{ t.innovationSubtitle }}</p>
      </div>
        <div class="innovation-actions">
          <el-button :icon="MagicStick" @click="openSuggestionDrawer">{{ t.viewIdeas }}</el-button>
          <el-button type="primary" :icon="DocumentAdd" @click="applyIdeaPreset('processChain')">{{ t.generateProcessTemplate }}</el-button>
          <el-button :icon="Aim" @click="applyIdeaPreset('evidence')">{{ t.generateEvidenceTemplate }}</el-button>
          <el-button :icon="CopyDocument" @click="openCloneDialog">{{ t.cloneTemplate }}</el-button>
        </div>
      </div>

    <div class="toolbar">
      <el-input v-model="filters.search" class="search-input" :placeholder="t.search" :prefix-icon="Search" clearable @keyup.enter="fetchTemplates" @clear="fetchTemplates" />
      <el-select v-model="filters.task_type" :placeholder="t.type" clearable @change="fetchTemplates">
        <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-button :icon="Refresh" @click="fetchTemplates">{{ t.refresh }}</el-button>
    </div>

    <div class="table-wrap">
        <el-table :data="templates" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="name" :label="t.name" min-width="220" show-overflow-tooltip />
        <el-table-column prop="code" :label="t.code" min-width="190" show-overflow-tooltip />
        <el-table-column prop="task_type" :label="t.type" width="130">
          <template #default="scope">{{ typeMap[scope.row.task_type] || scope.row.task_type }}</template>
        </el-table-column>
        <el-table-column prop="is_builtin" :label="t.source" width="110" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.is_builtin ? 'success' : 'info'" size="small">{{ scope.row.is_builtin ? t.builtin : t.custom }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="fields_count" :label="t.fieldsCount" width="100" align="center" />
        <el-table-column :label="t.quality" width="120" align="center">
          <template #default="scope">
            <el-tag :type="getQuality(scope.row).type" size="small">{{ getQuality(scope.row).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t.level" width="120" align="center">
          <template #default="scope">
            <el-tag :type="getTemplateLevel(scope.row).type" size="small">{{ getTemplateLevel(scope.row).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" :label="t.description" min-width="260" show-overflow-tooltip />
        <el-table-column prop="updated_at" :label="t.updatedAt" width="170">
          <template #default="scope">{{ formatDate(scope.row.updated_at) }}</template>
        </el-table-column>
        <el-table-column :label="t.actions" width="210" fixed="right" align="center">
          <template #default="scope">
            <el-button type="primary" link :disabled="scope.row.is_builtin" @click="openEditDialog(scope.row)">{{ t.edit }}</el-button>
            <el-button type="primary" link @click="openPreview(scope.row)">{{ t.preview }}</el-button>
            <el-button type="primary" link @click="openCloneDialog(scope.row)">{{ t.clone }}</el-button>
            <el-button type="primary" link @click="exportTemplate(scope.row)">{{ t.export }}</el-button>
            <el-button type="danger" link :disabled="scope.row.is_builtin" @click="deleteTemplate(scope.row)">{{ t.delete }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? t.editTemplate : t.newTemplate" width="760px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <div class="form-grid">
          <el-form-item :label="t.name" prop="name"><el-input v-model="form.name" /></el-form-item>
          <el-form-item :label="t.code" prop="code"><el-input v-model="form.code" /></el-form-item>
          <el-form-item :label="t.type" prop="task_type">
            <el-select v-model="form.task_type" class="full-width"><el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
          </el-form-item>
          <el-form-item :label="t.createdBy"><el-input v-model="form.created_by" /></el-form-item>
        </div>
        <el-form-item :label="t.description"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item :label="t.schema" prop="schemaText">
          <el-input v-model="form.schemaText" type="textarea" :rows="12" class="mono" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t.cancel }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveTemplate">{{ t.save }}</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="previewVisible" :title="previewTemplate?.name || t.preview" size="46%">
      <div v-if="previewTemplate" class="preview-panel">
        <div class="preview-meta">
          <el-tag>{{ typeMap[previewTemplate.task_type] || previewTemplate.task_type }}</el-tag>
          <el-tag :type="previewTemplate.is_builtin ? 'success' : 'info'">{{ previewTemplate.is_builtin ? t.builtin : t.custom }}</el-tag>
          <el-tag type="warning">{{ t.fieldsCount }} {{ previewTemplate.fields_count || 0 }}</el-tag>
        </div>
        <p class="preview-desc">{{ previewTemplate.description || t.noDescription }}</p>
        <el-table :data="getTemplateFields(previewTemplate)" stripe>
          <el-table-column prop="key" label="Key" min-width="150" show-overflow-tooltip />
          <el-table-column prop="label" :label="t.fieldLabel" min-width="150" show-overflow-tooltip />
          <el-table-column prop="type" :label="t.fieldType" width="100" />
          <el-table-column prop="required" :label="t.required" width="90" align="center">
            <template #default="scope"><el-tag size="small" :type="scope.row.required ? 'danger' : 'info'">{{ scope.row.required ? t.yes : t.no }}</el-tag></template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>

    <el-drawer v-model="suggestionVisible" :title="t.viewIdeas" size="42%">
      <div class="idea-list">
        <div v-for="idea in literatureIdeas" :key="idea.title" class="idea-item">
          <div class="idea-title">{{ idea.title }}</div>
          <p>{{ idea.description }}</p>
          <div class="idea-tags"><el-tag v-for="tag in idea.tags" :key="tag" size="small">{{ tag }}</el-tag></div>
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="cloneDialogVisible" :title="t.cloneTemplate" width="640px">
      <el-form :model="cloneForm" label-width="96px">
        <el-form-item :label="t.baseTemplate">
          <el-select v-model="cloneForm.base_id" class="full-width" filterable clearable @change="syncCloneBase">
            <el-option v-for="item in templates" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t.newName">
          <el-input v-model="cloneForm.name" />
        </el-form-item>
        <el-form-item :label="t.newCode">
          <el-input v-model="cloneForm.code" />
        </el-form-item>
        <el-form-item :label="t.newDesc">
          <el-input v-model="cloneForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cloneDialogVisible = false">{{ t.cancel }}</el-button>
        <el-button type="primary" @click="createCloneTemplate">{{ t.save }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Aim, CopyDocument, DocumentAdd, MagicStick, Plus, Refresh, Search, Upload } from '@element-plus/icons-vue'

const API_BASE_URL = '/pdf'
const t = {
  title: '\u4efb\u52a1\u6a21\u677f\u7ba1\u7406',
  subtitle: '\u7ba1\u7406\u9884\u7f6e\u548c\u81ea\u5b9a\u4e49\u63d0\u53d6\u6a21\u677f\uff0c\u652f\u6491\u79d1\u7814\u4efb\u52a1\u914d\u7f6e\u590d\u7528',
  import: '\u5bfc\u5165\u6a21\u677f',
  create: '\u65b0\u5efa\u6a21\u677f',
  search: '\u641c\u7d22\u540d\u79f0\u3001\u7f16\u7801\u3001\u8bf4\u660e',
  type: '\u4efb\u52a1\u7c7b\u578b',
  refresh: '\u5237\u65b0',
  name: '\u6a21\u677f\u540d\u79f0',
  code: '\u6a21\u677f\u7f16\u7801',
  source: '\u6765\u6e90',
  builtin: '\u9884\u7f6e',
  custom: '\u81ea\u5b9a\u4e49',
  description: '\u8bf4\u660e',
  updatedAt: '\u66f4\u65b0\u65f6\u95f4',
  totalTemplates: '\u6a21\u677f\u603b\u6570',
  builtinTemplates: '\u9884\u7f6e\u6a21\u677f',
  customTemplates: '\u81ea\u5b9a\u4e49',
  avgFields: '\u5e73\u5747\u5b57\u6bb5',
  fieldsCount: '\u5b57\u6bb5\u6570',
  quality: '\u4f53\u68c0',
  level: '\u7ea7\u522b',
  innovationTitle: '\u6587\u732e\u542f\u53d1\u7684\u6a21\u677f\u521b\u65b0',
  innovationSubtitle: '\u5f15\u5165\u8bc1\u636e\u94fe\u3001\u7f6e\u4fe1\u5ea6\u3001\u5de5\u827a-\u7ed3\u6784-\u6027\u80fd\u5173\u7cfb\u548c\u81ea\u9002\u5e94\u8ffd\u95ee\u5b57\u6bb5\uff0c\u8ba9\u6a21\u677f\u66f4\u9002\u5408\u79d1\u7814\u62bd\u53d6\u4e0e\u4eba\u5de5\u590d\u6838\u3002',
  viewIdeas: '\u67e5\u770b\u521b\u65b0\u70b9',
  generateProcessTemplate: '\u751f\u6210\u5de5\u827a\u94fe\u6a21\u677f',
  generateEvidenceTemplate: '\u751f\u6210\u8bc1\u636e\u94fe\u6a21\u677f',
  cloneTemplate: '\u514b\u968f\u6a21\u677f',
  clone: '\u514b\u968f',
  baseTemplate: '\u57fa\u7840\u6a21\u677f',
  newName: '\u65b0\u540d\u79f0',
  newCode: '\u65b0\u7f16\u7801',
  newDesc: '\u65b0\u8bf4\u660e',
  actions: '\u64cd\u4f5c',
  edit: '\u7f16\u8f91',
  preview: '\u9884\u89c8',
  export: '\u5bfc\u51fa',
  delete: '\u5220\u9664',
  editTemplate: '\u7f16\u8f91\u6a21\u677f',
  newTemplate: '\u65b0\u5efa\u6a21\u677f',
  createdBy: '\u521b\u5efa\u4eba',
  schema: 'JSON Schema',
  noDescription: '\u65e0\u8bf4\u660e',
  fieldLabel: '\u5b57\u6bb5\u540d',
  fieldType: '\u7c7b\u578b',
  required: '\u5fc5\u586b',
  yes: '\u662f',
  no: '\u5426',
  cancel: '\u53d6\u6d88',
  save: '\u4fdd\u5b58'
}
const typeOptions = [
  { label: '\u6587\u732e\u6574\u7406', value: 'literature' },
  { label: '\u56fe\u8c31\u6784\u5efa', value: 'kg_build' },
  { label: '\u6587\u6863\u5ba1\u6838', value: 'review' },
  { label: '\u77e5\u8bc6\u95ee\u7b54', value: 'qa' },
  { label: '\u7cfb\u7edf\u7ef4\u62a4', value: 'system' },
  { label: '\u5176\u4ed6', value: 'other' }
]
const typeMap = Object.fromEntries(typeOptions.map((item) => [item.value, item.label]))
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const previewVisible = ref(false)
const suggestionVisible = ref(false)
const cloneDialogVisible = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const templates = ref([])
const previewTemplate = ref(null)
const cloneForm = ref({ base_id: null, name: '', code: '', description: '' })
const stats = ref({})
const filters = reactive({ search: '', task_type: '' })
const form = reactive({ name: '', code: '', description: '', task_type: 'literature', created_by: 'admin', schemaText: '{\n  "fields": []\n}' })
const rules = {
  name: [{ required: true, message: '\u8bf7\u8f93\u5165\u6a21\u677f\u540d\u79f0', trigger: 'blur' }],
  code: [{ required: true, message: '\u8bf7\u8f93\u5165\u6a21\u677f\u7f16\u7801', trigger: 'blur' }],
  task_type: [{ required: true, message: '\u8bf7\u9009\u62e9\u4efb\u52a1\u7c7b\u578b', trigger: 'change' }]
}

const literatureIdeas = [
  {
    title: '证据链 + 置信度字段',
    description: '信息抽取结果不只保存答案，还保存证据句、页码和置信度，方便人工审核优先处理低置信度或冲突样本。',
    tags: ['human-in-the-loop', 'confidence', 'review']
  },
  {
    title: '工艺-结构-性能链式模板',
    description: '陶瓷材料论文常围绕制备工艺、微观结构和性能指标展开，模板可直接表达链式关系，便于后续知识图谱建边。',
    tags: ['relation extraction', 'ceramic', 'knowledge graph']
  },
  {
    title: '自适应追问字段',
    description: '当 DOI、单位、性能数值或证据缺失时，模板自动保留追问项，形成半自动补全和复核流程。',
    tags: ['active learning', 'missing fields', 'annotation']
  }
]

onMounted(() => {
  fetchTemplates()
  fetchStats()
})

const fetchTemplates = async () => {
  loading.value = true
  try {
    const response = await axios.get(`${API_BASE_URL}/task-templates`, { params: { search: filters.search || undefined, task_type: filters.task_type || undefined } })
    if (response.data.status === 'success') templates.value = response.data.data.templates
  } catch (error) {
    ElMessage.error('\u6a21\u677f\u5217\u8868\u52a0\u8f7d\u5931\u8d25')
  } finally {
    loading.value = false
  }
}
const fetchStats = async () => {
  const response = await axios.get(`${API_BASE_URL}/task-templates/stats`)
  if (response.data.status === 'success') stats.value = response.data.data
}
const resetForm = () => Object.assign(form, { name: '', code: '', description: '', task_type: 'literature', created_by: 'admin', schemaText: '{\n  "fields": []\n}' })
const openCreateDialog = () => {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}
const openSuggestionDrawer = () => { suggestionVisible.value = true }
const openPreview = (row) => {
  previewTemplate.value = row
  previewVisible.value = true
}
const openCloneDialog = (row = null) => {
  if (row) {
    cloneForm.value = {
      base_id: row.id,
      name: `${row.name} - 派生版`,
      code: `${row.code}_derived`,
      description: row.description || ''
    }
  } else {
    cloneForm.value = { base_id: null, name: '', code: '', description: '' }
  }
  cloneDialogVisible.value = true
}
const syncCloneBase = (baseId) => {
  const base = templates.value.find((item) => item.id === baseId)
  if (!base) return
  cloneForm.value.name = `${base.name} - 派生版`
  cloneForm.value.code = `${base.code}_derived`
  cloneForm.value.description = base.description || ''
}
const getTemplateFields = (template) => Array.isArray(template?.schema?.fields) ? template.schema.fields : []
const getQuality = (template) => {
  const fields = getTemplateFields(template)
  const hasEvidence = fields.some((field) => ['evidence_sentence', 'page', 'confidence'].includes(field.key))
  if (hasEvidence) return { label: '\u5ba1\u6838\u53cb\u597d', type: 'success' }
  if (fields.length >= 5) return { label: '\u5b8c\u6574', type: 'primary' }
  return { label: '\u5f85\u5b8c\u5584', type: 'warning' }
}
const getTemplateLevel = (template) => {
  const fields = getTemplateFields(template)
  const meta = template?.schema?.meta || {}
  if (meta.tags?.includes('relation-extraction')) return { label: '链式抽取', type: 'success' }
  if (meta.tags?.includes('human-in-the-loop')) return { label: '人工审核', type: 'warning' }
  if (fields.length > 8) return { label: '高复杂度', type: 'danger' }
  return { label: '基础模板', type: 'info' }
}
const applyIdeaPreset = (type) => {
  editingId.value = null
  const preset = ideaPresets[type]
  Object.assign(form, {
    name: preset.name,
    code: `${preset.code}_${Date.now().toString().slice(-5)}`,
    description: preset.description,
    task_type: preset.task_type,
    created_by: 'admin',
    schemaText: JSON.stringify(preset.schema, null, 2)
  })
  dialogVisible.value = true
}
const createCloneTemplate = async () => {
  try {
    const base = templates.value.find((item) => item.id === cloneForm.value.base_id)
    if (!base) throw new Error('请选择基础模板')
    await axios.post(`${API_BASE_URL}/task-templates`, {
      name: cloneForm.value.name,
      code: cloneForm.value.code,
      description: cloneForm.value.description,
      task_type: base.task_type,
      created_by: 'admin',
      schema: base.schema
    })
    ElMessage.success('派生模板已创建')
    cloneDialogVisible.value = false
    fetchTemplates()
    fetchStats()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || error.message || '创建派生模板失败')
  }
}
const openEditDialog = (row) => {
  editingId.value = row.id
  Object.assign(form, { name: row.name, code: row.code, description: row.description || '', task_type: row.task_type, created_by: row.created_by || 'admin', schemaText: JSON.stringify(row.schema || { fields: [] }, null, 2) })
  dialogVisible.value = true
}
const buildPayload = () => {
  let schema
  try {
    schema = JSON.parse(form.schemaText || '{}')
  } catch (error) {
    throw new Error('\u6a21\u677f JSON \u683c\u5f0f\u4e0d\u6b63\u786e')
  }
  return { name: form.name, code: form.code, description: form.description, task_type: form.task_type, created_by: form.created_by, schema }
}
const saveTemplate = async () => {
  await formRef.value?.validate()
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value) await axios.put(`${API_BASE_URL}/task-templates/${editingId.value}`, payload)
    else await axios.post(`${API_BASE_URL}/task-templates`, payload)
    ElMessage.success('\u6a21\u677f\u5df2\u4fdd\u5b58')
    dialogVisible.value = false
    fetchTemplates()
    fetchStats()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || error.message || '\u6a21\u677f\u4fdd\u5b58\u5931\u8d25')
  } finally {
    saving.value = false
  }
}
const importTemplate = async ({ file }) => {
  const data = new FormData()
  data.append('file', file)
  try {
    await axios.post(`${API_BASE_URL}/task-templates/import`, data)
    ElMessage.success('\u6a21\u677f\u5df2\u5bfc\u5165')
    fetchTemplates()
    fetchStats()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '\u6a21\u677f\u5bfc\u5165\u5931\u8d25')
  }
}
const exportTemplate = async (row) => {
  const response = await axios.get(`${API_BASE_URL}/task-templates/${row.id}/export`, { responseType: 'blob' })
  const url = URL.createObjectURL(new Blob([response.data], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${row.code}.json`
  link.click()
  URL.revokeObjectURL(url)
}
const deleteTemplate = async (row) => {
  try {
    await ElMessageBox.confirm(`\u786e\u5b9a\u5220\u9664\u6a21\u677f\u201c${row.name}\u201d\u5417\uff1f`, '\u5220\u9664\u786e\u8ba4', { type: 'warning' })
    await axios.delete(`${API_BASE_URL}/task-templates/${row.id}`)
    ElMessage.success('\u6a21\u677f\u5df2\u5220\u9664')
    fetchTemplates()
    fetchStats()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('\u6a21\u677f\u5220\u9664\u5931\u8d25')
  }
}
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-') : '-'

const ideaPresets = {
  processChain: {
    name: '工艺-结构-性能链路模板',
    code: 'custom_process_structure_property',
    description: '用于抽取陶瓷材料论文中的材料、工艺参数、微观结构、性能数值和关系摘要。',
    task_type: 'kg_build',
    schema: {
      meta: { version: '1.0', tags: ['ceramic', 'process-structure-property', 'relation-extraction'] },
      fields: [
        { key: 'material', label: '材料/组分', type: 'text', required: true },
        { key: 'preparation_method', label: '制备方法', type: 'text', required: false },
        { key: 'process_parameters', label: '工艺参数', type: 'list', required: false },
        { key: 'microstructure', label: '微观结构', type: 'list', required: false },
        { key: 'property_name', label: '性能名称', type: 'text', required: true },
        { key: 'property_value', label: '性能数值', type: 'text', required: true },
        { key: 'unit', label: '单位', type: 'text', required: false },
        { key: 'evidence_sentence', label: '证据句', type: 'textarea', required: true },
        { key: 'relation_summary', label: '关系摘要', type: 'textarea', required: true }
      ]
    }
  },
  evidence: {
    name: '证据链与置信度审核模板',
    code: 'custom_evidence_confidence_review',
    description: '用于保存抽取结论、证据句、页码、置信度和人工审核备注。',
    task_type: 'review',
    schema: {
      meta: { version: '1.0', tags: ['evidence', 'confidence', 'human-review'] },
      fields: [
        { key: 'claim', label: '抽取结论', type: 'textarea', required: true },
        { key: 'evidence_sentence', label: '证据句', type: 'textarea', required: true },
        { key: 'page', label: '页码', type: 'number', required: false },
        { key: 'confidence', label: '置信度', type: 'number', required: true, min: 0, max: 1 },
        { key: 'conflict_flag', label: '冲突标记', type: 'boolean', required: false },
        { key: 'review_note', label: '审核备注', type: 'textarea', required: false }
      ]
    }
  }
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 24px; background: #f6f7f9; color: #303133; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.page-header p { margin: 6px 0 0; color: #606266; font-size: 13px; }
.header-actions, .toolbar { display: flex; align-items: center; gap: 10px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 16px; }
.stat-card { display: flex; justify-content: space-between; align-items: center; min-height: 70px; padding: 16px 18px; background: #fff; border: 1px solid #e6ebf5; border-radius: 4px; }
.stat-card span { color: #606266; font-size: 13px; }
.stat-card strong { color: #1f6feb; font-size: 26px; }
.innovation-panel { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 16px; padding: 18px; background: #fff; border: 1px solid #e6ebf5; border-radius: 4px; }
.innovation-panel h3 { margin: 0 0 6px; font-size: 16px; }
.innovation-panel p { margin: 0; color: #606266; font-size: 13px; line-height: 1.6; }
.innovation-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.toolbar { padding: 16px; margin-bottom: 16px; background: #fff; border: 1px solid #e6ebf5; border-radius: 4px; }
.search-input { width: 320px; }
.table-wrap { padding: 18px; background: #fff; border: 1px solid #e6ebf5; border-radius: 4px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 12px; }
.full-width { width: 100%; }
.mono :deep(textarea) { font-family: Consolas, Monaco, monospace; font-size: 13px; }
.preview-meta { display: flex; gap: 8px; margin-bottom: 12px; }
.preview-desc { color: #606266; line-height: 1.6; }
.idea-list { display: flex; flex-direction: column; gap: 12px; }
.idea-item { padding: 14px; border: 1px solid #e6ebf5; border-radius: 4px; background: #fff; }
.idea-title { font-weight: 600; color: #303133; margin-bottom: 6px; }
.idea-item p { margin: 0 0 10px; color: #606266; line-height: 1.6; }
.idea-tags { display: flex; flex-wrap: wrap; gap: 6px; }
@media (max-width: 1080px) { .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .innovation-panel { align-items: flex-start; flex-direction: column; } }
</style>
