<template>
  <div class="entity-evaluator">
    <div class="evaluator-header">
      <h3>🎯 实体识别结果</h3>
      <div class="header-actions">
        <el-button 
          type="primary"
          :loading="extracting"
          :disabled="!canExtract"
          @click="startEntityExtraction"
        >
          <el-icon><MagicStick /></el-icon>
          开始实体识别
        </el-button>
        <el-button 
          v-if="entities.length > 0"
          type="success"
          :disabled="confirmedEntities.length === 0"
          @click="confirmSelection"
        >
          <el-icon><Check /></el-icon>
          确认选择 ({{ confirmedEntities.length }})
        </el-button>
      </div>
    </div>

    <!-- 提取状态和配置 -->
    <div class="extraction-config">
      <el-alert
        v-if="!selectedDocument"
        title="请先选择文档"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="!selectedTerms || selectedTerms.length === 0"
        title="未选择术语，将使用通用实体识别模式"
        type="info"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="entityTerms.length === 0"
        title="所选术语中没有实体类型，将使用通用识别模式"
        type="info"
        :closable="false"
        show-icon
      />
      <div v-else class="config-info">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="文档">
            {{ selectedDocument.name }}
          </el-descriptions-item>
          <el-descriptions-item label="实体术语">
            {{ entityTerms.length }} 个
          </el-descriptions-item>
          <el-descriptions-item label="文档长度">
            {{ documentContentLength }} 字符
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <!-- 实体识别结果表格 -->
    <div v-if="entities.length > 0" class="entities-table">
      <div class="table-header">
        <div class="table-title">
          <span>📊 识别到 {{ entities.length }} 个实体</span>
          <el-text type="info" size="small" class="entity-count-note">
            识别结果可能受限于大模型能力，数量不代表文档实体总量
          </el-text>
          <!-- 异常17修复：实体数量不足的提示 -->
          <el-alert
            v-if="entities.length < 3"
            title="提示：识别结果可能少于文档实际实体数量，请人工补充或重新抽取。"
            type="warning"
            :closable="false"
            show-icon
            style="margin-top: 8px"
          />
          <div class="selection-actions">
            <el-button size="small" @click="selectAllEntities">全选</el-button>
            <el-button size="small" @click="clearAllEntities">清空</el-button>
            <el-button size="small" type="success" @click="addNewEntity">
              <el-icon><Plus /></el-icon>
              新增
            </el-button>
            <el-dropdown @command="handleExport" v-if="entities.length > 0">
              <el-button size="small" type="primary">
                导出结果
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="json">导出为JSON</el-dropdown-item>
                  <el-dropdown-item command="excel">导出为Excel</el-dropdown-item>
                  <el-dropdown-item command="csv">导出为CSV</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
        <div class="table-filters">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索实体名称或类型..."
            prefix-icon="Search"
            style="width: 300px"
            clearable
          />
          <el-select
            v-model="typeFilter"
            placeholder="按类型筛选"
            style="width: 150px"
            clearable
          >
            <el-option label="全部类型" value="" />
            <el-option
              v-for="type in entityTypes"
              :key="type"
              :label="type"
              :value="type"
            />
          </el-select>
        </div>
      </div>

      <el-table
        ref="entityTable"
        :data="filteredEntities"
        border
        stripe
        height="400"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        
        <!-- 序号 -->
        <el-table-column type="index" label="序号" width="60" />
        
        <!-- 实体ID -->
        <el-table-column 
          prop="entity_id" 
          label="实体ID" 
          width="70"
          show-overflow-tooltip
        >
          <template #default="{ row, $index }">
            <el-input 
              v-if="row.editing"
              v-model="row.entity_id"
              size="small"
              @blur="saveEdit(row, $index)"
            />
            <span v-else>{{ row.entity_id || row.id }}</span>
          </template>
        </el-table-column>
        
        <!-- 实体名 -->
        <el-table-column 
          prop="entity_name" 
          label="实体名" 
          min-width="120"
          show-overflow-tooltip
        >
          <template #default="{ row, $index }">
            <el-input 
              v-if="row.editing"
              v-model="row.entity_name"
              size="small"
              @blur="saveEdit(row, $index)"
            />
            <el-tag 
              v-else
              :type="getEntityTagType(row.type)" 
              size="small"
              style="cursor: pointer"
              @click="editEntity(row)"
            >
              {{ row.entity_name || row.name }}
            </el-tag>
          </template>
        </el-table-column>
        
        <!-- 类型 -->
        <el-table-column 
          prop="type" 
          label="类型" 
          width="100"
          show-overflow-tooltip
        >
          <template #default="{ row, $index }">
            <el-input 
              v-if="row.editing"
              v-model="row.type"
              size="small"
              @blur="saveEdit(row, $index)"
            />
            <span v-else>{{ row.type }}</span>
          </template>
        </el-table-column>
        
        <!-- 属性值 -->
        <el-table-column 
          prop="attributes" 
          label="属性值" 
          min-width="150"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <div v-if="row.attributes && Object.keys(row.attributes).length > 0" class="attributes">
              <el-tag
                v-for="(value, key) in Object.entries(row.attributes).slice(0, 2)"
                :key="key"
                size="small"
                style="margin: 2px"
              >
                {{ key }}: {{ value }}
              </el-tag>
              <el-text v-if="Object.keys(row.attributes).length > 2" type="info" size="small">
                等{{ Object.keys(row.attributes).length }}个属性
              </el-text>
            </div>
            <el-text v-else type="placeholder" size="small">
              无属性
            </el-text>
          </template>
        </el-table-column>
        
        <!-- 描述 -->
        <el-table-column 
          prop="description" 
          label="描述" 
          min-width="150"
          show-overflow-tooltip
        >
          <template #default="{ row, $index }">
            <el-input 
              v-if="row.editing"
              v-model="row.description"
              type="textarea"
              size="small"
              @blur="saveEdit(row, $index)"
            />
            <el-text 
              v-else-if="row.description" 
              type="info" 
              size="small"
              style="cursor: pointer"
              @click="editEntity(row)"
            >
              {{ row.description }}
            </el-text>
            <el-text 
              v-else 
              type="placeholder" 
              size="small"
              style="cursor: pointer"
              @click="editEntity(row)"
            >
              点击添加描述
            </el-text>
          </template>
        </el-table-column>
        
        <!-- 置信度 -->
        <el-table-column 
          prop="confidence" 
          label="置信度" 
          width="120"
          sortable
        >
          <template #default="{ row, $index }">
            <div v-if="row.editing">
              <el-input-number
                v-model="row.confidence"
                :min="0"
                :max="1"
                :step="0.01"
                :precision="2"
                size="small"
                @blur="saveEdit(row, $index)"
              />
            </div>
            <div v-else>
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
            </div>
          </template>
        </el-table-column>
        
        <!-- 位置 -->
        <el-table-column 
          label="位置" 
          min-width="120"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <div v-if="(row.position || row.positions) && (row.position || row.positions).length > 0" class="positions">
              <el-tag
                v-for="(pos, index) in (row.position || row.positions).slice(0, 2)"
                :key="index"
                size="small"
                type="info"
                style="margin: 2px"
              >
                {{ pos.start }}-{{ pos.end }}
              </el-tag>
              <el-text v-if="(row.position || row.positions).length > 2" type="info" size="small">
                等{{ (row.position || row.positions).length }}处
              </el-text>
            </div>
            <el-text v-else type="placeholder" size="small">
              未标注位置
            </el-text>
          </template>
        </el-table-column>
        
        <!-- 出现次数 -->
        <el-table-column 
          prop="occurrence_count" 
          label="出现次数" 
          width="100"
          sortable
        >
          <template #default="{ row, $index }">
            <el-input-number
              v-if="row.editing"
              v-model="row.occurrence_count"
              :min="0"
              size="small"
              @blur="saveEdit(row, $index)"
            />
            <el-badge 
              v-else
              :value="row.occurrence_count || (row.position || row.positions)?.length || 0"
              :type="row.occurrence_count > 1 ? 'primary' : 'info'"
              class="count-badge"
            />
          </template>
        </el-table-column>
        
        <!-- 操作 -->
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row, $index }">
            <el-button-group v-if="!row.editing" size="small">
              <el-tooltip content="编辑" placement="top">
                <el-button
                  size="small"
                  @click="editEntity(row)"
                >
                  <el-icon><Edit /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="详情" placement="top">
                <el-button
                  size="small"
                  @click="viewEntityDetail(row)"
                >
                  <el-icon><View /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                <el-button
                  size="small"
                  type="danger"
                  @click="deleteEntity($index)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-tooltip>
            </el-button-group>
            <el-button-group v-else size="small">
              <el-tooltip content="保存" placement="top">
                <el-button
                  size="small"
                  type="primary"
                  @click="saveEdit(row, $index)"
                >
                  <el-icon><Check /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="取消" placement="top">
                <el-button
                  size="small"
                  @click="cancelEdit(row, $index)"
                >
                  <el-icon><Close /></el-icon>
                </el-button>
              </el-tooltip>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="filteredEntities.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!extracting" class="empty-state">
      <el-empty description="暂无实体识别结果或未进行识别">
        <template #image>
          <el-icon size="100" color="#c0c4cc">
            <Document />
          </el-icon>
        </template>
        <template #default>
          <div class="empty-actions">
            <p>您可以：</p>
            <div class="action-buttons">
              <el-button 
                v-if="canExtract" 
                type="primary" 
                @click="startEntityExtraction"
              >
                <el-icon><MagicStick /></el-icon>
                开始自动识别
              </el-button>
              <el-button 
                type="success" 
                @click="addManualEntity"
              >
                <el-icon><Plus /></el-icon>
                手动添加实体
              </el-button>
            </div>
          </div>
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
          <h4>正在进行实体识别...</h4>
          <p>这可能需要几分钟时间，请耐心等待</p>
          <el-progress 
            :percentage="extractionProgress" 
            :stroke-width="6" 
            :format="(percentage) => `${percentage.toFixed(2)}%`"
          />
        </div>
      </el-card>
    </div>

    <!-- 实体详情弹窗 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="`实体详情: ${currentEntity?.name}`"
      width="600px"
    >
      <div v-if="currentEntity" class="entity-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="实体名称">
            {{ currentEntity.name }}
          </el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ currentEntity.type }}
          </el-descriptions-item>
          <el-descriptions-item label="置信度">
            {{ Math.round(currentEntity.confidence * 100) }}%
          </el-descriptions-item>
          <el-descriptions-item label="出现次数">
            {{ currentEntity.positions?.length || 0 }}
          </el-descriptions-item>
        </el-descriptions>
        
        <div v-if="currentEntity.description" class="entity-description">
          <h5>描述信息：</h5>
          <p>{{ currentEntity.description }}</p>
        </div>
        
        <div v-if="currentEntity.positions" class="entity-positions">
          <h5>在文档中的位置：</h5>
          <div class="positions-list">
            <el-tag
              v-for="(pos, index) in currentEntity.positions"
              :key="index"
              style="margin: 4px"
            >
              位置 {{ pos.start }}-{{ pos.end }}
            </el-tag>
          </div>
        </div>
        
        <div v-if="currentEntity.context" class="entity-context">
          <h5>上下文：</h5>
          <el-scrollbar max-height="200px">
            <div class="context-text">
              {{ currentEntity.context }}
            </div>
          </el-scrollbar>
        </div>
      </div>
    </el-dialog>

    <!-- 异常17修复：新增实体弹窗 -->
    <el-dialog
      v-model="showAddEntityDialog"
      title="新增实体"
      width="600px"
      :destroy-on-close="true"
    >
      <el-form
        :model="newEntityForm"
        label-width="100px"
        label-position="left"
      >
        <el-form-item label="实体ID" required>
          <el-input-number
            v-model="newEntityForm.entity_id"
            :min="1"
            style="width: 200px"
          />
        </el-form-item>
        
        <el-form-item label="实体名称" required>
          <el-input
            v-model="newEntityForm.entity_name"
            placeholder="请输入实体名称"
            style="width: 400px"
          />
        </el-form-item>
        
        <el-form-item label="实体类型">
          <el-select
            v-model="newEntityForm.type"
            placeholder="选择实体类型"
            style="width: 400px"
            allow-create
            filterable
          >
            <el-option label="设备" value="设备" />
            <el-option label="人员" value="人员" />
            <el-option label="地点" value="地点" />
            <el-option label="部门" value="部门" />
            <el-option label="产品" value="产品" />
            <el-option label="技术指标" value="技术指标" />
            <el-option label="自定义" value="自定义" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="描述">
          <el-input
            v-model="newEntityForm.description"
            type="textarea"
            placeholder="请输入实体描述（可选）"
            :rows="3"
            style="width: 400px"
          />
        </el-form-item>
        
        <el-form-item label="置信度">
          <el-slider
            v-model="newEntityForm.confidence"
            :min="0"
            :max="1"
            :step="0.01"
            show-stops
            show-input
            style="width: 400px"
          />
        </el-form-item>
        
        <el-form-item label="出现次数">
          <el-input-number
            v-model="newEntityForm.occurrence_count"
            :min="1"
            style="width: 200px"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="cancelNewEntity">取消</el-button>
          <el-button type="primary" @click="saveNewEntity">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Check, Document, Loading, Search, Plus, Edit, View, Delete, Close, ArrowDown } from '@element-plus/icons-vue'

export default {
  name: 'EntityEvaluator',
  components: {
    MagicStick,
    Check,
    Document,
    Loading,
    Search,
    Plus,
    Edit,
    View,
    Delete,
    Close,
    ArrowDown
  },
  props: {
    selectedDocument: {
      type: Object,
      default: null
    },
    selectedTerms: {
      type: Array,
      default: () => []
    }
  },
  emits: ['entities-confirmed', 'entities-changed'],
  setup(props, { emit }) {
    // 响应式数据
    const entities = ref([])
    const confirmedEntities = ref([])
    const extracting = ref(false)
    const extractionProgress = ref(0)
    const searchKeyword = ref('')
    const typeFilter = ref('')
    
    // 异常17修复：新增实体弹窗相关变量
    const showAddEntityDialog = ref(false)
    const newEntityForm = ref({
      entity_id: 1,
      entity_name: '',
      type: '自定义',
      attributes: {},
      description: '',
      confidence: 1.0,
      position: [],
      occurrence_count: 1
    })
    const currentPage = ref(1)
    const pageSize = ref(50)
    const detailDialogVisible = ref(false)
    const currentEntity = ref(null)
    const entityTable = ref(null)
    
    // API基础URL
    const API_BASE_URL = '/api/graph'

    // 计算属性
    const entityTerms = computed(() => {
      return props.selectedTerms.filter(term => term.type === '实体')
    })

    const documentContentLength = computed(() => {
      if (!props.selectedDocument) return 0
      const content = props.selectedDocument.json_data?.text || props.selectedDocument.content || ''
      return content.length
    })

    const canExtract = computed(() => {
      return props.selectedDocument &&   // 只要有文档就可以进行实体识别
             !extracting.value
    })

    const filteredEntities = computed(() => {
      let result = entities.value

      // 搜索筛选
      if (searchKeyword.value) {
        const keyword = searchKeyword.value.toLowerCase()
        result = result.filter(entity => 
          (entity.entity_name || entity.name || '').toLowerCase().includes(keyword) ||
          (entity.type || '').toLowerCase().includes(keyword) ||
          (entity.description && entity.description.toLowerCase().includes(keyword))
        )
      }

      // 类型筛选
      if (typeFilter.value) {
        result = result.filter(entity => entity.type === typeFilter.value)
      }

      return result
    })

    const entityTypes = computed(() => {
      const types = new Set(entities.value.map(entity => entity.type))
      return Array.from(types).sort()
    })

    // 开始实体识别
    const startEntityExtraction = async () => {
      if (!canExtract.value) {
        ElMessage.warning('请确保已选择文档')
        return
      }

      extracting.value = true
      extractionProgress.value = 0
      entities.value = []
      confirmedEntities.value = []

      try {
        // 模拟进度更新
        const progressTimer = setInterval(() => {
          if (extractionProgress.value < 90) {
            extractionProgress.value = parseFloat((extractionProgress.value + Math.random() * 10).toFixed(2))
          }
        }, 500)

        const requestData = {
          document: {
            id: props.selectedDocument.document_id,
            name: props.selectedDocument.name,
            content: props.selectedDocument.json_data?.text || props.selectedDocument.content || ''
          },
          terms: entityTerms.value,
          document_id: props.selectedDocument.document_id?.toString() // 异常14新增：支持缓存机制
        }

        const response = await axios.post(`${API_BASE_URL}/entity-extraction`, requestData)
        
        clearInterval(progressTimer)
        extractionProgress.value = 100

        if (response.data && Array.isArray(response.data)) {
          entities.value = response.data
          if (entities.value.length > 0) {
            ElMessage.success(`成功识别 ${entities.value.length} 个实体`)
          } else {
            ElMessage.info('未检测到可识别的实体，您可以手动添加')
          }
        } else {
          entities.value = []
          ElMessage.warning('实体识别结果格式异常')
        }
      } catch (error) {
        console.error('实体识别失败:', error)
        clearInterval(progressTimer)
        
        const errorMessage = error.response?.data?.detail || error.message || '未知错误'
        
        // 详细的错误分类和友好提示
        if (error.response?.status === 400) {
          if (errorMessage.includes('文档内容不能为空') || errorMessage.includes('document')) {
            ElMessage({
              message: '当前文档内容为空，无法进行实体识别。请检查文档内容或手动添加实体。',
              type: 'info',
              duration: 5000
            })
          } else if (errorMessage.includes('术语') || errorMessage.includes('term')) {
            ElMessage({
              message: '术语配置问题。系统将使用通用识别模式，您也可以手动添加实体。',
              type: 'info',
              duration: 5000
            })
          } else {
            ElMessage({
              message: `参数错误：${errorMessage}`,
              type: 'warning',
              duration: 5000
            })
          }
        } else if (error.response?.status === 422) {
          ElMessage({
            message: '数据格式错误，请检查文档格式是否正确。',
            type: 'warning',
            duration: 5000
          })
        } else if (error.response?.status === 500) {
          ElMessage({
            message: '服务器处理出现问题，请稍后重试或联系管理员。可以先手动添加实体。',
            type: 'error',
            duration: 8000
          })
        } else if (error.code === 'ECONNABORTED' || errorMessage.includes('timeout')) {
          ElMessage({
            message: '识别请求超时，可能是文档内容较长。请稍后重试或分段处理文档。',
            type: 'warning',
            duration: 8000
          })
        } else if (error.code === 'NETWORK_ERROR' || !navigator.onLine) {
          ElMessage({
            message: '网络连接问题，请检查网络状态后重试。',
            type: 'error',
            duration: 5000
          })
        } else {
          ElMessage({
            message: `实体识别失败：${errorMessage}。您可以手动添加实体或稍后重试。`,
            type: 'warning',
            duration: 8000
          })
        }
        
        entities.value = []
        extractionProgress.value = 0
      } finally {
        extracting.value = false
      }
    }

    // 处理表格选择变化
    const handleSelectionChange = (selection) => {
      confirmedEntities.value = selection
      emit('entities-changed', selection)
    }

    // 全选实体
    const selectAllEntities = () => {
      const table = entityTable.value
      if (table) {
        filteredEntities.value.forEach(entity => {
          table.toggleRowSelection(entity, true)
        })
      }
    }

    // 清空选择
    const clearAllEntities = () => {
      const table = entityTable.value
      if (table) {
        table.clearSelection()
      }
    }

    // 确认选择
    const confirmSelection = async () => {
      if (confirmedEntities.value.length === 0) {
        ElMessage.warning('请先选择要确认的实体')
        return
      }

      try {
        await ElMessageBox.confirm(
          `确认选择 ${confirmedEntities.value.length} 个实体用于关系抽取？`,
          '确认实体选择',
          {
            confirmButtonText: '确认',
            cancelButtonText: '取消',
            type: 'info'
          }
        )

        // 异常14新增：保存实体到MySQL
        if (props.selectedDocument?.document_id) {
          try {
            const saveRequestData = {
              document_id: props.selectedDocument.document_id.toString(),
              entities: confirmedEntities.value
            }

            await axios.post(`${API_BASE_URL}/save-entities`, saveRequestData)
            ElMessage.success(`已确认并保存 ${confirmedEntities.value.length} 个实体`)
          } catch (saveError) {
            console.error('保存实体失败:', saveError)
            ElMessage.warning('实体确认成功，但保存到数据库失败，可在后续步骤中重试')
          }
        }

        emit('entities-confirmed', confirmedEntities.value)
      } catch {
        // 用户取消
      }
    }

    // 查看实体详情
    const viewEntityDetail = (entity) => {
      currentEntity.value = entity
      detailDialogVisible.value = true
    }

    // 获取实体标签类型
    const getEntityTagType = (type) => {
      const typeMap = {
        '设备': 'primary',
        '人员': 'success',
        '部门': 'warning',
        '产品': 'info',
        '工艺': 'danger',
        '自定义': 'primary'
      }
      return typeMap[type] || 'default'
    }

    // 获取置信度颜色
    const getConfidenceColor = (confidence) => {
      if (confidence >= 0.8) return '#67c23a'
      if (confidence >= 0.6) return '#e6a23c'
      if (confidence >= 0.4) return '#f56c6c'
      return '#909399'
    }

    // 手动添加实体
    const addManualEntity = async () => {
      try {
        const { value: entityName } = await ElMessageBox.prompt(
          '请输入实体名称',
          '手动添加实体',
          {
            confirmButtonText: '添加',
            cancelButtonText: '取消',
            inputPattern: /\S+/,
            inputErrorMessage: '实体名称不能为空'
          }
        )

        if (entityName) {
          const newEntity = {
            id: Date.now(), // 简单的ID生成
            name: entityName.trim(),
            type: '自定义',
            confidence: 1.0, // 手动添加的实体置信度为100%
            attributes: {},
            positions: []
          }
          
          entities.value.push(newEntity)
          ElMessage.success(`已添加实体: ${entityName}`)
        }
      } catch {
        // 用户取消
      }
    }

    // 编辑实体
    const editEntity = (entity) => {
      // 备份原始数据，用于取消时恢复
      entity._backup = { ...entity }
      entity.editing = true
    }

    // 保存编辑
    const saveEdit = (entity, index) => {
      try {
        // 验证必填字段
        if (!entity.entity_name && !entity.name) {
          ElMessage.warning('实体名称不能为空')
          return
        }
        
        // 删除备份数据
        delete entity._backup
        entity.editing = false
        
        // 触发数据更新事件
        emit('entities-changed', confirmedEntities.value)
        ElMessage.success('实体信息已保存')
      } catch (error) {
        ElMessage.error('保存失败: ' + error.message)
      }
    }

    // 取消编辑
    const cancelEdit = (entity, index) => {
      if (entity._backup) {
        // 恢复原始数据
        Object.assign(entity, entity._backup)
        delete entity._backup
      }
      entity.editing = false
    }

    // 删除实体
    const deleteEntity = async (index) => {
      try {
        await ElMessageBox.confirm(
          '确定要删除这个实体吗？此操作不可恢复。',
          '确认删除',
          {
            confirmButtonText: '删除',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )

        entities.value.splice(index, 1)
        ElMessage.success('实体已删除')
        
        // 更新确认列表
        const deletedEntity = entities.value[index]
        if (deletedEntity && confirmedEntities.value.includes(deletedEntity)) {
          const confirmedIndex = confirmedEntities.value.indexOf(deletedEntity)
          confirmedEntities.value.splice(confirmedIndex, 1)
        }
        
        emit('entities-changed', confirmedEntities.value)
      } catch {
        // 用户取消删除
      }
    }

    // 新增实体
    const addNewEntity = () => {
      // 异常17修复：改为弹窗形式新增实体
      showAddEntityDialog.value = true
      newEntityForm.value = {
        entity_id: entities.value.length + 1,
        entity_name: '',
        type: '自定义',
        attributes: {},
        description: '',
        confidence: 1.0,
        position: [],
        occurrence_count: 1
      }
    }
    
    // 异常17修复：保存新增实体
    const saveNewEntity = () => {
      if (!newEntityForm.value.entity_name.trim()) {
        ElMessage.warning('请输入实体名称')
        return
      }
      
      const newEntity = {
        ...newEntityForm.value,
        editing: false
      }
      
      entities.value.unshift(newEntity)
      showAddEntityDialog.value = false
      ElMessage.success('实体添加成功')
      
      // 触发变更事件
      emit('entities-changed', entities.value)
    }
    
    // 异常17修复：取消新增实体
    const cancelNewEntity = () => {
      showAddEntityDialog.value = false
    }

    // 导出实体数据
    const handleExport = (format) => {
      if (entities.value.length === 0) {
        ElMessage.warning('没有可导出的实体数据')
        return
      }

      try {
        const now = new Date()
        const timestamp = now.toISOString().slice(0, 19).replace(/:/g, '-')
        const fileName = `实体识别结果_${timestamp}`
        
        if (format === 'json') {
          exportAsJSON(fileName)
        } else if (format === 'excel') {
          exportAsExcel(fileName)
        } else if (format === 'csv') {
          exportAsCSV(fileName)
        }
        
        ElMessage.success(`已导出${entities.value.length}个实体为${format.toUpperCase()}格式`)
      } catch (error) {
        ElMessage.error('导出失败: ' + error.message)
      }
    }

    // 导出为JSON
    const exportAsJSON = (fileName) => {
      const data = {
        export_info: {
          timestamp: new Date().toISOString(),
          document_name: props.selectedDocument?.name || '未知文档',
          total_entities: entities.value.length
        },
        entities: entities.value.map(entity => ({
          entity_id: entity.entity_id || entity.id,
          entity_name: entity.entity_name || entity.name,
          type: entity.type,
          attributes: entity.attributes || {},
          description: entity.description || '',
          confidence: entity.confidence || 1.0,
          position: entity.position || entity.positions || [],
          occurrence_count: entity.occurrence_count || 0
        }))
      }
      
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      downloadFile(blob, `${fileName}.json`)
    }

    // 导出为CSV
    const exportAsCSV = (fileName) => {
      const headers = ['实体ID', '实体名称', '类型', '属性', '描述', '置信度', '出现次数', '位置信息']
      const rows = entities.value.map(entity => [
        entity.entity_id || entity.id,
        entity.entity_name || entity.name,
        entity.type || '',
        JSON.stringify(entity.attributes || {}),
        entity.description || '',
        entity.confidence || 1.0,
        entity.occurrence_count || 0,
        (entity.position || entity.positions || []).length > 0 ? 
          (entity.position || entity.positions).map(p => `${p.start}-${p.end}`).join(';') : ''
      ])
      
      const csvContent = [headers, ...rows]
        .map(row => row.map(field => `"${String(field).replace(/"/g, '""')}"`).join(','))
        .join('\n')
      
      const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' })
      downloadFile(blob, `${fileName}.csv`)
    }

    // 导出为Excel（简化版，实际可使用xlsx库）
    const exportAsExcel = (fileName) => {
      // 这里简化为CSV格式，实际项目中可以使用xlsx库生成真正的Excel文件
      exportAsCSV(fileName.replace('.xlsx', ''))
      ElMessage.info('Excel导出已简化为CSV格式，如需真正的Excel文件请安装xlsx库')
    }

    // 文件下载辅助函数
    const downloadFile = (blob, fileName) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    }

    // 异常23修复：页面初始化时立即检查实体表是否存在
    const checkExistingEntities = async () => {
      if (!props.selectedDocument?.document_id) {
        return
      }

      try {
        const response = await axios.get(`${API_BASE_URL}/documents/${props.selectedDocument.document_id}/entities`)
        
        if (response.data?.exists && response.data.entities && response.data.entities.length > 0) {
          // 表存在且有数据，直接加载
          entities.value = response.data.entities
          ElMessage.success(`加载已有实体数据：${response.data.entities.length} 个实体`)
          
          // 可以选择自动选中所有实体，或者让用户手动选择
          // confirmedEntities.value = response.data.entities
          // emit('entities-changed', confirmedEntities.value)
        } else {
          // 表不存在或无数据
          entities.value = []
          console.log(`实体表不存在，等待用户选择自动抽取或手动添加`)
        }
      } catch (error) {
        console.error('检查已有实体数据失败:', error)
        entities.value = []
      }
    }

    // 异常23修复：组件挂载时立即检查
    onMounted(() => {
      checkExistingEntities()
    })

    // 异常23修复：监听文档变化，自动重新检查
    watch(() => props.selectedDocument, () => {
      if (props.selectedDocument?.document_id) {
        checkExistingEntities()
      } else {
        entities.value = []
        confirmedEntities.value = []
      }
    })

    return {
      entities,
      confirmedEntities,
      extracting,
      extractionProgress,
      searchKeyword,
      typeFilter,
      currentPage,
      pageSize,
      detailDialogVisible,
      currentEntity,
      entityTable,
      entityTerms,
      documentContentLength,
      canExtract,
      filteredEntities,
      entityTypes,
      startEntityExtraction,
      handleSelectionChange,
      selectAllEntities,
      clearAllEntities,
      confirmSelection,
      addManualEntity,
      viewEntityDetail,
      getEntityTagType,
      getConfidenceColor,
      editEntity,
      saveEdit,
      cancelEdit,
      deleteEntity,
      addNewEntity,
      handleExport,
      // 异常17修复：新增实体弹窗相关
      showAddEntityDialog,
      newEntityForm,
      saveNewEntity,
      cancelNewEntity
    }
  }
}
</script>

<style scoped>
.entity-evaluator {
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

.entities-table {
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
  flex-wrap: wrap;
}

.entity-count-note {
  color: #909399;
  font-style: italic;
  margin-left: 8px;
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

.confidence-text {
  text-align: center;
  font-size: 12px;
  margin-top: 4px;
}

.positions {
  max-width: 150px;
  line-height: 1.5;
}

.count-badge {
  display: inline-block;
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

.empty-actions {
  margin-top: 16px;
}

.empty-actions p {
  margin-bottom: 16px;
  color: #606266;
  font-size: 14px;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 12px;
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

.entity-detail {
  padding: 16px 0;
}

.entity-description,
.entity-positions,
.entity-context {
  margin-top: 20px;
}

.entity-description h5,
.entity-positions h5,
.entity-context h5 {
  margin: 0 0 12px 0;
  color: #606266;
  font-size: 14px;
}

.positions-list {
  max-height: 120px;
  overflow-y: auto;
  line-height: 1.8;
}

.context-text {
  padding: 12px;
  background-color: #f8f9fa;
  border-radius: 4px;
  line-height: 1.6;
  color: #606266;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .table-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  
  .table-filters {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .table-header {
    flex-direction: column;
    align-items: stretch;
  }
  
  .table-title {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .entity-count-note {
    margin-left: 0;
    font-size: 12px;
  }
  
  .selection-actions {
    width: 100%;
    justify-content: flex-start;
  }
  
  .table-filters {
    flex-direction: column;
    gap: 8px;
  }
  
  .header-actions {
    flex-direction: column;
    gap: 8px;
  }
  
  /* 移动端表格优化 */
  .el-table {
    font-size: 12px;
  }
  
  .confidence-text {
    font-size: 10px;
  }
}
</style>