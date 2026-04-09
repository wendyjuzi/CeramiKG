<template>
  <div class="knowledge-graph">
    <div class="graph-header">
      <h3>🕸️ 知识图谱</h3>
      <div class="header-actions">
        <el-button
          type="primary"
          :loading="loading"
          :disabled="!selectedDocumentOption"
          @click="loadKnowledgeGraph"
        >
          <el-icon><Refresh /></el-icon>
          加载图谱
        </el-button>
        <el-button 
          v-if="graphData && graphData.nodes.length > 0"
          @click="exportGraph"
        >
          <el-icon><Download /></el-icon>
          导出图谱
        </el-button>
      </div>
    </div>

    <!-- 图谱配置和控制 -->
    <div class="graph-controls">
      <el-card shadow="hover">
        <div class="control-row">
          <div class="control-item">
            <label>文档：</label>
            <el-select
              v-model="selectedDocumentOption"
              placeholder="选择要查看的知识图谱"
              style="width: 200px"
              @change="handleDocumentChange"
              clearable
            >
              <el-option
                key="all-knowledge"
                label="所有知识"
                value="all-knowledge"
              />
              <el-option
                v-for="option in knowledgeTables"
                :key="option.document_id"
                :label="option.display_name"
                :value="option.document_id"
              >
                <span style="float: left">{{ option.display_name }}</span>
                <span style="float: right; color: #8492a6; font-size: 13px">
                  {{ option.is_legacy ? '旧格式' : '新格式' }}
                </span>
              </el-option>
            </el-select>
          </div>
          
          <div class="control-item">
            <label>布局模式：</label>
            <el-radio-group v-model="layoutMode" @change="updateLayout">
              <el-radio-button label="force">力导图</el-radio-button>
              <el-radio-button label="circle">环形</el-radio-button>
              <el-radio-button label="tree">树形</el-radio-button>
            </el-radio-group>
          </div>
          
          <div class="control-item">
            <label>节点大小：</label>
            <el-slider
              v-model="nodeSize"
              :min="5"
              :max="30"
              @change="updateNodeSize"
              style="width: 150px"
            />
          </div>
        </div>
        
        <div class="control-row">
          <div class="control-item">
            <el-checkbox v-model="showLabels" @change="toggleLabels">
              显示标签
            </el-checkbox>
          </div>
          <div class="control-item">
            <el-checkbox v-model="showEdgeLabels" @change="toggleEdgeLabels">
              显示边标签
            </el-checkbox>
          </div>
          <div class="control-item">
            <el-checkbox v-model="enableZoom" @change="toggleZoom">
              启用缩放
            </el-checkbox>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 图谱统计信息 -->
    <div v-if="graphData" class="graph-stats">
      <el-descriptions :column="4" border size="small">
        <el-descriptions-item label="节点数量">
          <el-tag type="primary">{{ graphData.nodes.length }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="边数量">
          <el-tag type="success">{{ graphData.edges.length }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="节点类型">
          <el-tag type="info">{{ nodeTypes.length }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="关系类型">
          <el-tag type="warning">{{ edgeTypes.length }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 图谱可视化区域 -->
    <div class="graph-container">
      <div
        v-loading="loading"
        ref="graphRef"
        class="graph-canvas"
        :style="{ height: graphHeight + 'px' }"
      >
        <!-- 异常59修复：将加载按钮移到图谱可视化区域内 -->
        <div v-if="!loading && (!graphData || graphData.nodes.length === 0)" class="graph-load-overlay">
          <div class="load-content">
            <el-icon size="60" color="#c0c4cc">
              <Share />
            </el-icon>
            <p class="load-message">暂无知识图谱数据</p>
            <el-button
              v-if="selectedDocumentOption"
              type="primary"
              size="large"
              @click="loadKnowledgeGraph"
              class="load-button"
            >
              <el-icon><Refresh /></el-icon>
              加载图谱数据
            </el-button>
            <el-text v-else type="warning" size="default">
              请先选择文档或知识图谱
            </el-text>
          </div>
        </div>
      </div>

      <!-- 图例 -->
      <div v-if="graphData && graphData.nodes.length > 0" class="graph-legend">
        <el-card shadow="hover">
          <template #header>
            <span>图例</span>
          </template>

          <div class="legend-section">
            <h5>节点类型</h5>
            <div class="legend-items">
              <div
                v-for="type in nodeTypes"
                :key="type"
                class="legend-item"
              >
                <div
                  class="legend-node"
                  :style="{ backgroundColor: getNodeColor(type) }"
                />
                <span>{{ type }}</span>
              </div>
            </div>
          </div>

          <div class="legend-section">
            <h5>关系类型</h5>
            <div class="legend-items">
              <div
                v-for="type in edgeTypes"
                :key="type"
                class="legend-item"
              >
                <div
                  class="legend-edge"
                  :style="{ borderColor: getEdgeColor(type) }"
                />
                <span>{{ type }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 节点详情面板 -->
    <el-drawer
      v-model="nodeDetailVisible"
      title="节点详情"
      direction="rtl"
      size="400px"
    >
      <div v-if="selectedNode" class="node-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="节点名称">
            {{ selectedNode.name }}
          </el-descriptions-item>
          <el-descriptions-item label="节点类型">
            <el-tag :color="getNodeColor(selectedNode.type)">
              {{ selectedNode.type }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="度数">
            {{ selectedNode.degree }}
          </el-descriptions-item>
          <el-descriptions-item label="描述" v-if="selectedNode.description">
            {{ selectedNode.description }}
          </el-descriptions-item>
        </el-descriptions>
        
        <!-- 相邻节点 -->
        <div class="neighbors-section">
          <h4>相邻节点 ({{ neighbors.length }})</h4>
          <div class="neighbors-list">
            <el-tag
              v-for="neighbor in neighbors"
              :key="neighbor.id"
              @click="highlightNode(neighbor)"
              style="margin: 4px; cursor: pointer"
              :type="neighbor.relation === selectedNode.name ? 'success' : 'primary'"
            >
              {{ neighbor.name }} ({{ neighbor.relation }})
            </el-tag>
          </div>
        </div>
        
        <!-- 相关关系 -->
        <div class="relations-section">
          <h4>相关关系 ({{ relatedRelations.length }})</h4>
          <el-table :data="relatedRelations" size="small" height="200">
            <el-table-column prop="source" label="源" width="80" />
            <el-table-column prop="relation" label="关系" width="80" />
            <el-table-column prop="target" label="目标" width="80" />
          </el-table>
        </div>
      </div>
    </el-drawer>

  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Refresh, Download, Share } from '@element-plus/icons-vue'

export default {
  name: 'KnowledgeGraph',
  components: {
    Refresh,
    Download,
    Share
  },
  props: {
    documentId: {
      type: String,
      default: ''
    },
    documentName: {
      type: String,
      default: ''
    }
  },
  emits: ['node-selected', 'graph-loaded', 'update:document-id'],
  setup(props, { emit }) {
    // 响应式数据
    const graphRef = ref(null)
    const graphData = ref(null)
    const knowledgeTables = ref([])
    const selectedDocumentOption = ref('')
    const loading = ref(false)
    const selectedNode = ref(null)
    const nodeDetailVisible = ref(false)
    const layoutMode = ref('force')
    const nodeSize = ref(15)
    const showLabels = ref(true)
    const showEdgeLabels = ref(false)
    const enableZoom = ref(true)
    const graphHeight = ref(600)

    // D3相关变量
    let svg, simulation, nodes, links, nodeElements, linkElements, labelElements, nodeGroups
    
    // API基础URL
    const API_BASE_URL = '/api/graph'

    // 计算属性：文档ID双向绑定（保留文档名模型用于显示）
    const documentNameModel = computed({
      get: () => props.documentName,
      set: (value) => {
        // 这里需要找到对应的document_id并触发更新
        // 暂时保留旧逻辑，主要用于显示
      }
    })

    // 颜色映射
    const nodeColorScale = d3.scaleOrdinal(d3.schemeCategory10)
    const edgeColorScale = d3.scaleOrdinal(d3.schemeSet3)

    // 计算属性
    const nodeTypes = computed(() => {
      if (!graphData.value) return []
      return [...new Set(graphData.value.nodes.map(node => node.type))].sort()
    })

    const edgeTypes = computed(() => {
      if (!graphData.value) return []
      return [...new Set(graphData.value.edges.map(edge => edge.relation_type))].sort()
    })

    const neighbors = computed(() => {
      if (!selectedNode.value || !graphData.value) return []
      
      const nodeId = selectedNode.value.id
      const result = []
      
      // 创建节点ID到节点对象的映射
      const nodeMap = {}
      graphData.value.nodes.forEach(node => {
        nodeMap[node.id] = node
      })
      
      graphData.value.edges.forEach(edge => {
        // 异常25修复：兼容不同的数据结构（ID字符串或对象）
        const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source
        const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target
        
        if (sourceId === nodeId && nodeMap[targetId]) {
          result.push({
            id: targetId,
            name: nodeMap[targetId].name || targetId,
            relation: edge.relation_type || edge.type
          })
        } else if (targetId === nodeId && nodeMap[sourceId]) {
          result.push({
            id: sourceId,
            name: nodeMap[sourceId].name || sourceId,
            relation: edge.relation_type || edge.type
          })
        }
      })
      
      return result
    })

    const relatedRelations = computed(() => {
      if (!selectedNode.value || !graphData.value) return []
      
      const nodeId = selectedNode.value.id
      const result = []
      
      // 创建节点ID到节点对象的映射
      const nodeMap = {}
      graphData.value.nodes.forEach(node => {
        nodeMap[node.id] = node
      })
      
      graphData.value.edges.forEach(edge => {
        // 异常25修复：兼容不同的数据结构（ID字符串或对象）
        const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source
        const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target
        
        if (sourceId === nodeId || targetId === nodeId) {
          const sourceName = nodeMap[sourceId]?.name || sourceId
          const targetName = nodeMap[targetId]?.name || targetId
          
          result.push({
            source: sourceName,
            relation: edge.relation_type || edge.type,
            target: targetName
          })
        }
      })
      
      return result
    })

    // 异常51修复：加载知识图谱选项列表
    const loadKnowledgeTables = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/knowledge-graph-options`)
        knowledgeTables.value = response.data || []
        console.log('加载知识图谱选项:', knowledgeTables.value)
      } catch (error) {
        console.error('加载知识图谱选项失败:', error)
        ElMessage.error('加载知识图谱选项失败')
        // 回退到旧接口（兼容性）
        try {
          const fallbackResponse = await axios.get(`${API_BASE_URL}/knowledge-tables`)
          const oldTables = fallbackResponse.data || []
          // 转换为新格式
          knowledgeTables.value = oldTables.map(table => ({
            document_id: table,
            display_name: table,
            description: `表: ${table}`,
            is_legacy: true
          }))
          console.log('使用旧接口获取表列表:', knowledgeTables.value)
        } catch (fallbackError) {
          console.error('旧接口也失败:', fallbackError)
        }
      }
    }

    // 加载知识图谱数据
    const loadKnowledgeGraph = async () => {
      if (!selectedDocumentOption.value) {
        ElMessage.warning('请选择要查看的文档或知识图谱')
        return
      }

      loading.value = true
      try {
        let response

        // 根据选择调用不同的API
        if (selectedDocumentOption.value === 'all-knowledge') {
          // 加载所有知识图谱
          response = await axios.get(`${API_BASE_URL}/unified-knowledge-graph`)
        } else {
          // 加载特定文档的知识图谱
          response = await axios.get(`${API_BASE_URL}/knowledge-graph/${selectedDocumentOption.value}`)
        }

        if (response.data && response.data.nodes && response.data.edges) {
          graphData.value = response.data

          // 计算节点度数
          graphData.value.nodes.forEach(node => {
            node.degree = graphData.value.edges.filter(
              edge => edge.source === node.id || edge.target === node.id
            ).length
          })

          await nextTick()
          renderGraph()
          emit('graph-loaded', graphData.value)

          // 异常51修复：改进成功消息显示
          let selectedTypeName = '所有知识'
          if (selectedDocumentOption.value !== 'all-knowledge') {
            // 查找对应的显示名称
            const selectedOption = knowledgeTables.value.find(opt => opt.document_id === selectedDocumentOption.value)
            selectedTypeName = selectedOption ? selectedOption.display_name : selectedDocumentOption.value
          }
          ElMessage.success(`成功加载${selectedTypeName}图谱：${graphData.value.nodes.length} 个节点，${graphData.value.edges.length} 条边`)
        } else {
          graphData.value = null
          ElMessage.warning('知识图谱数据格式异常')
        }
      } catch (error) {
        console.error('加载知识图谱失败:', error)
        ElMessage.error('加载知识图谱失败: ' + (error.response?.data?.detail || error.message))
        graphData.value = null
      } finally {
        loading.value = false
      }
    }

    // 处理文档变化
    const handleDocumentChange = () => {
      if (selectedDocumentOption.value) {
        loadKnowledgeGraph()
      }
    }

    // 渲染图谱
    const renderGraph = () => {
      if (!graphData.value || !graphRef.value) return

      // 清除之前的图谱
      d3.select(graphRef.value).selectAll('*').remove()

      const width = graphRef.value.clientWidth
      const height = graphHeight.value

      // 创建SVG
      svg = d3.select(graphRef.value)
        .append('svg')
        .attr('width', width)
        .attr('height', height)

      // 添加缩放功能
      if (enableZoom.value) {
        const zoom = d3.zoom()
          .scaleExtent([0.1, 10])
          .on('zoom', (event) => {
            svg.select('.graph-content').attr('transform', event.transform)
          })
        svg.call(zoom)
      }

      const graphContent = svg.append('g').attr('class', 'graph-content')

      // 复制数据以避免修改原始数据
      nodes = JSON.parse(JSON.stringify(graphData.value.nodes))
      links = JSON.parse(JSON.stringify(graphData.value.edges))

      // 创建力导向模拟
      simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))

      // 异常25修复：美化边的渲染效果
      // 添加箭头标记定义
      const defs = svg.append('defs')
      
      // 为每种关系类型创建不同颜色的箭头
      const relationTypes = [...new Set(links.map(d => d.relation_type || d.type))]
      relationTypes.forEach(type => {
        defs.append('marker')
          .attr('id', `arrow-${type.replace(/[^a-zA-Z0-9]/g, '_')}`)
          .attr('viewBox', '0 -5 10 10')
          .attr('refX', 15)
          .attr('refY', 0)
          .attr('markerWidth', 6)
          .attr('markerHeight', 6)
          .attr('orient', 'auto')
          .append('path')
          .attr('d', 'M0,-5L10,0L0,5')
          .attr('fill', getEdgeColor(type))
      })

      // 创建边（使用路径而不是直线，支持曲线）
      linkElements = graphContent.append('g')
        .selectAll('path')
        .data(links)
        .enter().append('path')
        .attr('stroke', d => getEdgeColor(d.relation_type || d.type))
        .attr('stroke-width', d => Math.max(1, Math.min(4, (d.confidence || 1) * 3))) // 根据置信度调整线宽
        .attr('stroke-opacity', 0.7)
        .attr('fill', 'none')
        .attr('marker-end', d => `url(#arrow-${(d.relation_type || d.type).replace(/[^a-zA-Z0-9]/g, '_')})`)
        .style('cursor', 'pointer')
        .on('mouseover', function(event, d) {
          d3.select(this)
            .attr('stroke-width', d => Math.max(3, Math.min(6, (d.confidence || 1) * 4)))
            .attr('stroke-opacity', 0.9)
        })
        .on('mouseout', function(event, d) {
          d3.select(this)
            .attr('stroke-width', d => Math.max(1, Math.min(4, (d.confidence || 1) * 3)))
            .attr('stroke-opacity', 0.7)
        })

      // 创建边标签
      const linkLabelElements = graphContent.append('g')
        .selectAll('text')
        .data(links)
        .enter().append('text')
        .attr('class', 'edge-label')  // 异常25修复：添加类名用于标签切换
        .attr('text-anchor', 'middle')
        .attr('font-size', '10px')
        .attr('fill', '#666')
        .style('display', showEdgeLabels.value ? 'block' : 'none')
        .text(d => d.relation_type || d.type)

      // 异常25修复：美化节点渲染效果
      // 先创建节点组
      nodeGroups = graphContent.append('g')
        .selectAll('g')
        .data(nodes)
        .enter().append('g')
        .style('cursor', 'pointer')
        .on('click', handleNodeClick)
        .call(d3.drag()
          .on('start', dragStart)
          .on('drag', dragging)
          .on('end', dragEnd))

      // 添加阴影效果
      const shadow = defs.append('filter')
        .attr('id', 'drop-shadow')
        .attr('height', '130%')
      
      shadow.append('feGaussianBlur')
        .attr('in', 'SourceAlpha')
        .attr('stdDeviation', 3)
      
      shadow.append('feOffset')
        .attr('dx', 2)
        .attr('dy', 2)
        .attr('result', 'offset')
      
      const feMerge = shadow.append('feMerge')
      feMerge.append('feMergeNode')
        .attr('in', 'offset')
      feMerge.append('feMergeNode')
        .attr('in', 'SourceGraphic')

      // 创建渐变节点
      nodeElements = nodeGroups.append('circle')
        .attr('r', d => {
          // 根据节点度数调整大小
          const basSize = nodeSize.value
          const degree = graphData.value.edges.filter(edge => {
            const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source
            const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target
            return sourceId === d.id || targetId === d.id
          }).length
          return Math.max(basSize * 0.7, Math.min(basSize * 1.8, basSize + degree * 2))
        })
        .attr('fill', d => {
          // 创建渐变效果
          const gradientId = `gradient-${d.type.replace(/[^a-zA-Z0-9]/g, '_')}`
          if (!defs.select(`#${gradientId}`).node()) {
            const gradient = defs.append('radialGradient')
              .attr('id', gradientId)
            gradient.append('stop')
              .attr('offset', '0%')
              .attr('stop-color', d3.color(getNodeColor(d.type)).brighter(0.3))
            gradient.append('stop')
              .attr('offset', '100%')
              .attr('stop-color', getNodeColor(d.type))
          }
          return `url(#${gradientId})`
        })
        .attr('stroke', '#fff')
        .attr('stroke-width', 3)
        .attr('filter', 'url(#drop-shadow)')
        .on('mouseover', function(event, d) {
          // 节点hover效果
          d3.select(this)
            .transition()
            .duration(200)
            .attr('r', d => {
              const basSize = nodeSize.value
              const degree = graphData.value.edges.filter(edge => {
                const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source
                const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target
                return sourceId === d.id || targetId === d.id
              }).length
              return Math.max(basSize * 0.7, Math.min(basSize * 1.8, basSize + degree * 2)) * 1.2
            })
            .attr('stroke-width', 4)
          
          // 显示tooltip
          showTooltip(event, d)
        })
        .on('mouseout', function(event, d) {
          d3.select(this)
            .transition()
            .duration(200)
            .attr('r', d => {
              const basSize = nodeSize.value
              const degree = graphData.value.edges.filter(edge => {
                const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source
                const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target
                return sourceId === d.id || targetId === d.id
              }).length
              return Math.max(basSize * 0.7, Math.min(basSize * 1.8, basSize + degree * 2))
            })
            .attr('stroke-width', 3)
          
          // 隐藏tooltip
          hideTooltip()
        })

      // 创建节点标签
      labelElements = graphContent.append('g')
        .selectAll('text')
        .data(nodes)
        .enter().append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '0.35em')
        .attr('font-size', '12px')
        .attr('fill', '#333')
        .style('display', showLabels.value ? 'block' : 'none')
        .style('pointer-events', 'none')
        .text(d => d.name)

      // 异常25修复：更新位置支持曲线边和新的节点结构
      simulation.on('tick', () => {
        // 更新曲线边的路径
        linkElements
          .attr('d', d => {
            const dx = d.target.x - d.source.x
            const dy = d.target.y - d.source.y
            const dr = Math.sqrt(dx * dx + dy * dy)
            
            // 创建平滑的二次贝塞尔曲线
            if (dr > 0) {
              const curve = dr * 0.15 // 曲线程度
              const mx = (d.source.x + d.target.x) / 2
              const my = (d.source.y + d.target.y) / 2
              const cx = mx + (-dy / dr) * curve
              const cy = my + (dx / dr) * curve
              
              return `M${d.source.x},${d.source.y} Q${cx},${cy} ${d.target.x},${d.target.y}`
            }
            return `M${d.source.x},${d.source.y} L${d.target.x},${d.target.y}`
          })

        linkLabelElements
          .attr('x', d => (d.source.x + d.target.x) / 2)
          .attr('y', d => (d.source.y + d.target.y) / 2)

        // 更新节点组的位置（节点组包含circle）
        nodeGroups
          .attr('transform', d => `translate(${d.x},${d.y})`)

        labelElements
          .attr('x', d => d.x)
          .attr('y', d => {
            // 根据节点实际大小调整标签位置
            const degree = graphData.value.edges.filter(edge => {
              const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source
              const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target
              return sourceId === d.id || targetId === d.id
            }).length
            const radius = Math.max(nodeSize.value * 0.7, Math.min(nodeSize.value * 1.8, nodeSize.value + degree * 2))
            return d.y + radius + 15
          })
      })
    }

    // 节点点击处理
    const handleNodeClick = (event, d) => {
      selectedNode.value = d
      nodeDetailVisible.value = true
      emit('node-selected', d)

      // 高亮节点和相关边
      highlightNode(d)
    }

    // 高亮节点
    const highlightNode = (node) => {
      if (!nodeElements || !linkElements) return

      // 重置所有节点和边的样式
      nodeElements.attr('opacity', 0.3)
      linkElements.attr('opacity', 0.1)

      // 高亮选中节点
      nodeElements
        .filter(d => d.id === node.id)
        .attr('opacity', 1)
        .attr('r', nodeSize.value * 1.5)

      // 高亮相关边和节点
      const relatedNodeIds = new Set([node.id])
      linkElements
        .filter(d => d.source.id === node.id || d.target.id === node.id)
        .attr('opacity', 1)
        .each(d => {
          relatedNodeIds.add(d.source.id)
          relatedNodeIds.add(d.target.id)
        })

      nodeElements
        .filter(d => relatedNodeIds.has(d.id))
        .attr('opacity', 1)
    }

    // 拖拽处理
    const dragStart = (event, d) => {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      d.fx = d.x
      d.fy = d.y
    }

    const dragging = (event, d) => {
      d.fx = event.x
      d.fy = event.y
    }

    const dragEnd = (event, d) => {
      if (!event.active) simulation.alphaTarget(0)
      d.fx = null
      d.fy = null
    }

    // 更新布局
    const updateLayout = () => {
      if (!simulation || !nodes) return

      simulation.stop()

      const width = graphRef.value.clientWidth
      const height = graphHeight.value

      if (layoutMode.value === 'circle') {
        const radius = Math.min(width, height) / 2 - 50
        nodes.forEach((node, i) => {
          const angle = (i / nodes.length) * 2 * Math.PI
          node.x = width / 2 + radius * Math.cos(angle)
          node.y = height / 2 + radius * Math.sin(angle)
          node.fx = node.x
          node.fy = node.y
        })
      } else if (layoutMode.value === 'tree') {
        // 简单的树形布局
        const levels = {}
        const visited = new Set()
        const queue = [nodes[0]]
        levels[nodes[0].id] = 0
        
        while (queue.length > 0) {
          const current = queue.shift()
          if (visited.has(current.id)) continue
          visited.add(current.id)
          
          links.forEach(link => {
            if (link.source.id === current.id && !visited.has(link.target.id)) {
              levels[link.target.id] = levels[current.id] + 1
              queue.push(link.target)
            }
          })
        }
        
        const levelCounts = {}
        Object.values(levels).forEach(level => {
          levelCounts[level] = (levelCounts[level] || 0) + 1
        })
        
        const levelPositions = {}
        nodes.forEach(node => {
          const level = levels[node.id] || 0
          levelPositions[level] = (levelPositions[level] || 0) + 1
          
          node.x = (width / (levelCounts[level] + 1)) * levelPositions[level]
          node.y = (height / (Math.max(...Object.keys(levels).map(Number)) + 2)) * (level + 1)
          node.fx = node.x
          node.fy = node.y
        })
      } else {
        // 力导图模式，释放固定位置
        nodes.forEach(node => {
          node.fx = null
          node.fy = null
        })
        simulation.alphaTarget(0.3).restart()
      }
      
      if (layoutMode.value !== 'force') {
        simulation.tick()
        // 异常25修复：手动更新元素位置以确保布局切换生效
        if (nodeElements && linkElements && labelElements) {
          nodeElements
            .attr('cx', d => d.x)
            .attr('cy', d => d.y)
          
          linkElements
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y)
          
          labelElements
            .attr('x', d => d.x)
            .attr('y', d => d.y + nodeSize.value + 15)
          
          // 更新边标签位置
          svg.selectAll('.edge-label')
            .attr('x', d => (d.source.x + d.target.x) / 2)
            .attr('y', d => (d.source.y + d.target.y) / 2)
        }
      }
    }

    // 更新节点大小
    const updateNodeSize = () => {
      if (nodeElements) {
        nodeElements.attr('r', nodeSize.value)
        // 同时更新节点标签位置
        if (labelElements) {
          labelElements.attr('y', d => d.y + nodeSize.value + 15)
        }
      }
    }

    // 切换标签显示
    const toggleLabels = () => {
      if (labelElements) {
        labelElements.style('display', showLabels.value ? 'block' : 'none')
      }
    }

    // 切换边标签显示
    const toggleEdgeLabels = () => {
      if (svg) {
        // 直接选择边标签元素并更新显示状态
        svg.selectAll('.edge-label')
          .style('display', showEdgeLabels.value ? 'block' : 'none')
      }
    }

    // 切换缩放功能
    const toggleZoom = () => {
      if (svg) {
        if (enableZoom.value) {
          const zoom = d3.zoom()
            .scaleExtent([0.1, 10])
            .on('zoom', (event) => {
              svg.select('.graph-content').attr('transform', event.transform)
            })
          svg.call(zoom)
        } else {
          svg.on('.zoom', null)
        }
      }
    }

    // 导出图谱
    const exportGraph = () => {
      if (!svg) return
      
      const svgElement = svg.node()
      const serializer = new XMLSerializer()
      const svgString = serializer.serializeToString(svgElement)
      
      const blob = new Blob([svgString], { type: 'image/svg+xml' })
      const url = URL.createObjectURL(blob)
      
      const link = document.createElement('a')
      link.href = url
      link.download = `knowledge-graph-${props.documentId || props.documentName || 'graph'}.svg`
      link.click()
      
      URL.revokeObjectURL(url)
      ElMessage.success('图谱导出成功')
    }

    // 获取节点颜色
    const getNodeColor = (type) => {
      return nodeColorScale(type)
    }

    // 获取边颜色
    const getEdgeColor = (type) => {
      return edgeColorScale(type)
    }

    // 异常25修复：添加tooltip功能
    let tooltip = null
    
    const showTooltip = (event, d) => {
      if (!tooltip) {
        tooltip = d3.select('body').append('div')
          .attr('class', 'graph-tooltip')
          .style('position', 'absolute')
          .style('visibility', 'hidden')
          .style('background', 'rgba(0, 0, 0, 0.8)')
          .style('color', 'white')
          .style('padding', '10px')
          .style('border-radius', '5px')
          .style('font-size', '12px')
          .style('pointer-events', 'none')
          .style('z-index', '9999')
      }
      
      // 计算节点度数
      const degree = graphData.value.edges.filter(edge => {
        const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source
        const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target
        return sourceId === d.id || targetId === d.id
      }).length
      
      tooltip
        .style('visibility', 'visible')
        .html(`
          <div><strong>${d.name}</strong></div>
          <div>类型: ${d.type}</div>
          <div>连接数: ${degree}</div>
          ${d.description ? `<div>描述: ${d.description}</div>` : ''}
          ${d.confidence ? `<div>置信度: ${(d.confidence * 100).toFixed(1)}%</div>` : ''}
        `)
        .style('left', (event.pageX + 10) + 'px')
        .style('top', (event.pageY - 10) + 'px')
    }
    
    const hideTooltip = () => {
      if (tooltip) {
        tooltip.style('visibility', 'hidden')
      }
    }

    // 生命周期
    onMounted(() => {
      loadKnowledgeTables()
      
      // 监听窗口大小变化
      const resizeHandler = () => {
        if (graphData.value) {
          renderGraph()
        }
      }
      window.addEventListener('resize', resizeHandler)
    })

    onUnmounted(() => {
      if (simulation) {
        simulation.stop()
      }
      window.removeEventListener('resize', resizeHandler)
    })

    return {
      graphRef,
      graphData,
      knowledgeTables,
      selectedDocumentOption,
      loading,
      selectedNode,
      nodeDetailVisible,
      layoutMode,
      nodeSize,
      showLabels,
      showEdgeLabels,
      enableZoom,
      graphHeight,
      nodeTypes,
      edgeTypes,
      neighbors,
      relatedRelations,
      documentNameModel,
      loadKnowledgeTables,
      loadKnowledgeGraph,
      handleDocumentChange,
      updateLayout,
      updateNodeSize,
      toggleLabels,
      toggleEdgeLabels,
      toggleZoom,
      exportGraph,
      highlightNode,
      getNodeColor,
      getEdgeColor
    }
  }
}
</script>

<style scoped>
.knowledge-graph {
  width: 100%;
  height: 100%;
}

.graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.graph-header h3 {
  margin: 0;
  color: #409eff;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.graph-controls {
  margin-bottom: 20px;
}

.control-row {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.control-row:last-child {
  margin-bottom: 0;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-item label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
}

.graph-stats {
  margin-bottom: 20px;
}

.graph-container {
  display: flex;
  gap: 20px;
  position: relative;
}

.graph-canvas {
  flex: 1;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background-color: #fff;
  overflow: hidden;
  position: relative; /* 异常57修复：确保v-loading加载文字居中 */
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 异常59修复：图谱加载覆盖层样式 */
.graph-load-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(255, 255, 255, 0.95);
  z-index: 10;
}

.load-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
  padding: 40px;
}

.load-message {
  margin: 0;
  color: #606266;
  font-size: 16px;
}

.load-button {
  font-size: 16px;
  padding: 12px 24px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.3);
  transition: all 0.3s ease;
}

.load-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.4);
}

.graph-legend {
  width: 200px;
  flex-shrink: 0;
}

.legend-section {
  margin-bottom: 16px;
}

.legend-section:last-child {
  margin-bottom: 0;
}

.legend-section h5 {
  margin: 0 0 8px 0;
  color: #606266;
  font-size: 14px;
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #606266;
}

.legend-node {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1px solid #fff;
}

.legend-edge {
  width: 20px;
  height: 2px;
  border-top: 2px solid;
}

.node-detail {
  padding: 16px 0;
}

.neighbors-section,
.relations-section {
  margin-top: 20px;
}

.neighbors-section h4,
.relations-section h4 {
  margin: 0 0 12px 0;
  color: #606266;
  font-size: 14px;
}

.neighbors-list {
  max-height: 200px;
  overflow-y: auto;
  line-height: 1.8;
}


/* 响应式设计 */
@media (max-width: 768px) {
  .graph-container {
    flex-direction: column;
  }
  
  .graph-legend {
    width: 100%;
  }
  
  .control-row {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }
  
  .control-item {
    justify-content: space-between;
  }
}

/* D3图谱样式 */
:deep(.graph-content) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

:deep(.graph-content text) {
  user-select: none;
}

:deep(.graph-content circle:hover) {
  stroke-width: 3px;
}

:deep(.graph-content line:hover) {
  stroke-width: 3px;
  stroke-opacity: 0.8;
}
</style>