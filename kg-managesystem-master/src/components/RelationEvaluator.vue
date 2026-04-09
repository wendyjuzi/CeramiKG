<template>
  <div class="relation-evaluator">
    <div class="evaluator-header">
      <h3>🔗 关系抽取结果</h3>
      <div class="header-actions">
        <el-button 
          type="primary"
          :loading="extracting"
          :disabled="!canExtract"
          @click="startRelationExtraction"
        >
          <el-icon><Connection /></el-icon>
          开始关系抽取
        </el-button>
        <el-button 
          v-if="relations.length > 0"
          type="success"
          :disabled="confirmedRelations.length === 0"
          @click="saveKnowledge"
        >
          <el-icon><DocumentAdd /></el-icon>
          保存知识 ({{ confirmedRelations.length }})
        </el-button>
      </div>
    </div>

    <!-- 抽取状态和配置 -->
    <div class="extraction-config">
      <el-alert
        v-if="!selectedDocument"
        title="请先选择文档"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="!confirmedEntities || confirmedEntities.length === 0"
        title="请先确认实体"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="relationTerms.length === 0"
        title="将使用通用关系抽取模式"
        type="info"
        :closable="false"
        show-icon
      />
      <div v-else class="config-info">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="文档">
            {{ selectedDocument.name }}
          </el-descriptions-item>
          <el-descriptions-item label="实体数量">
            {{ confirmedEntities.length }} 个
          </el-descriptions-item>
          <el-descriptions-item label="关系术语">
            {{ relationTerms.length }} 个
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <!-- 关系抽取结果表格 -->
    <div v-if="relations.length > 0" class="relations-table">
      <div class="table-header">
        <div class="table-title">
          <span>📊 识别到 {{ relations.length }} 个关系</span>
          <div class="selection-actions">
            <el-button size="small" @click="selectAllRelations">全选</el-button>
            <el-button size="small" @click="clearAllRelations">清空</el-button>
            <el-button size="small" type="primary" @click="addNewRelation">
              <el-icon><Plus /></el-icon>新增
            </el-button>
          </div>
        </div>
        <div class="table-filters">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索关系或实体..."
            prefix-icon="Search"
            style="width: 300px"
            clearable
          />
          <el-select
            v-model="relationTypeFilter"
            placeholder="按关系类型筛选"
            style="width: 150px"
            clearable
          >
            <el-option label="全部关系" value="" />
            <el-option
              v-for="type in relationTypes"
              :key="type"
              :label="type"
              :value="type"
            />
          </el-select>
        </div>
      </div>

      <el-table
        ref="relationTable"
        :data="filteredRelations"
        border
        stripe
        height="500"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        
        <!-- 序号列 -->
        <el-table-column
          label="序号"
          width="80"
          sortable
        >
          <template #default="{ row, $index }">
            {{ row.id || ($index + 1) }}
          </template>
        </el-table-column>
        
        <!-- 关系ID列 -->
        <el-table-column 
          prop="relation_id" 
          label="关系ID" 
          width="120"
          show-overflow-tooltip
        />
        
        <!-- 关系名列 -->
        <el-table-column 
          prop="relation_name" 
          label="关系名" 
          width="150"
          show-overflow-tooltip
        />
        
        <!-- 头实体名列 -->
        <el-table-column 
          prop="head_entity" 
          label="头实体名" 
          width="150"
          show-overflow-tooltip
        />
        
        <!-- 尾实体名列 -->
        <el-table-column 
          prop="tail_entity" 
          label="尾实体名" 
          width="150"
          show-overflow-tooltip
        />
        
        <!-- 关系三元组列（保留用于更好的视觉展示） -->
        <el-table-column label="关系三元组" min-width="300">
          <template #default="{ row }">
            <div class="relation-triple">
              <el-tag type="primary" size="small">{{ row.head_entity || row.source_entity }}</el-tag>
              <el-icon class="relation-arrow"><Right /></el-icon>
              <el-tag type="success" size="small">{{ row.relation_name || row.relation_type }}</el-tag>
              <el-icon class="relation-arrow"><Right /></el-icon>
              <el-tag type="warning" size="small">{{ row.tail_entity || row.target_entity }}</el-tag>
            </div>
          </template>
        </el-table-column>
        
        <!-- 异常17修复：置信度保留两位小数 -->
        <el-table-column 
          prop="confidence" 
          label="置信度" 
          width="120"
          sortable
        >
          <template #default="{ row }">
            <el-progress 
              :percentage="parseFloat((row.confidence * 100).toFixed(2))"
              :stroke-width="8"
              :format="(percentage) => `${percentage.toFixed(2)}%`"
              :color="getConfidenceColor(row.confidence)"
              :show-text="false"
            />
            <div class="confidence-text">
              {{ (row.confidence * 100).toFixed(2) }}%
            </div>
          </template>
        </el-table-column>
        
        <el-table-column 
          prop="description" 
          label="描述" 
          min-width="200"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <el-text v-if="row.description" type="info" size="small">
              {{ row.description }}
            </el-text>
            <el-text v-else type="placeholder" size="small">
              无描述
            </el-text>
          </template>
        </el-table-column>
        
        <!-- 异常17修复：证据文本字段 -->
        <el-table-column 
          prop="evidence_text"
          label="证据文本" 
          min-width="200"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <div v-if="row.evidence_text || row.evidence" class="evidence-text">
              <el-text type="info" size="small">
                "{{ row.evidence_text || row.evidence }}"
              </el-text>
            </div>
            <el-text v-else type="placeholder" size="small">
              无证据文本
            </el-text>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row, $index }">
            <el-button
              size="small"
              @click="editRelation(row, $index)"
            >
              编辑
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="deleteRelation($index)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="filteredRelations.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!extracting" class="empty-state">
      <el-empty description="暂无关系抽取结果">
        <template #image>
          <el-icon size="100" color="#c0c4cc">
            <Connection />
          </el-icon>
        </template>
      </el-empty>
    </div>

    <!-- 加载状态 -->
    <div v-if="extracting" class="loading-state">
      <el-card>
        <div class="loading-content">
          <el-icon size="50" class="rotating">
            <Loading />
          </el-icon>
          <h4>正在进行关系抽取...</h4>
          <p>正在分析实体间的关系，请耐心等待</p>
          <el-progress :percentage="extractionProgress" :stroke-width="6" />
        </div>
      </el-card>
    </div>

    <!-- 关系编辑弹窗 -->
    <el-dialog
      v-model="editDialogVisible"
      :title="editingIndex >= 0 ? '编辑关系' : '新增关系'"
      width="600px"
      @close="resetEditForm"
    >
      <el-form
        ref="editFormRef"
        :model="editForm"
        :rules="editRules"
        label-width="120px"
      >
        <!-- 序号 -->
        <el-form-item label="序号">
          <el-input v-model="editForm.id" disabled placeholder="自动生成" />
        </el-form-item>
        
        <!-- 关系ID -->
        <el-form-item label="关系ID">
          <el-input v-model="editForm.relation_id" placeholder="自动生成关系ID" />
        </el-form-item>
        
        <!-- 关系名 -->
        <el-form-item label="关系名" prop="relation_name">
          <el-input
            v-model="editForm.relation_name"
            placeholder="输入关系名"
          />
        </el-form-item>
        
        <!-- 头实体名 -->
        <el-form-item label="头实体名" prop="head_entity">
          <el-select
            v-model="editForm.head_entity"
            placeholder="选择头实体"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="entity in confirmedEntities"
              :key="entity.entity_id || entity.id"
              :label="entity.entity_name || entity.name"
              :value="entity.entity_name || entity.name"
            />
          </el-select>
        </el-form-item>
        
        <!-- 尾实体名 -->
        <el-form-item label="尾实体名" prop="tail_entity">
          <el-select
            v-model="editForm.tail_entity"
            placeholder="选择尾实体"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="entity in confirmedEntities"
              :key="entity.entity_id || entity.id"
              :label="entity.entity_name || entity.name"
              :value="entity.entity_name || entity.name"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="置信度" prop="confidence">
          <el-slider
            v-model="editForm.confidence"
            :min="0"
            :max="1"
            :step="0.01"
            :format-tooltip="(val) => `${Math.round(val * 100)}%`"
            style="width: 100%"
          />
        </el-form-item>
        
        <el-form-item label="描述">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="3"
            placeholder="输入关系描述"
          />
        </el-form-item>
        
        <!-- 异常17修复：统一证据文本字段名 -->
        <el-form-item label="证据文本">
          <el-input
            v-model="editForm.evidence_text"
            type="textarea"
            :rows="3"
            placeholder="输入证据文本"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="editDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveEdit">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, computed, reactive, watch, nextTick, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, DocumentAdd, Right, Loading, Search, Plus } from '@element-plus/icons-vue'

export default {
  name: 'RelationEvaluator',
  components: {
    Connection,
    DocumentAdd,
    Right,
    Loading,
    Search,
    Plus
  },
  props: {
    selectedDocument: {
      type: Object,
      default: null
    },
    selectedTerms: {
      type: Array,
      default: () => []
    },
    confirmedEntities: {
      type: Array,
      default: () => []
    }
  },
  emits: ['knowledge-saved', 'relations-changed'],
  setup(props, { emit }) {
    // 响应式数据
    const relations = ref([])
    const confirmedRelations = ref([])
    const extracting = ref(false)
    const extractionProgress = ref(0)
    const searchKeyword = ref('')
    const relationTypeFilter = ref('')
    const currentPage = ref(1)
    const pageSize = ref(20)
    const editDialogVisible = ref(false)
    const editFormRef = ref(null)
    const editingIndex = ref(-1)
    const relationTable = ref(null)  // 异常19修复：添加表格ref

    // 编辑表单（支持新字段格式，异常17修复）
    const editForm = reactive({
      id: null,
      relation_id: '',
      relation_name: '',
      head_entity: '',
      tail_entity: '',
      confidence: 0.8,
      description: '',
      evidence_text: '', // 异常17修复：统一字段名
      // 向后兼容
      evidence: '',
      source_entity: '',
      relation_type: '',
      target_entity: ''
    })

    // 表单验证规则（支持新字段格式）
    const editRules = {
      head_entity: [
        { required: true, message: '请选择头实体', trigger: 'change' }
      ],
      relation_name: [
        { required: true, message: '请输入关系名', trigger: 'blur' }
      ],
      tail_entity: [
        { required: true, message: '请选择尾实体', trigger: 'change' }
      ],
      confidence: [
        { required: true, message: '请设置置信度', trigger: 'change' }
      ]
    }
    
    // API基础URL
    const API_BASE_URL = '/api/graph'

    // 计算属性
    const relationTerms = computed(() => {
      return props.selectedTerms.filter(term => term.type === '关系')
    })

    const canExtract = computed(() => {
      return props.selectedDocument && 
             props.confirmedEntities.length > 0 && 
             !extracting.value
    })

    const filteredRelations = computed(() => {
      let result = relations.value

      // 搜索筛选（支持新旧字段格式）
      if (searchKeyword.value) {
        const keyword = searchKeyword.value.toLowerCase()
        result = result.filter(relation => 
          (relation.head_entity || relation.source_entity || '').toLowerCase().includes(keyword) ||
          (relation.tail_entity || relation.target_entity || '').toLowerCase().includes(keyword) ||
          (relation.relation_name || relation.relation_type || '').toLowerCase().includes(keyword) ||
          (relation.relation_id || '').toLowerCase().includes(keyword) ||
          (relation.description && relation.description.toLowerCase().includes(keyword))
        )
      }

      // 关系类型筛选（支持新旧字段格式）
      if (relationTypeFilter.value) {
        result = result.filter(relation => 
          (relation.relation_name || relation.relation_type) === relationTypeFilter.value
        )
      }

      return result
    })

    const relationTypes = computed(() => {
      const types = new Set(relations.value.map(relation =>
        relation.relation_name || relation.relation_type || ''
      ))
      return Array.from(types).filter(type => type).sort()
    })

    // 开始关系抽取
    const startRelationExtraction = async () => {
      if (!canExtract.value) {
        ElMessage.warning('请确保已选择文档、确认实体和关系术语')
        return
      }

      extracting.value = true
      extractionProgress.value = 0
      relations.value = []
      confirmedRelations.value = []

      try {
        // 模拟进度更新
        const progressTimer = setInterval(() => {
          if (extractionProgress.value < 90) {
            extractionProgress.value = parseFloat((extractionProgress.value + Math.random() * 10).toFixed(2))
          }
        }, 500)

        const requestData = {
          entities: props.confirmedEntities,
          terms: relationTerms.value.length > 0 ? relationTerms.value : null, // 无术语时传null
          document_content: props.selectedDocument.json_data?.text || props.selectedDocument.content || '',
          document_id: props.selectedDocument?.document_id?.toString() // 异常14新增：支持缓存机制
        }

        const response = await axios.post(`${API_BASE_URL}/relation-extraction`, requestData)
        
        clearInterval(progressTimer)
        extractionProgress.value = 100

        if (response.data && Array.isArray(response.data)) {
          relations.value = response.data
          ElMessage.success(`成功识别 ${relations.value.length} 个关系`)
        } else {
          relations.value = []
          ElMessage.warning('关系抽取结果格式异常')
        }
      } catch (error) {
        console.error('关系抽取失败:', error)
        ElMessage.error('关系抽取失败: ' + (error.response?.data?.detail || error.message))
        relations.value = []
      } finally {
        extracting.value = false
      }
    }

    // 处理表格选择变化
    const handleSelectionChange = (selection) => {
      confirmedRelations.value = selection
      emit('relations-changed', selection)
    }

    // 全选关系（选择所有筛选后的数据，不仅是当前页）
    const selectAllRelations = () => {
        const table = relationTable.value
        if (table) {
          // 先清空当前选择
          table.clearSelection()
          // 选择所有筛选后的数据
          filteredRelations.value.forEach(relation => {
            table.toggleRowSelection(relation, true)
          })
        }
    }

    // 清空选择
    const clearAllRelations = () => {
      nextTick(() => {
        const table = relationTable.value
        if (table) {
          table.clearSelection()
        }
      })
    }

    // 编辑关系（支持新旧字段格式）
    const editRelation = (relation, index) => {
      editingIndex.value = index
      // 新字段格式
      editForm.id = relation.id
      editForm.relation_id = relation.relation_id || ''
      editForm.relation_name = relation.relation_name || relation.relation_type || ''
      editForm.head_entity = relation.head_entity || relation.source_entity || ''
      editForm.tail_entity = relation.tail_entity || relation.target_entity || ''
      // 向后兼容
      editForm.source_entity = relation.source_entity || relation.head_entity || ''
      editForm.relation_type = relation.relation_type || relation.relation_name || ''
      editForm.target_entity = relation.target_entity || relation.tail_entity || ''
      // 其他字段（异常17修复）
      editForm.confidence = relation.confidence || 0.8
      editForm.description = relation.description || ''
      editForm.evidence_text = relation.evidence_text || relation.evidence || ''
      editForm.evidence = relation.evidence || relation.evidence_text || '' // 向后兼容
      editDialogVisible.value = true
    }

    // 删除关系
    const deleteRelation = async (index) => {
      try {
        await ElMessageBox.confirm(
          '确定要删除这个关系吗？',
          '删除关系',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        relations.value.splice(index, 1)
        ElMessage.success('关系删除成功')
      } catch {
        // 用户取消
      }
    }

    // 新增关系
    const addNewRelation = () => {
      resetEditForm()
      // 设置新关系的默认值
      editForm.id = relations.value.length + 1
      editForm.relation_id = `rel_${String(relations.value.length + 1).padStart(3, '0')}`
      editingIndex.value = -1 // -1表示新增模式
      editDialogVisible.value = true
    }

    // 保存编辑（支持新增和修改）
    const saveEdit = async () => {
      if (!editFormRef.value) return
      
      try {
        await editFormRef.value.validate()
        
        if (editingIndex.value >= 0) {
          // 更新现有关系
          relations.value[editingIndex.value] = { 
            ...editForm,
            // 确保向后兼容性
            source_entity: editForm.head_entity,
            relation_type: editForm.relation_name,
            target_entity: editForm.tail_entity
          }
          ElMessage.success('关系更新成功')
        } else {
          // 新增关系
          const newRelation = {
            ...editForm,
            // 确保向后兼容性
            source_entity: editForm.head_entity,
            relation_type: editForm.relation_name,
            target_entity: editForm.tail_entity
          }
          relations.value.push(newRelation)
          ElMessage.success('关系新增成功')
        }
        
        editDialogVisible.value = false
        resetEditForm()
      } catch (error) {
        console.error('表单验证失败:', error)
      }
    }

    // 重置编辑表单（支持新字段格式）
    const resetEditForm = () => {
      editingIndex.value = -1
      // 新字段格式
      editForm.id = null
      editForm.relation_id = ''
      editForm.relation_name = ''
      editForm.head_entity = ''
      editForm.tail_entity = ''
      // 向后兼容
      editForm.source_entity = ''
      editForm.relation_type = ''
      editForm.target_entity = ''
      // 其他字段（异常17修复）
      editForm.confidence = 0.8
      editForm.description = ''
      editForm.evidence_text = ''
      editForm.evidence = '' // 向后兼容
      
      if (editFormRef.value) {
        editFormRef.value.resetFields()
      }
    }

    // 保存知识
    const saveKnowledge = async () => {
      if (confirmedRelations.value.length === 0) {
        ElMessage.warning('请先选择要保存的关系')
        return
      }

      try {
        await ElMessageBox.confirm(
          `确认保存 ${confirmedRelations.value.length} 个关系到知识库？`,
          '保存知识',
          {
            confirmButtonText: '保存',
            cancelButtonText: '取消',
            type: 'info'
          }
        )

        // 异常14修改：先保存关系，再保存最终知识
        if (props.selectedDocument?.document_id) {
          // 1. 保存关系到关系表
          const relationRequestData = {
            document_id: props.selectedDocument.document_id.toString(),
            relations: confirmedRelations.value
          }

          try {
            await axios.post(`${API_BASE_URL}/save-relations`, relationRequestData)
          } catch (relationError) {
            console.error('保存关系失败:', relationError)
            throw new Error('保存关系失败')
          }

          // 2. 保存最终知识到知识表
          const knowledgeRequestData = {
            document_id: props.selectedDocument.document_id.toString(),
            relations: confirmedRelations.value
          }

          const response = await axios.post(`${API_BASE_URL}/save-knowledge-new`, knowledgeRequestData)
          
          if (response.data && response.data.success) {
            ElMessage.success(`成功保存 ${confirmedRelations.value.length} 个关系到知识库`)
            emit('knowledge-saved', {
              success: true,
              document_name: props.selectedDocument.name,
              document_id: props.selectedDocument.document_id,
              relations: confirmedRelations.value,
              data: response.data.data
            })
          } else {
            ElMessage.error('保存知识失败')
          }
        } else {
          // 保持向后兼容的旧方式
          const requestData = {
            document_name: props.selectedDocument.name,
            relations: confirmedRelations.value
          }

          const response = await axios.post(`${API_BASE_URL}/save-knowledge`, requestData)
          
          if (response.data && response.data.success) {
            ElMessage.success(`成功保存 ${confirmedRelations.value.length} 个关系到知识库`)
            emit('knowledge-saved', {
              success: true,
              document_name: props.selectedDocument.name,
              relations: confirmedRelations.value,
              data: response.data.data
            })
          } else {
            ElMessage.error('保存知识失败')
          }
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('保存知识失败:', error)
          ElMessage.error('保存知识失败: ' + (error.response?.data?.detail || error.message))
        }
      }
    }

    // 获取置信度颜色
    const getConfidenceColor = (confidence) => {
      if (confidence >= 0.8) return '#67c23a'
      if (confidence >= 0.6) return '#e6a23c'
      if (confidence >= 0.4) return '#f56c6c'
      return '#909399'
    }

    // 监听筛选条件变化，重置分页
    watch([searchKeyword, relationTypeFilter], () => {
      currentPage.value = 1
    })

    // 异常23修复：页面初始化时立即检查关系表是否存在
    const checkExistingRelations = async () => {
      if (!props.selectedDocument?.document_id) {
        return
      }

      try {
        const response = await axios.get(`${API_BASE_URL}/documents/${props.selectedDocument.document_id}/relations`)
        
        if (response.data?.exists && response.data.relations && response.data.relations.length > 0) {
          // 表存在且有数据，直接加载
          relations.value = response.data.relations
          ElMessage.success(`加载已有关系数据：${response.data.relations.length} 个关系`)
          
          // 可以选择自动选中所有关系，或者让用户手动选择
          // confirmedRelations.value = response.data.relations
          // emit('relations-changed', confirmedRelations.value)
        } else {
          // 表不存在或无数据
          relations.value = []
          console.log(`关系表不存在，等待用户选择自动抽取或手动添加`)
        }
      } catch (error) {
        console.error('检查已有关系数据失败:', error)
        relations.value = []
      }
    }

    // 异常23修复：组件挂载时立即检查
    onMounted(() => {
      checkExistingRelations()
    })

    // 异常23修复：监听文档变化，自动重新检查
    watch(() => props.selectedDocument, () => {
      if (props.selectedDocument?.document_id) {
        checkExistingRelations()
      } else {
        relations.value = []
        confirmedRelations.value = []
      }
    })

    // 注意：在传统的 setup() 函数中，不需要 defineExpose
    // saveKnowledge 函数已通过 return 语句暴露给父组件

    return {
      relations,
      confirmedRelations,
      extracting,
      extractionProgress,
      searchKeyword,
      relationTypeFilter,
      currentPage,
      pageSize,
      editDialogVisible,
      editFormRef,
      editForm,
      editRules,
      relationTable,  // 异常19修复：导出表格ref
      relationTerms,
      canExtract,
      filteredRelations,
      relationTypes,
      startRelationExtraction,
      handleSelectionChange,
      selectAllRelations,
      clearAllRelations,
      addNewRelation,
      editRelation,
      deleteRelation,
      saveEdit,
      resetEditForm,
      saveKnowledge,
      getConfidenceColor
    }
  }
}
</script>

<style scoped>
.relation-evaluator {
  width: 100%;
}

.evaluator-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.evaluator-header h3 {
  margin: 0;
  color: #409eff;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.extraction-config {
  margin-bottom: 20px;
}

.config-info {
  margin-top: 12px;
}

.relations-table {
  margin-top: 20px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.table-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.selection-actions {
  display: flex;
  gap: 8px;
}

.table-filters {
  display: flex;
  gap: 12px;
  align-items: center;
}

.relation-triple {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.relation-arrow {
  color: #909399;
  font-size: 12px;
}

.confidence-text {
  text-align: center;
  font-size: 12px;
  margin-top: 4px;
}

.evidence-text {
  max-width: 200px;
  line-height: 1.5;
}

.table-pagination {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.empty-state {
  text-align: center;
  padding: 60px 0;
}

.loading-state {
  margin: 40px 0;
}

.loading-content {
  text-align: center;
  padding: 40px;
}

.loading-content h4 {
  margin: 16px 0 8px 0;
  color: #606266;
}

.loading-content p {
  margin: 0 0 20px 0;
  color: #909399;
}

.rotating {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .table-header {
    flex-direction: column;
    align-items: stretch;
  }
  
  .table-filters {
    flex-direction: column;
    gap: 8px;
  }
  
  .header-actions {
    flex-direction: column;
    gap: 8px;
  }
  
  .relation-triple {
    flex-direction: column;
    gap: 4px;
    align-items: flex-start;
  }
}
</style>