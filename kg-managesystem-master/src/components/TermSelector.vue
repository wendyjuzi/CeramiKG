<template>
  <div class="term-selector">
    <div class="selector-header">
      <h3>🏷️ 术语选择</h3>
      <div class="header-actions">
        <!-- 异常54修复：改善新增术语按钮图标显示 -->
        <el-button
          type="primary"
          size="small"
          @click="openAddTermDialog"
          :disabled="loading"
        >
          <el-icon><Plus /></el-icon>
          新增术语
        </el-button>
        <el-button
          type="text"
          @click="selectAll"
          :disabled="loading"
        >
          全选
        </el-button>
        <el-button
          type="text"
          @click="clearAll"
          :disabled="loading"
        >
          清空
        </el-button>
        <el-tag v-if="selectedTerms.length > 0" type="primary" size="small">
          已选择 {{ selectedTerms.length }} 个术语
        </el-tag>
      </div>
    </div>

    <!-- 筛选控件 -->
    <div class="filter-controls">
      <div class="filter-row">
        <div class="filter-item">
          <el-radio-group v-model="filterType" @change="handleFilterChange">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="实体">实体类型</el-radio-button>
            <el-radio-button label="关系">关系类型</el-radio-button>
          </el-radio-group>
        </div>
        <div class="filter-item">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索术语名称或描述..."
            @input="handleSearch"
            clearable
            prefix-icon="Search"
            style="width: 300px"
          />
        </div>
      </div>
    </div>

    <!-- 统计信息 -->
    <div class="stats-info">
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="总数">
          {{ filteredTerms.length }}
        </el-descriptions-item>
        <el-descriptions-item label="实体类型">
          {{ entityTerms.length }}
        </el-descriptions-item>
        <el-descriptions-item label="关系类型">
          {{ relationTerms.length }}
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 术语卡片展示区 -->
    <div v-loading="loading" class="terms-container">
      <div v-if="filteredTerms.length === 0" class="empty-state">
        <el-empty description="没有找到匹配的术语">
          <el-button type="primary" @click="loadTerms">
            刷新术语库
          </el-button>
        </el-empty>
      </div>
      
      <div v-else class="terms-grid">
        <div
          v-for="term in paginatedTerms"
          :key="term.id"
          class="term-card"
          :class="{ 
            'selected': isTermSelected(term),
            'entity-term': term.type === '实体',
            'relation-term': term.type === '关系'
          }"
          @click="toggleTerm(term)"
        >
          <el-card shadow="hover" :body-style="{ padding: '16px' }">
            <div class="term-header">
              <div class="term-info">
                <span class="term-name">{{ term.name }}</span>
                <el-tag 
                  :type="term.type === '实体' ? 'primary' : 'success'" 
                  size="small"
                >
                  {{ term.type }}
                </el-tag>
              </div>
              <el-checkbox
                :model-value="isTermSelected(term)"
                @click.stop
                @change="toggleTerm(term)"
                size="large"
              />
            </div>
            
            <div v-if="term.description" class="term-description">
              <el-text type="info" size="small">
                {{ term.description }}
              </el-text>
            </div>
            
            <div class="term-footer">
              <div class="term-footer-left">
                <el-text type="info" size="small">
                  ID: {{ term.id }}
                </el-text>
              </div>
              <!-- 异常54修复：改善术语管理操作按钮可见性 -->
              <div class="term-footer-right">
                <el-button
                  type="primary"
                  size="small"
                  link
                  @click.stop="openEditTermDialog(term)"
                  title="编辑术语"
                  class="edit-btn"
                >
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  link
                  @click.stop="deleteTerm(term)"
                  title="删除术语"
                  class="delete-btn"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </el-card>
        </div>
      </div>

      <!-- 分页器 -->
      <div v-if="filteredTerms.length > pageSize" class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[12, 24, 48, 96]"
          :total="filteredTerms.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>
    </div>

    <!-- 选中术语预览 -->
    <div v-if="selectedTerms.length > 0" class="selected-preview">
      <el-collapse v-model="activeCollapse">
        <el-collapse-item title="查看选中的术语" name="selected">
          <template #title>
            <span>📋 查看选中的术语 ({{ selectedTerms.length }})</span>
          </template>
          
          <div class="selected-terms-list">
            <div class="term-type-group">
              <h4 v-if="selectedEntityTerms.length > 0">
                实体类型 ({{ selectedEntityTerms.length }})
              </h4>
              <el-tag
                v-for="term in selectedEntityTerms"
                :key="term.id"
                type="primary"
                closable
                @close="toggleTerm(term)"
                style="margin: 4px"
              >
                {{ term.name }}
              </el-tag>
            </div>
            
            <div class="term-type-group">
              <h4 v-if="selectedRelationTerms.length > 0">
                关系类型 ({{ selectedRelationTerms.length }})
              </h4>
              <el-tag
                v-for="term in selectedRelationTerms"
                :key="term.id"
                type="success"
                closable
                @close="toggleTerm(term)"
                style="margin: 4px"
              >
                {{ term.name }}
              </el-tag>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <!-- 异常41修复：术语管理对话框 -->
    <el-dialog
      v-model="termDialogVisible"
      :title="dialogMode === 'add' ? '新增术语' : '编辑术语'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="termFormRef"
        :model="termForm"
        :rules="termFormRules"
        label-width="100px"
      >
        <el-form-item label="术语名称" prop="name">
          <el-input
            v-model="termForm.name"
            placeholder="请输入术语名称"
            clearable
            maxlength="100"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="术语类型" prop="type">
          <el-radio-group v-model="termForm.type">
            <el-radio label="实体">实体类型</el-radio>
            <el-radio label="关系">关系类型</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="术语描述" prop="description">
          <el-input
            v-model="termForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入术语描述（可选）"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="termDialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            @click="submitTermForm"
            :loading="termSubmitting"
          >
            {{ dialogMode === 'add' ? '新增' : '更新' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Delete, Plus } from '@element-plus/icons-vue'

export default {
  name: 'TermSelector',
  components: {
    Edit,
    Delete,
    Plus
  },
  emits: ['terms-selected', 'terms-changed'],
  setup(props, { emit }) {
    // 响应式数据
    const terms = ref([])
    const selectedTerms = ref([])
    const loading = ref(false)
    const filterType = ref('')
    const searchKeyword = ref('')
    const currentPage = ref(1)
    const pageSize = ref(24)
    const activeCollapse = ref([])

    // 异常41修复：术语管理相关状态
    const termDialogVisible = ref(false)
    const dialogMode = ref('add') // add | edit
    const termSubmitting = ref(false)
    const termFormRef = ref(null)
    const editingTerm = ref(null)

    // 术语表单数据
    const termForm = reactive({
      name: '',
      type: '实体',
      description: ''
    })

    // 术语表单验证规则
    const termFormRules = {
      name: [
        { required: true, message: '请输入术语名称', trigger: 'blur' },
        { min: 1, max: 100, message: '术语名称长度在 1 到 100 个字符', trigger: 'blur' }
      ],
      type: [
        { required: true, message: '请选择术语类型', trigger: 'change' }
      ]
    }

    // API基础URL
    const API_BASE_URL = '/api/graph'

    // 计算属性
    const filteredTerms = computed(() => {
      let result = terms.value

      // 按类型筛选
      if (filterType.value) {
        result = result.filter(term => term.type === filterType.value)
      }

      // 按关键字搜索
      if (searchKeyword.value) {
        const keyword = searchKeyword.value.toLowerCase()
        result = result.filter(term => 
          term.name.toLowerCase().includes(keyword) ||
          (term.description && term.description.toLowerCase().includes(keyword))
        )
      }

      return result
    })

    const paginatedTerms = computed(() => {
      const start = (currentPage.value - 1) * pageSize.value
      const end = start + pageSize.value
      return filteredTerms.value.slice(start, end)
    })

    const entityTerms = computed(() => 
      filteredTerms.value.filter(term => term.type === '实体')
    )

    const relationTerms = computed(() => 
      filteredTerms.value.filter(term => term.type === '关系')
    )

    const selectedEntityTerms = computed(() =>
      selectedTerms.value.filter(term => term.type === '实体')
    )

    const selectedRelationTerms = computed(() =>
      selectedTerms.value.filter(term => term.type === '关系')
    )

    // 加载术语库
    const loadTerms = async () => {
      loading.value = true
      try {
        const response = await axios.get(`${API_BASE_URL}/terms`)
        
        if (response.data && Array.isArray(response.data)) {
          terms.value = response.data
          ElMessage.success(`成功加载 ${terms.value.length} 个术语`)
        } else {
          terms.value = []
          ElMessage.warning('术语数据格式异常')
        }
      } catch (error) {
        console.error('加载术语失败:', error)
        ElMessage.error('加载术语失败: ' + (error.response?.data?.detail || error.message))
        terms.value = []
      } finally {
        loading.value = false
      }
    }

    // 处理筛选变化
    const handleFilterChange = () => {
      currentPage.value = 1
    }

    // 处理搜索
    const handleSearch = () => {
      currentPage.value = 1
    }

    // 判断术语是否被选中
    const isTermSelected = (term) => {
      return selectedTerms.value.some(selected => selected.id === term.id)
    }

    // 切换术语选择状态
    const toggleTerm = (term) => {
      const index = selectedTerms.value.findIndex(selected => selected.id === term.id)
      
      if (index === -1) {
        // 添加术语
        selectedTerms.value.push(term)
      } else {
        // 移除术语
        selectedTerms.value.splice(index, 1)
      }
      
      // 触发事件
      emit('terms-selected', selectedTerms.value)
      emit('terms-changed', selectedTerms.value)
    }

    // 全选
    const selectAll = () => {
      selectedTerms.value = [...filteredTerms.value]
      emit('terms-selected', selectedTerms.value)
      emit('terms-changed', selectedTerms.value)
      ElMessage.success(`已选择 ${selectedTerms.value.length} 个术语`)
    }

    // 清空选择
    const clearAll = () => {
      selectedTerms.value = []
      emit('terms-selected', selectedTerms.value)
      emit('terms-changed', selectedTerms.value)
      ElMessage.info('已清空所有选择')
    }

    // 异常41修复：术语管理方法
    const resetTermForm = () => {
      termForm.name = ''
      termForm.type = '实体'
      termForm.description = ''
      if (termFormRef.value) {
        termFormRef.value.clearValidate()
      }
    }

    const openAddTermDialog = () => {
      dialogMode.value = 'add'
      editingTerm.value = null
      resetTermForm()
      termDialogVisible.value = true
    }

    const openEditTermDialog = (term) => {
      dialogMode.value = 'edit'
      editingTerm.value = term
      termForm.name = term.name
      termForm.type = term.type
      termForm.description = term.description || ''
      termDialogVisible.value = true
    }

    const submitTermForm = async () => {
      if (!termFormRef.value) return

      try {
        const valid = await termFormRef.value.validate()
        if (!valid) return

        termSubmitting.value = true

        if (dialogMode.value === 'add') {
          // 新增术语
          const response = await axios.post(`${API_BASE_URL}/terms`, {
            name: termForm.name.trim(),
            type: termForm.type,
            description: termForm.description || null
          })

          ElMessage.success('术语新增成功')

          // 添加到本地列表
          terms.value.push(response.data)
        } else {
          // 编辑术语
          await axios.put(`${API_BASE_URL}/terms/${editingTerm.value.id}`, {
            name: termForm.name.trim(),
            type: termForm.type,
            description: termForm.description || null
          })

          ElMessage.success('术语更新成功')

          // 更新本地列表
          const index = terms.value.findIndex(t => t.id === editingTerm.value.id)
          if (index !== -1) {
            terms.value[index] = {
              ...terms.value[index],
              name: termForm.name.trim(),
              type: termForm.type,
              description: termForm.description || null
            }
          }
        }

        termDialogVisible.value = false
        emit('terms-changed', selectedTerms.value)
      } catch (error) {
        console.error('术语操作失败:', error)
        ElMessage.error('术语操作失败: ' + (error.response?.data?.detail || error.message))
      } finally {
        termSubmitting.value = false
      }
    }

    const deleteTerm = async (term) => {
      try {
        await ElMessageBox.confirm(
          `确定要删除术语"${term.name}"吗？此操作不可撤销。`,
          '删除确认',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )

        await axios.delete(`${API_BASE_URL}/terms/${term.id}`)

        ElMessage.success('术语删除成功')

        // 从本地列表中移除
        const index = terms.value.findIndex(t => t.id === term.id)
        if (index !== -1) {
          terms.value.splice(index, 1)
        }

        // 如果删除的术语在选中列表中，也要移除
        const selectedIndex = selectedTerms.value.findIndex(t => t.id === term.id)
        if (selectedIndex !== -1) {
          selectedTerms.value.splice(selectedIndex, 1)
          emit('terms-selected', selectedTerms.value)
          emit('terms-changed', selectedTerms.value)
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除术语失败:', error)
          ElMessage.error('删除术语失败: ' + (error.response?.data?.detail || error.message))
        }
      }
    }

    // 监听筛选条件变化，重置分页
    watch([filterType, searchKeyword], () => {
      currentPage.value = 1
    })

    // 组件挂载时加载术语
    onMounted(() => {
      loadTerms()
    })

    return {
      terms,
      selectedTerms,
      loading,
      filterType,
      searchKeyword,
      currentPage,
      pageSize,
      activeCollapse,
      filteredTerms,
      paginatedTerms,
      entityTerms,
      relationTerms,
      selectedEntityTerms,
      selectedRelationTerms,
      loadTerms,
      handleFilterChange,
      handleSearch,
      isTermSelected,
      toggleTerm,
      selectAll,
      clearAll,
      // 异常41修复：术语管理
      termDialogVisible,
      dialogMode,
      termSubmitting,
      termFormRef,
      termForm,
      termFormRules,
      openAddTermDialog,
      openEditTermDialog,
      submitTermForm,
      deleteTerm
    }
  }
}
</script>

<style scoped>
.term-selector {
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-controls {
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
}

.stats-info {
  margin-bottom: 20px;
}

.terms-container {
  min-height: 300px;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
}

.terms-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.term-card {
  cursor: pointer;
  transition: all 0.3s ease;
  border-radius: 8px;
  overflow: hidden;
}

.term-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.term-card.selected {
  border: 2px solid #409eff;
  background: linear-gradient(135deg, #e6f3ff 0%, #f0f8ff 100%);
}

.term-card.entity-term.selected {
  border-color: #409eff;
  background: linear-gradient(135deg, #e6f3ff 0%, #f0f8ff 100%);
}

.term-card.relation-term.selected {
  border-color: #67c23a;
  background: linear-gradient(135deg, #f0f9ff 0%, #e8f5e8 100%);
}

.term-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.term-info {
  flex: 1;
  margin-right: 8px;
}

.term-name {
  font-weight: 600;
  font-size: 16px;
  color: #303133;
  display: block;
  margin-bottom: 6px;
}

.term-description {
  margin-bottom: 12px;
  line-height: 1.5;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.term-footer {
  border-top: 1px solid #f0f0f0;
  padding-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.term-footer-left {
  flex: 1;
}

.term-footer-right {
  display: flex;
  gap: 4px;
}

/* 异常54修复：改善术语操作按钮可见性 */
.term-footer-right .el-button {
  padding: 6px 8px;
  min-height: auto;
  margin: 0 2px;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.term-footer-right .edit-btn {
  color: #409eff;
  background-color: rgba(64, 158, 255, 0.1);
}

.term-footer-right .edit-btn:hover {
  background-color: rgba(64, 158, 255, 0.2);
  transform: scale(1.1);
}

.term-footer-right .delete-btn {
  color: #f56c6c;
  background-color: rgba(245, 108, 108, 0.1);
}

.term-footer-right .delete-btn:hover {
  background-color: rgba(245, 108, 108, 0.2);
  transform: scale(1.1);
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.selected-preview {
  margin-top: 24px;
  border-top: 1px solid #ebeef5;
  padding-top: 20px;
}

.selected-terms-list {
  padding: 12px 0;
}

.term-type-group {
  margin-bottom: 16px;
}

.term-type-group h4 {
  margin-bottom: 8px;
  color: #606266;
  font-size: 14px;
  font-weight: 600;
}

.term-type-group:last-child {
  margin-bottom: 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }
  
  .filter-item {
    margin-bottom: 12px;
  }
  
  .terms-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 12px;
  }
  
  .header-actions {
    flex-direction: column;
    gap: 8px;
  }
}
</style>