<template>
    <!-- 查询模块 -->
  <div class="query-module">
    <el-card>
      <div class="custom-query-container">
        <!-- 第一行：数据库选择和查询方式 -->
        <div class="query-row first-row">
          <!-- 数据库选择 -->
          <div class="query-item">
            <span class="query-label">数据库</span>
            <el-select
              v-model="currentDatabase"
              placeholder="选择数据库"
              style="width: 180px"
            >
              <el-option
                v-for="db in databaseList"
                :key="db"
                :label="db"
                :value="db"
              />
            </el-select>
          </div>

          <!-- 查询方式切换 -->
          <div class="query-item">
            <span class="query-label">查询方式</span>
            <el-radio-group v-model="queryMode">
              <el-radio-button label="cypher">Cypher查询</el-radio-button>
              <el-radio-button label="filter">筛选查询</el-radio-button>
            </el-radio-group>
          </div>
        </div>

        <!-- 第二行：具体查询内容 -->
        <div class="query-row second-row">
          <!-- Cypher查询 -->
          <template v-if="queryMode === 'cypher'">
            <div class="cypher-query-container">
              <el-input
                v-model="cypherQuery"
                placeholder="输入Cypher查询语句"
                clearable
                style="flex: 1; margin-right: 10px"
              />
              <el-button
                type="primary"
                @click="executeCypherQuery"
                :disabled="!cypherQuery"
              >
                执行
              </el-button>
            </div>
          </template>

          <!-- 筛选查询 -->
          <template v-else>
            <div class="filter-query-container">
              <!-- 查询类型 -->
              <div class="query-item">
                <span class="query-label">查询类型</span>
                <el-select v-model="filterType" placeholder="选择类型" clearable style="width: 120px">
                  <el-option label="节点" value="node" />
                  <el-option label="关系" value="relationship" />
                </el-select>
              </div>

              <!-- 标签 -->
              <div class="query-item">
                <span class="query-label">标签</span>
                <el-select
                  v-model="selectedLabel"
                  placeholder="选择标签"
                  :disabled="!availableLabels[filterType]?.length"
                  clearable
                  style="width: 150px"
                >
                  <el-option
                    v-for="label in availableLabels[filterType] || []"
                    :key="label"
                    :label="label"
                    :value="label"
                  />
                </el-select>
              </div>

              <!-- 关键字 -->
              <div class="query-item">
                <span class="query-label">关键字</span>
                <el-input
                  v-model="keyword"
                  placeholder="输入属性关键字"
                  clearable
                  :disabled="filterType === 'relationship'"
                  style="width: 280px"
                />
              </div>

              <el-button
                type="primary"
                @click="executeFilterQuery"
                :disabled="!filterType"
              >
                查询
              </el-button>
            </div>
          </template>
        </div>
      </div>
    </el-card>
  </div>

  <!-- 添加标签对话框 -->
  <el-dialog v-model="showAddLabelDialog" title="添加标签" width="400px">
    <el-form :model="labelForm" label-position="top">
      <el-form-item label="选择标签">
        <el-select
          v-model="labelForm.newLabel"
          placeholder="选择标签"
          filterable
          allow-create
          style="width: 100%"
        >
          <el-option
            v-for="label in availableLabels.node"
            :key="label"
            :label="label"
            :value="label"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showAddLabelDialog = false">取消</el-button>
      <el-button type="primary" @click="addLabel">确认</el-button>
    </template>
  </el-dialog>


  <div class="graph-container">
    <!-- 图谱可视化区域 -->
    <div ref="graphContainer" class="graph-area">
      <!-- 修改后的标签颜色图例 -->
      <div class="legend-container">
        <div
          v-for="(color, label) in labelColorMap"
          :key="label"
          class="legend-item"
          @click="queryNodesByLabel(label)"
          :title="`点击查询所有${label}节点`"
          v-show="!isLegendCollapsed"
        >
          <div class="legend-color" :style="{ backgroundColor: color }"></div>
          <span class="legend-label">{{ label }}</span>
        </div>

        <!-- 添加折叠按钮 -->
        <div class="collapse-legend-btn" @click="toggleLegendCollapse">
          <el-icon :size="16">
            <ArrowDown v-if="isLegendCollapsed" />
            <ArrowUp v-else />
          </el-icon>
        </div>
      </div>

      <!-- 新增控制按钮组 - 现在放在graph-area内部 -->
      <div class="graph-controls">
        <el-button type="primary" @click="showAddNodeDialog = true">
          <el-icon><Plus /></el-icon>新增节点
        </el-button>
        <el-button type="success" @click="startCreateRelationship" :disabled="!canCreateRelationship">
          <el-icon><Connection /></el-icon>新增关系
        </el-button>
      </div>
    </div>


    <!-- 修改新增节点对话框 -->
<el-dialog v-model="showAddNodeDialog" title="新增节点" width="500px">
  <el-form :model="newNodeForm" label-position="top">
    <el-form-item label="节点标签" required>
      <el-input v-model="newNodeForm.label" placeholder="请输入节点标签" />
    </el-form-item>

    <!-- 改为属性编辑方式 -->
    <el-form-item label="节点属性">
      <div v-for="(item, index) in newNodeForm.propertyList" :key="index" class="property-item">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
          <el-input
            v-model="item.key"
            placeholder="属性名"
            style="width: 120px"
            @change="updateNewNodeProperty(index)"
          />
          <el-input
            v-model="item.value"
            placeholder="属性值"
            style="flex: 1"
            @change="updateNewNodeProperty(index)"
          />
          <el-button
            type="danger"
            @click="removeNewNodeProperty(index)"
            :icon="Delete"
            circle
          />
        </div>
      </div>
      <div style="display: flex; gap: 8px; margin-top: 10px;">
        <el-input v-model="newPropertyKey" placeholder="属性名" style="flex: 1" />
        <el-input v-model="newPropertyValue" placeholder="属性值" style="flex: 1" />
        <el-button
          type="primary"
          @click="addNewNodeProperty"
          :disabled="!newPropertyKey || !newPropertyValue"
        >
          添加属性
        </el-button>
      </div>
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="showAddNodeDialog = false">取消</el-button>
    <el-button type="primary" @click="createNewNode">确认</el-button>
  </template>
</el-dialog>



    <!-- 右侧属性板 -->
    <div v-if="selectedItem" class="property-panel" :class="{ 'collapsed': isPanelCollapsed }">
      <div class="collapse-handle" @click="togglePanelCollapse">
        <el-icon :size="20">
          <ArrowRight v-if="!isPanelCollapsed" />
          <ArrowLeft v-else />
        </el-icon>
      </div>



      <el-card class="property-card" v-show="!isPanelCollapsed">
        <template #header>
          <div class="card-header">
            <span>{{ selectedItem.type === 'node' ? '节点信息' : '关系信息' }}</span>
          </div>
        </template>

          <!-- 在节点属性部分添加图片显示区域 -->
        <div v-if="selectedItem.type === 'node'
        && (selectedItem.data.labels.includes('图片')  || selectedItem.data.labels.includes('标志图片')
        || selectedItem.data.labels.includes('设备图片')) && imageUrl"
             style="margin: 15px 0;">
          <el-image
            :src="imageUrl"
            fit="contain"
            style="width: 100%; height: 200px;"
            :preview-src-list="[imageUrl]"
          />
        </div>

         <div v-if="selectedItem.type === 'node'">
        <!-- 基本信息区域（固定高度） -->
        <div class="basic-info-section">
          <el-form label-position="top">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
              <span style="font-size: 16px; font-weight: bold;">节点属性</span>
              <el-button
                type="primary"
                @click="toggleEditMode"
                :icon="isEditMode ? Check : Edit"
              >
                {{ isEditMode ? '完成编辑' : '编辑属性' }}
              </el-button>
            </div>

            <!-- 节点ID -->
            <el-form-item label="节点ID">
              <el-input
                :value="selectedItem.data.id"
                readonly
                style="width: 100%"
                class="copyable-input"
              >
                <template #append>
                  <el-button
                    :icon="DocumentCopy"
                    @click="copyToClipboard(selectedItem.data.id)"
                  />
                </template>
              </el-input>
            </el-form-item>

            <!-- 标签 -->
            <el-form-item label="标签">
              <div class="label-container">
                <el-tag
                  v-for="label in selectedItem.data.labels"
                  :key="label"
                  closable
                  @close="removeLabel(label)"
                >
                  {{ label }}
                </el-tag>
                <el-button
                  v-if="isEditMode"
                  type="primary"
                  size="small"
                  @click="showAddLabelDialog = true"
                >
                  添加标签
                </el-button>
              </div>
            </el-form-item>
          </el-form>
        </div>

        <!-- 属性列表区域（可滚动） -->
        <div class="scrollable-properties">
          <el-divider />

          <!-- 属性列表 -->
          <div v-for="(value, key) in selectedItem.data.properties" :key="key" class="property-item">
            <el-form-item>
              <div style="display: flex; flex-direction: column; width: 100%;">
                <!-- 标签和复制按钮 -->
                <div style="display: flex; align-items: center; min-width: 150px; margin-bottom: 8px;">
                  <span style="font-weight: 500; margin-right: 8px;">{{ key }}</span>
                  <el-button
                    v-if="!isEditMode"
                    :icon="DocumentCopy"
                    @click="copyToClipboard(selectedItem.data.properties[key])"
                    size="small"
                    circle
                    plain
                  />
                </div>

                <!-- 输入框和删除按钮 -->
                <div style="display: flex; align-items: center;">
                  <el-input
                    v-model="selectedItem.data.properties[key]"
                    :disabled="!isEditMode"
                    style="flex-grow: 1;"
                    :readonly="!isEditMode"
                    type="textarea"
                    :autosize="{ minRows: 1, maxRows: 4 }"
                  />
                  <el-button
                    v-if="isEditMode"
                    type="danger"
                    @click="deleteProperty(key)"
                    style="margin-left: 8px;"
                    :icon="Delete"
                    circle
                  />
                </div>
              </div>
            </el-form-item>
          </div>

          <!-- 新增属性表单 -->
         <el-form-item v-if="isEditMode" style="display: block;">
          <template #label>
            <div style="display: block; width: 100%; font-weight: 500; margin-bottom: 8px;">
              新增属性
            </div>
          </template>

          <div style="display: flex; gap: 8px; width: 100%; margin-top: 8px;">
            <el-input v-model="newPropertyKey" placeholder="属性名" />
            <el-input v-model="newPropertyValue" placeholder="属性值" />
            <el-button
              type="primary"
              @click="addProperty"
              :disabled="!newPropertyKey || !newPropertyValue"
            >
              添加
            </el-button>
          </div>
        </el-form-item>
        </div>

        <!-- 操作按钮区域（固定高度） -->
        <div class="action-buttons">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-button type="success" @click="expandSelectedNode" style="width: 100%; margin-bottom: 10px;">
                展开节点
              </el-button>
            </el-col>
            <el-col :span="12">
              <el-button
                type="primary"
                @click="saveNodeChanges"
                style="width: 100%; margin-bottom: 10px;"
                :disabled="!isEditMode"
              >
                保存更改
              </el-button>
            </el-col>
            <el-col :span="12">
              <el-button type="warning" @click="showExpandDialog = true" style="width: 100%; margin-bottom: 10px;">
                扩展节点
              </el-button>
            </el-col>
            <el-col :span="12">
              <el-button type="danger" @click="deleteNode" style="width: 100%;">
                删除节点
              </el-button>
            </el-col>
          </el-row>
        </div>
      </div>

        <!-- 关系属性 -->
        <div v-else>
          <el-form label-position="top">
            <el-form-item label="关系类型">
              <el-input v-model="selectedItem.data.label" @change="updateRelationshipType" />
            </el-form-item>

            <el-divider />

            <div class="relationship-info">
              <p>From: {{ selectedItem.data.source.properties.name }}</p>
              <p>To: {{ selectedItem.data.target.properties.name }}</p>
            </div>

            <el-button type="danger" @click="deleteRelationship">删除关系</el-button>
          </el-form>
        </div>

        <!-- 关系创建 -->
        <div v-if="isCreatingRelationship" class="relationship-creating-hint">
          <el-alert type="info" show-icon :closable="false">
            正在创建关系: 请依次选择源节点和目标节点
            <el-button size="small" @click="cancelCreateRelationship">取消</el-button>
          </el-alert>
        </div>
      </el-card>
    </div>

    <!-- 修改扩展节点对话框 -->
<el-dialog v-model="showExpandDialog" title="扩展节点" width="500px">
  <el-form :model="expandForm" label-position="top">
    <el-form-item label="新的节点标签">
      <el-input v-model="expandForm.newNodeLabel" />
    </el-form-item>

    <el-form-item label="关系类型">
      <el-input v-model="expandForm.relationshipType" />
    </el-form-item>

    <el-form-item label="关系方向">
      <el-radio-group v-model="expandForm.direction">
        <el-radio label="out">由当前节点指向新节点</el-radio>
        <el-radio label="in">由新节点指向当前节点</el-radio>
      </el-radio-group>
    </el-form-item>

    <!-- 改为属性编辑方式 -->
    <el-form-item label="新节点属性">
      <div v-for="(item, index) in expandForm.propertyList" :key="index" class="property-item">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
          <el-input
            v-model="item.key"
            placeholder="属性名"
            style="width: 120px"
            @change="updateExpandProperty(index)"
          />
          <el-input
            v-model="item.value"
            placeholder="属性值"
            style="flex: 1"
            @change="updateExpandProperty(index)"
          />
          <el-button
            type="danger"
            @click="removeExpandProperty(index)"
            :icon="Delete"
            circle
          />
        </div>
      </div>
      <div style="display: flex; gap: 8px; margin-top: 10px;">
        <el-input v-model="newExpandPropertyKey" placeholder="属性名" style="flex: 1" />
        <el-input v-model="newExpandPropertyValue" placeholder="属性值" style="flex: 1" />
        <el-button
          type="primary"
          @click="addExpandProperty"
          :disabled="!newExpandPropertyKey || !newExpandPropertyValue"
        >
          添加属性
        </el-button>
      </div>
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="showExpandDialog = false">关闭</el-button>
    <el-button type="primary" @click="expandNode">确认</el-button>
  </template>
</el-dialog>
  </div>
</template>

<script setup>
import {ref, onMounted, watch, computed, onUnmounted} from 'vue';
import * as d3 from 'd3';
import { ElMessage, ElMessageBox } from 'element-plus';
import { DocumentCopy, Delete, Edit, Check,
  ArrowLeft, ArrowRight, Plus, Connection, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import neo4j from 'neo4j-driver'
import axios from 'axios'; // Add axios for API calls


const driver = neo4j.driver(
    'bolt://localhost:7687',
  neo4j.auth.basic(
    'neo4j', '12345678'
  )
)

const NODE_COLORS = [
  '#2E86C1',  // 深蓝色
  '#A93226',  // 深红色
  '#1E8449',  // 深绿色
  '#7D3C98',  // 深紫色
  '#CA6F1E',  // 深橙色
  '#1A5276'   // 深青色
];


// Reactive data 响应式数据
const graphContainer = ref(null);
const selectedItem = ref(null);
const showExpandDialog = ref(false);
const expandForm = ref({
  newNodeLabel: '',
  relationshipType: '',
  direction: 'out',
  propertyList: [], // 改为数组形式，包含key和value
  newNodeProperties: {} // 最终生成的属性对象
});

const hoveredNodeId = ref(null);

// 展示数据
const dataNodes = ref([]);
const dataRelationships = ref([]);

// D3 graph 变量
let svg, simulation, link, node, edgeLabel;

// 标签-颜色映射
const labelColorMap = ref({});

// 查询模块响应式数据
const currentDatabase = ref('main');
const databaseList = ref([]); // 示例数据库列表
const queryMode = ref('cypher');
const cypherQuery = ref('');
const filterType = ref('node');
const selectedLabel = ref('');
const keyword = ref('');
const availableLabels = ref([]);

// 编辑模式响应式数据
const isEditMode = ref(false);
const newPropertyKey = ref('');
const newPropertyValue = ref('');

// 属性板折叠
const isPanelCollapsed = ref(false)

// 新增节点和关系相关状态
const showAddNodeDialog = ref(false)
const newNodeForm = ref({
  label: '',
  propertyList: [], // 改为数组形式，包含key和value
  properties: {} // 最终生成的属性对象
});

// 创建关系相关状态
const isCreatingRelationship = ref(false)
const relationshipSource = ref(null)
const canCreateRelationship = computed(() => dataNodes.value.length > 1) // 至少有两个节点才能创建关系

// Add new reactive data for image handling
const imageUrl = ref(null);
const fastApiBaseUrl = '';

// Add new reactive data for label management
const showAddLabelDialog = ref(false);
const labelForm = ref({
  newLabel: ''
});

// 在setup()中添加新的响应式变量
// const newPropertyKey = ref('');
// const newPropertyValue = ref('');
const newExpandPropertyKey = ref('');
const newExpandPropertyValue = ref('');

// 图例标签折叠相关
const isLegendCollapsed = ref(false)

// 添加方法
function toggleLegendCollapse() {
  isLegendCollapsed.value = !isLegendCollapsed.value
}

// 修改节点双击事件处理
const handleNodeDblClick = (event, d) => {
  event.stopPropagation();
  selectItem({ type: 'node', data: d });
  expandSelectedNode(); // 执行展开节点操作
};


// 修改新增节点表单初始化
// const newNodeForm = ref({
//   label: '',
//   properties: {} // 改为对象形式
// });

// 修改扩展节点表单初始化
// const expandForm = ref({
//   newNodeLabel: '',
//   relationshipType: '',
//   direction: 'out',
//   newNodeProperties: {} // 改为对象形式
// });


// 监听数据库变化
watch(currentDatabase, async (newDb) => {
  // 清空查询条件
  cypherQuery.value = '';
  filterType.value = 'node';
  selectedLabel.value = '';
  keyword.value = '';

  // 重新加载标签
  await loadAvailableLabels();
  await initData();
  // initGraph();
  // resetSimulation();
  renderGraph();
});

// 初始化图谱
onMounted(async () => {
  await loadAvailableDatabases();
  await loadAvailableLabels();
  ElMessage.success(`已查询所有类型的节点`);
  await initData();

  initGraph();
  renderGraph();
});

// 新增方法：根据标签查询节点
async function queryNodesByLabel(label) {
  // 设置筛选查询模式
  queryMode.value = 'filter';
  filterType.value = 'node';
  selectedLabel.value = label;
  keyword.value = '';

  // 执行查询
  await executeFilterQuery();

  // 提示用户
  ElMessage.success(`已查询所有 ${label} 类型的节点`);
}

// 切换属性板折叠状态
function togglePanelCollapse() {
  isPanelCollapsed.value = !isPanelCollapsed.value
}

// 切换编辑模式
function toggleEditMode() {
  if (isEditMode.value) {
    // 从编辑模式切换回只读模式时自动保存
    saveNodeChanges();
  }
  isEditMode.value = !isEditMode.value;
  newPropertyKey.value = '';
  newPropertyValue.value = '';
}

// 复制到剪贴板功能
function copyToClipboard(text) {
  navigator.clipboard.writeText(text)
    .then(() => ElMessage.success('已复制到剪贴板'))
    .catch(() => ElMessage.error('复制失败'))
}

// 开始创建关系
function startCreateRelationship() {
  isCreatingRelationship.value = true
  relationshipSource.value = null
  ElMessage.info('请先选择源节点')
}

// 结束创建关系
function cancelCreateRelationship() {
  isCreatingRelationship.value = false
  relationshipSource.value = null
}


// 加载可用数据库
async function loadAvailableDatabases(){
  const session = driver.session()
  try {
    const result = await session.run('SHOW DATABASES');
    const databases = result.records.map(record => record.get('name'));
    databaseList.value = filterDatabases(databases, ['ontology', 'system'])
  } finally {
    await session.close()
  }
}

// 从数据库列表中删除非文档数据库
function filterDatabases(databases, excludeList) {
    return databases.filter(db => !excludeList.includes(db));
}


// 加载可用标签
async function loadAvailableLabels() {
  const session = driver.session({ database: currentDatabase.value });
  try {
    // 获取节点标签
    const labelsResult = await session.run('CALL db.labels() YIELD label RETURN collect(label) as labels');

    // 获取关系类型
    const relTypesResult = await session.run('CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as relTypes');

    availableLabels.value = {
      node: labelsResult.records[0].get('labels'),
      relationship: relTypesResult.records[0].get('relTypes')
    };


    // 更新标签颜色映射
    const newLabels = labelsResult.records[0].get('labels');
    const newColorMap = {};
    newLabels.forEach((label, index) => {
      newColorMap[label] = NODE_COLORS[index % NODE_COLORS.length];
    });
    labelColorMap.value = newColorMap;
  } catch (error) {
    ElMessage.error('加载可用标签失败: ' + error.message);
  } finally {
    await session.close();
  }
}

// 执行Cypher查询
async function executeCypherQuery() {
  const session = driver.session({ database: currentDatabase.value });
  try {
    const result = await session.run(cypherQuery.value);

    // 解析结果并更新图形数据
    // 这里需要根据实际Cypher查询结果格式调整
    const nodes = [];
    const relationships = [];

    // 示例解析逻辑（需根据实际查询调整）
    result.records.forEach(record => {
      record.keys.forEach(key => {
        const value = record.get(key);
        if (value instanceof neo4j.types.Node) {
          nodes.push({
            id: value.identity.toString(),
            labels: value.labels,
            properties: value.properties
          });
        } else if (value instanceof neo4j.types.Relationship) {
          relationships.push({
            id: value.identity.toString(),
            source: value.start.toString(),
            target: value.end.toString(),
            label: value.type
          });
        }
      });
    });

    dataNodes.value = nodes;
    dataRelationships.value = relationships;

    // resetSimulation();
    renderGraph();

    ElMessage.success(`查询成功，找到 ${nodes.length} 个节点和 ${relationships.length} 条关系`);
  } catch (error) {
    ElMessage.error('查询失败: ' + error.message);
  } finally {
    await session.close();
  }
}

// 执行筛选查询
async function executeFilterQuery() {
  const session = driver.session({ database: currentDatabase.value });
  try {
    let query = '';
    let result;

    if (filterType.value === 'node') {
      // 节点查询
      query = `MATCH (n${selectedLabel.value ? `:${selectedLabel.value}` : ''})
               ${keyword.value ? 'WHERE ANY(key IN keys(n) WHERE n[key] CONTAINS $keyword)' : ''}
               RETURN n LIMIT 200`;
      result = await session.run(query, { keyword: keyword.value });
    } else {
      // 关系查询 - 查询指定类型的关系及关联节点
      query = `MATCH (a)-[r${selectedLabel.value ? `:${selectedLabel.value}` : ''}]->(b)
               RETURN a, r, b LIMIT 200`;
      result = await session.run(query);
    }

    // 解析结果
    const nodes = [];
    const relationships = [];
    const nodeIds = new Set(); // 用于去重

    if (filterType.value === 'node') {
      // 节点查询结果处理
      result.records.forEach(record => {
        const node = record.get(0);
        nodes.push({
          id: node.identity.toString(),
          labels: node.labels,
          properties: node.properties
        });
      });
    } else {
      // 关系查询结果处理
      result.records.forEach(record => {
        const sourceNode = record.get('a');
        const rel = record.get('r');
        const targetNode = record.get('b');

        // 添加源节点
        if (!nodeIds.has(sourceNode.identity.toString())) {
          nodes.push({
            id: sourceNode.identity.toString(),
            labels: sourceNode.labels,
            properties: sourceNode.properties
          });
          nodeIds.add(sourceNode.identity.toString());
        }

        // 添加目标节点
        if (!nodeIds.has(targetNode.identity.toString())) {
          nodes.push({
            id: targetNode.identity.toString(),
            labels: targetNode.labels,
            properties: targetNode.properties
          });
          nodeIds.add(targetNode.identity.toString());
        }

        // 添加关系
        relationships.push({
          id: rel.identity.toString(),
          source: sourceNode.identity.toString(),
          target: targetNode.identity.toString(),
          label: rel.type
        });
      });
    }

    dataNodes.value = nodes;
    dataRelationships.value = relationships;
    renderGraph();

    ElMessage.success(`找到 ${nodes.length} 个节点和 ${relationships.length} 条关系`);
  } catch (error) {
    ElMessage.error('查询失败: ' + error.message);
  } finally {
    await session.close();
  }
}

// 获取图谱数据
async function fetchGraphData() {
  const session = driver.session({
    database: currentDatabase.value
  });
  try {
    // 首先获取所有标签类型
    const labelsResult = await session.run(`
      CALL db.labels() YIELD label
      RETURN collect(label) as labels
    `);
    const allLabels = labelsResult.records[0].get('labels');

    // 为每种标签分配颜色
    allLabels.forEach((label, index) => {
      labelColorMap.value[label] = NODE_COLORS[index % NODE_COLORS.length];
    });

    // 获取最多200个节点
    const nodesResult = await session.run('MATCH (n) RETURN n LIMIT 200');
    const nodes = nodesResult.records.map(record => ({
      id: record.get('n').identity.toString(),
      labels: record.get('n').labels,
      properties: record.get('n').properties
    }));

    // 如果没有任何节点，返回空数据
    if (nodes.length === 0) {
      return { nodes: [], relationships: [] };
    }
    // 获取这些节点之间的所有关系
    const nodeIds = nodes.map(n => parseInt(n.id));
    const relsResult = await session.run(`
      MATCH (a)-[r]->(b)
      WHERE ID(a) IN $nodeIds AND ID(b) IN $nodeIds
      RETURN a, r, b
    `, { nodeIds });

    const relationships = relsResult.records.map(record => ({
      id: record.get('r').identity.toString(),
      source: record.get('a').identity.toString(),
      target: record.get('b').identity.toString(),
      label: record.get('r').type
    }));
    return { nodes, relationships };
  } finally {
    await session.close();
  }
}

// 初始化数据
async function initData() {
  // 在组件中使用
  const {nodes, relationships} = await fetchGraphData()
  dataNodes.value = nodes
  // console.log(dataNodes.value.length > 1)
  // console.log(canCreateRelationship.value)
  dataRelationships.value = relationships
}

// 在D3变量部分添加以下变量
let zoom;
let g; // 包含所有图形元素的组

// 修改initGraph函数以设置缩放行为
function initGraph() {
  svg = d3.select(graphContainer.value)
    .append('svg')
    .attr('width', '100%')
    .attr('height', '100%');

  // 添加一个组元素用于缩放和平移
  g = svg.append('g');
  ElMessage.success(`找到 ${g.selectAll('*')}`);
  // 创建箭头标记（保持不变）
  svg.append('defs').append('marker')
    .attr('id', 'arrowhead')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 25)
    .attr('refY', 0)
    .attr('orient', 'auto')
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('xoverflow', 'visible')
    .append('svg:path')
    .attr('d', 'M 0,-5 L 10,0 L 0,5')
    .attr('fill', '#999');

  // 初始化力导向图（保持不变）
  simulation = d3.forceSimulation()
    .force('link', d3.forceLink().id(d => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(
      graphContainer.value.clientWidth / 2,
      graphContainer.value.clientHeight / 2
    ));

  // 设置缩放行为
  zoom = d3.zoom()
    .scaleExtent([0.1, 8]) // 最小和最大缩放级别
    .on('zoom', (event) => {
      g.attr('transform', event.transform);
    });

  svg.call(zoom);
}


// 修改renderGraph函数，将所有图形元素放在g元素下
function renderGraph() {

  // 清除现有元素（现在清除的是g元素内的内容）
  g.selectAll('*').remove();

  // 创建连线（关系）
  link = g.append('g')
    .selectAll('line')
    .data(dataRelationships.value)
    .enter()
    .append('line')
    .attr('class', 'link')
    .attr('marker-end', 'url(#arrowhead)')
    .style('stroke', '#999')
    .style('stroke-width', 2)
    .on('click', (event, d) => {
      event.stopPropagation();
      selectItem({ type: 'relationship', data: d });
    });

  // 创建边标签
  edgeLabel = g.append('g')
    .selectAll('text')
    .data(dataRelationships.value)
    .enter()
    .append('text')
    .attr('font-size', 10)
    .attr('fill', '#666')
    .text(d => d.label)
    .on('click', (event, d) => {
      event.stopPropagation();
      selectItem({ type: 'relationship', data: d });
    })


  // 创建节点（现在放在g元素下）
  node = g.append('g')
    .selectAll('g')
    .data(dataNodes.value)
    .enter()
    .append('g')
    .call(d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended)
    )
    .on('mouseover', (event, d) => {
      hoveredNodeId.value = d.id;
      highlightConnected(d.id);
    })
    .on('mouseout', () => {
      hoveredNodeId.value = null;
      resetHighlight();
    })
    .on('click', (event, d) => {
      event.stopPropagation();
      selectItem({ type: 'node', data: d });

    })
    .on('dblclick', handleNodeDblClick); // 添加双击事件

  // 添加节点圆形（保持不变）
  node.append('circle')
    .attr('r', 26)
    .attr('fill', d => labelColorMap.value[d.labels[0]] || '#cccccc'); // Fallback color

  // 添加节点标签（保持不变）
  node.append('text')
    .attr('dy', 0) // 重置垂直偏移
    .attr('text-anchor', 'middle')
    .style('font-size', '10px')
    .style('fill', 'white')
    .each(function(d) {
      const text = d.properties.name || d.id;
      const formattedText = formatNodeText(text); // 格式化文本
      const lines = formattedText.split('\n'); // 分割行

      const textElement = d3.select(this);
      lines.forEach((line, i) => {
        textElement.append('tspan') // 使用<tspan>实现多行
          .attr('x', 0)
          .attr('dy', i === 0 ? '0' : '1.2em') // 设置行间距
          .text(line);
      });
    });

  // 更新力导向图（保持不变）
  simulation.nodes(dataNodes.value);
  simulation.force('link').links(dataRelationships.value);
  simulation.alpha(1).restart(); // 强制重新布局
  simulation.on('tick', ticked);




  // 高亮相关节点和边
  function highlightConnected(nodeId) {
    // 高亮当前节点
    node.select('circle')
      .style('stroke', d => d.id === nodeId ? '#ffcc00' : null)
      .style('stroke-width', d => d.id === nodeId ? 3 : null)
      .style('cursor', 'pointer'); // 更改光标样式为手型

    node.select('text')
      .style('cursor', 'pointer'); // 更改光标样式为手型

    // 高亮相连的边
    link.style('stroke', d =>
      d.source.id === nodeId || d.target.id === nodeId ? '#ffcc00' : '#999'
    ).style('stroke-width', d =>
      d.source.id === nodeId || d.target.id === nodeId ? 3 : 2
    ).style('cursor', 'pointer'); // 更改光标样式为手型;

    // 高亮相邻节点
    const connectedNodeIds = new Set();
    dataRelationships.value.forEach(r => {
      if (r.source.id === nodeId) connectedNodeIds.add(r.target.id);
      if (r.target.id === nodeId) connectedNodeIds.add(r.source.id);
    });

    node.select('circle')
      .style('stroke', d => connectedNodeIds.has(d.id) ? '#ffcc00' : null)
      .style('stroke-width', d => connectedNodeIds.has(d.id) ? 3 : null);
  }

  function resetHighlight() {
    node.select('circle')
      .style('stroke', null)
      .style('stroke-width', null);

    link.style('stroke', '#999')
      .style('stroke-width', 2);
  }


  function ticked() {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);

    edgeLabel
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2);

    node.attr('transform', d => `translate(${d.x},${d.y})`);
  }
}


function dragstarted(event, d) {
  if (!event.active) simulation.alphaTarget(0.3).restart();
  d.fx = d.x;
  d.fy = d.y;
}

function dragged(event, d) {
  d.fx = event.x;
  d.fy = event.y;
}

function dragended(event, d) {
  if (!event.active) simulation.alphaTarget(0);
  d.fx = null;
  d.fy = null;
}

// 选中对象
function selectItem(item) {
  if (isCreatingRelationship.value && item.type === 'node') {
    if (!relationshipSource.value) {
      relationshipSource.value = item.data
      ElMessage.success('已选择源节点，请选择目标节点')
    } else {
      // 创建关系
      createNewRelationship(relationshipSource.value, item.data)
      isCreatingRelationship.value = false
      relationshipSource.value = null
    }
    return
  }


  selectedItem.value = item;
  imageUrl.value = null; // Reset image when selecting new item
  // Handle image node
  if (item.type === 'node' &&
    (item.data.labels.includes('图片') ||
     item.data.labels.includes('设备图片') ||
     item.data.labels.includes('标志图片')))
  {
      if (item.data.properties.path){
        console.log(111)
        fetchImage(item.data.properties.path);
      }
      else {
        console.log(222)
        fetchImage(item.data.properties.name[0]);
      }
  }

  // Highlight selected item
  if (item.type === 'node') {
    node.select('circle').style('stroke', null);
    node.filter(d => d.id === item.data.id).select('circle')
      .style('stroke', '#ffcc00')
      .style('stroke-width', 3);

    // 重置所有边的样式
    link.style('stroke', '#999').style('stroke-width', 2);
  } else {
    // 先重置所有边的样式
    link.style('stroke', '#999').style('stroke-width', 2);

    // 然后高亮选中的边
    link.filter(d => d.id === item.data.id)
      .style('stroke', '#ffcc00')
      .style('stroke-width', 3);

    // 重置所有节点的样式
    node.select('circle').style('stroke', null).style('stroke-width', null);
  }
}

// 查询图片
async function fetchImage(path) {
  console.log(path)
  try {
    const pathAfterSlash = path.substring(path.lastIndexOf('/') + 1);
    const response = await axios.get(`${fastApiBaseUrl}/api/image/${pathAfterSlash}`, {
      // params: { pathAfterSlash },
      responseType: 'blob' // Important for handling binary data
    });

    // Create object URL from the blob
    const blob = new Blob([response.data], { type: response.headers['content-type'] });
    imageUrl.value = URL.createObjectURL(blob);
  } catch (error) {
    console.error('Error fetching image:', error);
    ElMessage.error('获取图片失败: ' + error.message);
  }
}

// Add cleanup for object URLs when component unmounts
onUnmounted(() => {
  if (imageUrl.value) {
    URL.revokeObjectURL(imageUrl.value);
  }
});

// 修改createNewNode方法
async function createNewNode() {
  if (!newNodeForm.value.label) {
    ElMessage.error('节点标签不能为空');
    return;
  }

  try {
    const session = driver.session({ database: currentDatabase.value });
    try {
      // 确保使用最终生成的properties对象
      const result = await session.run(
        `CREATE (n:${newNodeForm.value.label} $properties)
         RETURN n`,
        { properties: newNodeForm.value.properties }
      );

      const createdNode = result.records[0].get('n');
      const nodeData = {
        id: createdNode.identity.toString(),
        labels: [newNodeForm.value.label],
        properties: newNodeForm.value.properties,
        x: graphContainer.value.clientWidth / 2 + (Math.random() - 0.5) * 100,
        y: graphContainer.value.clientHeight / 2 + (Math.random() - 0.5) * 100
      };

      dataNodes.value.push(nodeData);
      renderGraph();

      showAddNodeDialog.value = false;
      newNodeForm.value = {
        label: '',
        propertyList: [],
        properties: {}
      };
      ElMessage.success('节点创建成功');
    } finally {
      await session.close();
    }
  } catch (error) {
    ElMessage.error('创建节点失败: ' + error.message);
  }
}

async function createNewRelationship(source, target) {
  try {
    const relType = await ElMessageBox.prompt('请输入关系类型', '创建关系', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /.+/,
      inputErrorMessage: '关系类型不能为空'
    })

    const session = driver.session({ database: currentDatabase.value })
    try {
      const result = await session.run(
        `MATCH (a), (b)
         WHERE ID(a) = ${source.id} AND ID(b) = ${target.id}
         CREATE (a)-[r:${relType.value}]->(b)
         RETURN r`,
        { properties: {} }
      )


      const createdRel = result.records[0].get('r')
      const relData = {
        id: createdRel.identity.toString(),
        source: source.id,
        target: target.id,
        label: createdRel.type
      }

      dataRelationships.value.push(relData)
      renderGraph()
      ElMessage.success('关系创建成功')
    } finally {
      await session.close()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('创建关系失败: ' + error.message)
    }
  }
}

function updateNodeLabel() {
  // Update the node label in the visualization
  node.filter(d => d.id === selectedItem.value.data.id)
    .select('text')
    .text(selectedItem.value.data.label);
}

// 添加属性
function addProperty() {
  if (newPropertyKey.value && newPropertyValue.value) {
    selectedItem.value.data.properties[newPropertyKey.value] = newPropertyValue.value;
    newPropertyKey.value = '';
    newPropertyValue.value = '';
  }
}

// 删除属性
function deleteProperty(key) {
  ElMessageBox.confirm(`确定删除属性 "${key}" 吗?`, '提示', {
    type: 'warning'
  }).then(() => {
    delete selectedItem.value.data.properties[key];
    console.log(selectedItem.value.data.properties)
    ElMessage.success('属性已删除');
  }).catch(() => {
    // 取消操作
  });
}

// 在数据库保存节点更改
async function updateNodeInDatabase(node) {
  const session = driver.session({ database: currentDatabase.value });
  try {
    // Get current properties from database
    const result = await session.run(
      `MATCH (n) WHERE ID(n) = ${node.id} RETURN keys(n) AS keys`
    );
    const currentKeys = result.records[0].get('keys');

    // Get new property keys
    const newKeys = Object.keys(node.properties);

    // Find properties to delete
    const keysToDelete = currentKeys.filter(key => !newKeys.includes(key));

    // Update properties
    const properties = Object.entries(node.properties)
      .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
      .join(', ');

    // Construct remove properties statement
    const removeProperties = keysToDelete.map(key => `REMOVE n.${key}`).join(' ');

    // First remove all labels (we'll re-add the current ones)
    await session.run(
      `MATCH (n) WHERE ID(n) = ${node.id}
       REMOVE n:${node.labels.join(':')}`
    );

    // Then update node with current labels and properties
    await session.run(
      `MATCH (n) WHERE ID(n) = ${node.id}
       SET n:${node.labels.join(':')}
       SET n += {${properties}}
       ${removeProperties}`
    );
  } finally {
    await session.close();
  }
}

async function updateRelationshipInDatabase(relationship) {
  const session = driver.session({ database: currentDatabase.value });
  try {
    // 更新关系类型和属性
    await session.run(
      `MATCH ()-[r]->() WHERE ID(r) = ${parseInt(relationship.id)}
       SET r.type = $type
       SET r += $properties`,
      {
        type: relationship.label,
        properties: relationship.properties || {}
      }
    );
  } finally {
    await session.close();
  }
}

async function deleteNodeFromDatabase(nodeId) {
  const session = driver.session({ database: currentDatabase.value });
  try {
    await session.run(
      `MATCH (n) WHERE ID(n) = ${parseInt(nodeId)}
       DETACH DELETE n`
    );
  } finally {
    await session.close();
  }
}

async function deleteRelationshipFromDatabase(relId) {
  console.log(relId)
  const session = driver.session({ database: currentDatabase.value });
  try {
    await session.run(
      `MATCH ()-[r]->() WHERE ID(r) = ${relId}
       DELETE r`
    );
  } finally {
    await session.close();
  }
}

async function createNodeInDatabase(nodeData) {
  const session = driver.session({ database: currentDatabase.value });
  try {
    const result = await session.run(
      `CREATE (n:${nodeData.label} $properties)
       RETURN ID(n) as id`,
      { properties: nodeData.properties }
    );
    return result.records[0].get('id').toString();
  } finally {
    await session.close();
  }
}

async function createRelationshipInDatabase(relData) {
  const session = driver.session({ database: currentDatabase.value });
  try {
    const result = await session.run(
      `MATCH (a), (b)
       WHERE ID(a) = ${parseInt(relData.source)} AND ID(b) = ${parseInt(relData.target)}
       CREATE (a)-[r:${relData.label} $properties]->(b)
       RETURN ID(r) as id`,
      { properties: relData.properties || {} }
    );
    return result.records[0].get('id').toString();
  } finally {
    await session.close();
  }
}

// 修改操作函数以保存到数据库
async function saveNodeChanges() {
  try {
    await updateNodeInDatabase(selectedItem.value.data);
    ElMessage.success('节点修改已保存到数据库');
  } catch (error) {
    ElMessage.error('保存失败: ' + error.message);
  }
}

async function deleteNode() {
  try {
    await ElMessageBox.confirm(
      '这将删除节点及其所有关系，继续吗?',
      '警告',
      { type: 'warning' }
    );

    await deleteNodeFromDatabase(selectedItem.value.data.id);

    // 更新本地数据
    const nodeId = selectedItem.value.data.id;
    dataRelationships.value = dataRelationships.value.filter(
      r => r.source.id !== nodeId && r.target.id !== nodeId
    );
    dataNodes.value = dataNodes.value.filter(n => n.id !== nodeId);

    selectedItem.value = null;
    // resetSimulation();
    renderGraph();
    ElMessage.success('节点已从数据库删除');
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + error.message);
    }
  }
}

async function updateRelationshipType() {
  try {
    await updateRelationshipInDatabase(selectedItem.value.data);
    ElMessage.success('关系类型已更新到数据库');
  } catch (error) {
    ElMessage.error('更新失败: ' + error.message);
  }
}

async function deleteRelationship() {
  try {
    await ElMessageBox.confirm(
      '删除这个关系吗?',
      '警告',
      { type: 'warning' }
    );

    await deleteRelationshipFromDatabase(selectedItem.value.data.id);

    // 更新本地数据
    const relId = selectedItem.value.data.id;
    dataRelationships.value = dataRelationships.value.filter(r => r.id !== relId);

    selectedItem.value = null;
    renderGraph();
    ElMessage.success('关系已从数据库删除');
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + error.message);
    }
  }
}

// 修改expandNode方法
async function expandNode() {
  try {
    // 验证必填字段
    if (!expandForm.value.newNodeLabel?.trim()) {
      ElMessage.error('新节点标签不能为空');
      return;
    }

    if (!expandForm.value.relationshipType?.trim()) {
      ElMessage.error('关系类型不能为空');
      return;
    }

    // 确保有选中的节点且节点数据有效
    if (!selectedItem.value?.data?.id) {
      ElMessage.error('请先选择一个有效节点');
      return;
    }

    // 准备新节点数据
    const newNodeData = {
      label: expandForm.value.newNodeLabel,
      properties: expandForm.value.newNodeProperties || {}
    };

    const session = driver.session({ database: currentDatabase.value });
    try {
      // 1. 创建新节点
      const createNodeResult = await session.run(
        `CREATE (n:${newNodeData.label} $properties)
         RETURN ID(n) as id, n`,
        { properties: newNodeData.properties }
      );

      if (createNodeResult.records.length === 0) {
        throw new Error('创建节点失败');
      }

      const newNodeRecord = createNodeResult.records[0];
      const newNodeId = newNodeRecord.get('id').toString();
      const createdNode = newNodeRecord.get('n');

      // 2. 创建关系
      const sourceId = expandForm.value.direction === 'out'
        ? selectedItem.value.data.id
        : newNodeId;
      const targetId = expandForm.value.direction === 'out'
        ? newNodeId
        : selectedItem.value.data.id;

      const createRelResult = await session.run(
        `MATCH (a), (b)
         WHERE ID(a) = ${parseInt(sourceId)} AND ID(b) = ${parseInt(targetId)}
         CREATE (a)-[r:${expandForm.value.relationshipType}]->(b)
         RETURN ID(r) as relId, r`
      );

      if (createRelResult.records.length === 0) {
        throw new Error('创建关系失败');
      }

      const relRecord = createRelResult.records[0];
      const relId = relRecord.get('relId').toString();
      const createdRel = relRecord.get('r');

      // 更新本地数据
      dataNodes.value.push({
        id: newNodeId,
        labels: createdNode.labels || [newNodeData.label],
        properties: createdNode.properties || newNodeData.properties,
        x: selectedItem.value.data.x + (Math.random() - 0.5) * 100,
        y: selectedItem.value.data.y + (Math.random() - 0.5) * 100
      });

      dataRelationships.value.push({
        id: relId,
        source: sourceId,
        target: targetId,
        label: createdRel.type || expandForm.value.relationshipType
      });

      // 重置表单
      showExpandDialog.value = false;
      expandForm.value = {
        newNodeLabel: '',
        relationshipType: '',
        direction: 'out',
        propertyList: [],
        newNodeProperties: {}
      };
      newExpandPropertyKey.value = '';
      newExpandPropertyValue.value = '';

      // 重新渲染图形
      renderGraph();
      ElMessage.success('节点扩展成功');

    } catch (error) {
      console.error('扩展节点错误:', error);
      throw error;
    } finally {
      await session.close();
    }

  } catch (error) {
    console.error('扩展节点失败:', error);
    ElMessage.error(`扩展节点失败: ${error.message || '未知错误'}`);
  }
}

// 修改expandSelectedNode方法
async function expandSelectedNode() {
  try {
    // 确保有选中的节点
    if (!selectedItem.value || !selectedItem.value.data) {
      ElMessage.error('请先选择一个节点');
      return;
    }

    const nodeId = selectedItem.value.data.id;

    const session = driver.session({ database: currentDatabase.value });
    try {
      // 从数据库获取扩展数据
      const result = await session.run(`
        MATCH (a)-[r]->(b)
        WHERE ID(a) = ${parseInt(nodeId)} OR ID(b) = ${parseInt(nodeId)}
        RETURN a, r, b
      `);

      // 处理新节点
      const newNodes = [];
      const newRels = [];

      result.records.forEach(record => {
        const sourceNode = record.get('a');
        const targetNode = record.get('b');
        const rel = record.get('r');

        // 添加源节点(如果不是当前选中节点)
        if (sourceNode.identity.toString() !== nodeId) {
          if (!dataNodes.value.some(n => n.id === sourceNode.identity.toString())) {
            newNodes.push({
              id: sourceNode.identity.toString(),
              labels: sourceNode.labels.length > 0 ? sourceNode.labels : ['未分类'],
              properties: sourceNode.properties || {}
            });
          }
        }

        // 添加目标节点(如果不是当前选中节点)
        if (targetNode.identity.toString() !== nodeId) {
          if (!dataNodes.value.some(n => n.id === targetNode.identity.toString())) {
            newNodes.push({
              id: targetNode.identity.toString(),
              labels: targetNode.labels.length > 0 ? targetNode.labels : ['未分类'],
              properties: targetNode.properties || {}
            });
          }
        }

        // 添加关系(如果不存在)
        if (!dataRelationships.value.some(r => r.id === rel.identity.toString())) {
          newRels.push({
            id: rel.identity.toString(),
            source: sourceNode.identity.toString(),
            target: targetNode.identity.toString(),
            label: rel.type || '未定义'
          });
        }
      });

      // 合并新数据
      dataNodes.value = [...dataNodes.value, ...newNodes];
      dataRelationships.value = [...dataRelationships.value, ...newRels];

      // 重新渲染图形
      renderGraph();
      ElMessage.success(`已展开 ${newNodes.length} 个相邻节点和 ${newRels.length} 条关系`);

    } catch (error) {
      console.error('展开节点查询失败:', error);
      throw error;
    } finally {
      await session.close();
    }
  } catch (error) {
    console.error('展开节点失败:', error);
    ElMessage.error('展开节点失败: ' + (error.message || error.toString()));
  }
}

// 文字处理函数
function formatNodeText(text) {
  // 如果 text 不是字符串，转换为字符串或返回空字符串
  if (typeof text !== 'string') {
    text = String(text || '');
  }

  // 如果文字长度超过12个字符
  if (text.length > 12) {
    return text.substring(0, 4) + "...";
  }

  // 每4个字符插入换行符
  return text.replace(/(.{4})/g, "$1\n");
}

// 添加标签
async function addLabel() {
  if (!labelForm.value.newLabel) {
    ElMessage.warning('请选择或输入标签');
    return;
  }

  try {
    // Add label to node in database
    const session = driver.session({ database: currentDatabase.value });
    await session.run(
      `MATCH (n) WHERE ID(n) = ${selectedItem.value.data.id}
       SET n:${labelForm.value.newLabel}`
    );

    // Update local data
    if (!selectedItem.value.data.labels.includes(labelForm.value.newLabel)) {
      selectedItem.value.data.labels.push(labelForm.value.newLabel);

      // Update label color map if needed
      if (!labelColorMap.value[labelForm.value.newLabel]) {
        const colors = Object.values(labelColorMap.value);
        const newColor = NODE_COLORS.find(color => !colors.includes(color)) || '#cccccc';
        labelColorMap.value[labelForm.value.newLabel] = newColor;
      }
    }

    showAddLabelDialog.value = false;
    labelForm.value.newLabel = '';
    ElMessage.success('标签添加成功');
  } catch (error) {
    ElMessage.error('添加标签失败: ' + error.message);
  }
}

// 删除标签
async function removeLabel(labelToRemove) {
  try {
    await ElMessageBox.confirm(
      `确定删除标签 "${labelToRemove}" 吗?`,
      '警告',
      { type: 'warning' }
    );

    const session = driver.session({ database: currentDatabase.value });
    try {
      await session.run(
        `MATCH (n) WHERE ID(n) = ${selectedItem.value.data.id}
         REMOVE n:${labelToRemove}`
      );

      // 更新本地数据
      selectedItem.value.data.labels = selectedItem.value.data.labels.filter(
        label => label !== labelToRemove
      );

      ElMessage.success('标签删除成功');
    } finally {
      await session.close();
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除标签失败: ' + error.message);
    }
  }
}

// 修改新增节点属性操作方法
function addNewNodeProperty() {
  newNodeForm.value.propertyList.push({
    key: newPropertyKey.value,
    value: newPropertyValue.value
  });
  updateNewNodeProperties();
  newPropertyKey.value = '';
  newPropertyValue.value = '';
}

function removeNewNodeProperty(index) {
  newNodeForm.value.propertyList.splice(index, 1);
  updateNewNodeProperties();
}

function updateNewNodeProperty(index) {
  updateNewNodeProperties();
}

function updateNewNodeProperties() {
  const properties = {};
  newNodeForm.value.propertyList.forEach(item => {
    if (item.key) {
      properties[item.key] = item.value;
    }
  });
  newNodeForm.value.properties = properties;
}

// 修改扩展节点属性操作方法
function addExpandProperty() {
  expandForm.value.propertyList.push({
    key: newExpandPropertyKey.value,
    value: newExpandPropertyValue.value
  });
  updateExpandProperties();
  newExpandPropertyKey.value = '';
  newExpandPropertyValue.value = '';
}

function removeExpandProperty(index) {
  expandForm.value.propertyList.splice(index, 1);
  updateExpandProperties();
}

function updateExpandProperty(index) {
  updateExpandProperties();
}

function updateExpandProperties() {
  const properties = {};
  expandForm.value.propertyList.forEach(item => {
    if (item.key) {
      properties[item.key] = item.value;
    }
  });
  expandForm.value.newNodeProperties = properties;
}

</script>

<style scoped>
/* 修改容器样式，确保填充可用空间 */
.graph-container {
  display: flex;
  height: calc(100vh - 60px); /* 减去头部高度 */
  width: 100%;
}

/* 图谱展示区占满剩余空间 */
.graph-area {
  flex: 1; /* 占据父容器的剩余空间 */
  min-height: 600px; /* 保证图谱区域的最小高度 */
  border: 1px solid #eee; /* 浅灰色边框 */
  border-radius: 4px; /* 圆角边框 */
  background-color: #f8f9fa; /* 浅灰色背景 */
  position: relative; /* 为内部元素定位提供相对定位的容器 */
  overflow: hidden; /* 隐藏超出容器的内容 */
}

.property-panel {
  width: 350px; /* 默认宽度 */
  margin-left: 20px; /* 左侧外边距 */
  height: calc(100vh - 100px); /* 占据视口剩余高度，减去可能存在的头部或底部固定元素高度 */
  overflow-y: auto; /* 内容超出时显示垂直滚动条 */
  position: relative; /* 为子元素定位提供相对定位的容器 */
  transition: all 0.3s ease; /* 所有属性变化的过渡效果 */
  display: flex; /* 使用 Flexbox 布局 */
  flex-direction: column; /* 垂直排列子元素 */
}

.property-panel.collapsed {
  width: 24px; /* 折叠状态时的宽度 */
}

.property-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.property-item {
  margin-bottom: 15px;
}

.relationship-info {
  margin-bottom: 15px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.expand-btn circle {
  transition: all 0.2s;
}

.expand-btn:hover circle {
  r: 18;
  fill: #85ce61;
}

/* 查询模块样式 */
.query-module {
  margin-bottom: 20px;
}

.custom-query-container {
  padding: 0px;
}

.query-row {
  display: flex;
  align-items: center;
  margin-bottom: 5px;
}

.first-row {
  border-bottom: 1px solid #eee;
  padding-bottom: 15px;
}

.second-row {
  padding-top: 10px;
}

.query-item {
  display: flex;
  align-items: center;
  margin-right: 20px;
}

.query-label {
  margin-right: 8px;
  font-size: 18px;
  font-weight: 500;
  color: #606266;
  white-space: nowrap;
}

.cypher-query-container {
  display: flex;
  width: 100%;
  align-items: center;
}

.filter-query-container {
  display: flex;
  width: 100%;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.collapse-handle {
  position: absolute;
  left: -12px;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 60px;
  background-color: #fff;
  border: 1px solid #ebeef5;
  border-radius: 4px 0 0 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  box-shadow: -2px 0 4px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.collapse-handle:hover {
  background-color: #f5f7fa;
  color: var(--el-color-primary);
}


/* 控制按钮组样式调整 */
.graph-controls {
  position: absolute; /* 绝对定位 */
  top: 10px;
  left: 10px;
  z-index: 100;
  display: flex;
  gap: 10px;
  transform-origin: left top; /* 确保缩放时从左上角开始 */
}

.graph-controls .el-button {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transform: scale(1); /* 初始缩放比例 */
  transition: transform 0.2s ease;
}

/* 当画布缩放时调整按钮大小 */
.graph-area.zoomed .graph-controls .el-button {
  transform: scale(0.9); /* 根据缩放比例调整 */
}

/* 关系创建提示样式 */
.relationship-creating-hint {
  margin-top: 15px;
}

.relationship-creating-hint .el-alert {
  padding: 8px 16px;
}

/* 高亮可选节点 */
.node-selectable circle {
  stroke: #409EFF !important;
  stroke-width: 3px !important;
  cursor: pointer;
}

/* 修改 legend-container 样式 */
.legend-container {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  background-color: rgba(255, 255, 255, 0.8);
  padding: 8px;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  z-index: 10;
  max-width: 500px;
  transition: all 0.3s ease;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer; /* 添加手型光标 */
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.2s;
}

.legend-item:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.legend-item:active {
  background-color: rgba(0, 0, 0, 0.1);
}

.legend-color {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  border: 1px solid #ddd;
}

.legend-label {
  font-size: 12px;
  color: #333;
}

/* Add new styles for image display */
.image-display {
  margin: 15px 0;
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 5px;
  background-color: #f8f9fa;
}


/* 标签容器样式 */
.label-container {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  max-height: 80px;
  overflow-y: auto;
}



/* 基本信息区域 */
.basic-info-section {
  padding: 0 10px;
}

/* 可滚动属性区域 */
.scrollable-properties {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px;
  max-height: calc(100vh - 75vh); /* 根据实际需要调整 */
  margin-bottom: 10px;
}

/* 操作按钮区域 */
.action-buttons {
  padding: 0 10px;
  margin-top: auto; /* 固定在底部 */
}

/* 属性项样式优化 */
.property-item {
  margin-bottom: 15px;
  padding: 8px;
  border-radius: 4px;
  background-color: #f8f9fa;
}

/* 自定义滚动条样式 */
.scrollable-properties::-webkit-scrollbar {
  width: 6px;
}

.scrollable-properties::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.scrollable-properties::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.scrollable-properties::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 添加折叠按钮样式 */
.collapse-legend-btn {
  position: absolute;
  right: 5px;
  bottom: 5px;
  cursor: pointer;
  color: #666;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
}

.collapse-legend-btn:hover {
  background-color: rgba(0, 0, 0, 0.05);
  color: #409eff;
}




</style>