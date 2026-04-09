<template>
  <div class="build-container">
    <h1>知识图谱自动化构建</h1>
    <!-- 修改el-steps宽度为100% -->
    <div class="steps-container">
      <el-steps :active="currentStep" finish-status="success" simple>
        <el-step title="编辑提示词" />
        <el-step title="上传PDF" />
        <el-step title="输入数据库" />
        <el-step title="知识抽取" />
        <el-step title="图谱构建" />
      </el-steps>
    </div>

    <div class="step-content">
      <!-- 步骤1: 编辑提示词 -->
      <div v-show="currentStep === 1" class="step">
        <h2>1. 编辑提示词</h2>
        <div v-if="loadingPrompt" class="loading-container">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在生成提示词...</span>
        </div>
        <el-input
          v-else
          v-model="prompt"
          type="textarea"
          :rows="20"
          placeholder="请输入提示词..."
          class="prompt-textarea"
        />
      </div>

      <!-- 步骤2: 上传PDF文件 -->
      <div v-show="currentStep === 2" class="step">
        <h2>2. 上传PDF文件</h2>
        <el-upload
          class="upload-demo"
          drag
          action="#"
          :auto-upload="false"
          :on-change="handleFileUpload"
          :show-file-list="false"
          accept=".pdf"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            将文件拖到此处，或<em>点击上传</em>
          </div>
        </el-upload>
        <p v-if="uploadedFile" class="uploaded-file">
          已上传文件: {{ uploadedFile.name }}
        </p>
      </div>

      <!-- 步骤3: 输入数据库名称 -->
      <div v-show="currentStep === 3" class="step">
        <h2>3. 输入数据库名称</h2>
        <el-input
          v-model="databaseName"
          placeholder="请输入已存在的Neo4j数据库名称"
          clearable
        />
      </div>

      <!-- 步骤4: 知识抽取 -->
      <div v-show="currentStep === 4" class="step">
        <h2>4. 知识抽取</h2>
        <div v-if="loadingEntities" class="loading-container">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在加载实体数据...</span>
        </div>
        <div v-else-if="entities.length > 0" class="entity-selection">
          <!-- 操作按钮 -->
          <div class="selection-controls">
            <el-button @click="selectAll" type="primary" size="small">全选</el-button>
            <el-button @click="clearSelection" size="small">清空选择</el-button>
            <span class="selection-count">已选择: {{ selectedEntities.length }} / {{ entities.length }}</span>
          </div>

          <!-- 实体列表 -->
          <div class="entity-table-container">
            <el-table
              :data="entities"
              @selection-change="handleSelectionChange"
              ref="entityTable"
              stripe
              style="width: 100%"
              max-height="400"
            >
              <el-table-column type="selection" width="50" />
              <el-table-column prop="id" label="ID" width="280" show-overflow-tooltip />
              <el-table-column prop="name" label="名称" width="150" show-overflow-tooltip />
              <el-table-column prop="type" label="类型" width="120" />
              <el-table-column label="属性" min-width="200">
                <template #default="scope">
                  <div class="properties-cell">
                    <el-tag
                      v-for="(value, key) in scope.row.properties"
                      :key="key"
                      size="small"
                      class="property-tag"
                    >
                      {{ key }}: {{ value }}
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
        <el-empty v-else description="暂无实体数据" />
      </div>

      <!-- 步骤5: 开始构建 -->
      <div v-show="currentStep === 5" class="step">
        <h2>5. 开始构建</h2>
        <div class="build-summary">
          <p>将使用选中的 <strong>{{ selectedEntities.length }}</strong> 个实体进行知识图谱构建</p>
        </div>
        <el-button
          type="primary"
          @click="startBuilding"
          :loading="isBuilding"
          :disabled="selectedEntities.length === 0"
        >
          {{ isBuilding ? '构建中...' : '开始构建' }}
        </el-button>
        <el-alert
          v-if="buildResult"
          :title="buildResult"
          :type="buildResult.includes('成功') ? 'success' : 'error'"
          show-icon
          class="result-alert"
        />
      </div>
    </div>

    <div class="step-actions">
      <el-button v-if="currentStep > 1" @click="prevStep">上一步</el-button>
      <el-button
        v-if="currentStep < 5"
        type="primary"
        @click="nextStep"
        :disabled="!canProceed"
      >
        下一步
      </el-button>
    </div>
  </div>
</template>

<script setup>
import {computed, onMounted, ref, nextTick} from 'vue';
import neo4j from 'neo4j-driver';
import { UploadFilled, Loading } from '@element-plus/icons-vue';

// Neo4j连接配置
const NEO4J_URI = 'bolt://localhost:7687';
const NEO4J_USER = 'neo4j';
const NEO4J_PASSWORD = '12345678';

// 数据状态
const currentStep = ref(1);
const ontologies = ref([]);
const selectedOntology = ref(null);
const prompt = ref('');
const uploadedFile = ref(null);
const databaseName = ref('');

// 新增: 实体相关状态
const entities = ref([]);
const selectedEntities = ref([]);
const loadingEntities = ref(false);
const entityTable = ref(null);

// 加载状态
const loadingOntologies = ref(false);
const loadingPrompt = ref(false);
const isBuilding = ref(false);
const buildResult = ref('');
const buildProgress = ref(0);
const buildStatus = ref('');
const buildStatusText = ref('');

onMounted(async () => {
  await selectOntology("ahmi");
  await fetchOntologies();
});

// 计算是否可以进入下一步
const canProceed = computed(() => {
  switch (currentStep.value) {
    case 1: return prompt.value.trim() !== '';
    case 2: return uploadedFile.value !== null;
    case 3: return databaseName.value.trim() !== '';
    case 4: return selectedEntities.value.length > 0;
    default: return true;
  }
});

const nextStep = async () => {
  if (canProceed.value && currentStep.value < 5) {
    currentStep.value++;
    // 当进入第4步时，加载实体数据
    if (currentStep.value === 4) {
      await fetchEntities();
    }
  }
};

const prevStep = () => {
  if (currentStep.value > 1) {
    currentStep.value--;
  }
};

// 步骤1: 获取所有Ontology节点
const fetchOntologies = async () => {
  loadingOntologies.value = true;
  try {
    const driver = neo4j.driver(NEO4J_URI, neo4j.auth.basic(NEO4J_USER, NEO4J_PASSWORD));
    const session = driver.session({ database: 'ontology' });

    const result = await session.run(
      'MATCH (n:Ontology) RETURN n.name AS name, n.description AS description, n.id AS id'
    );

    ontologies.value = result.records.map(record => ({
      id: record.get('id'),
      name: record.get('name'),
      description: record.get('description')
    }));

    await session.close();
    await driver.close();
  } catch (error) {
    console.error('获取本体库失败:', error);
    alert('获取本体库失败，请检查Neo4j连接');
  } finally {
    loadingOntologies.value = false;
  }
};

// 选择本体库并获取提示词
const selectOntology = async (ontology) => {
  selectedOntology.value = ontology;
  loadingPrompt.value = true;
  try {
    const ontologyId = ontology?.id ?? 1.1
    const prompt_url = `/api/ontology/prompt/${ontologyId}`

    const response = await fetch(prompt_url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    prompt.value = data.prompt;
  } catch (error) {
    console.error('获取提示词失败:', error);
    prompt.value = '获取提示词失败！';
  } finally {
    loadingPrompt.value = false;
  }
};

// 新增: 获取实体数据
const fetchEntities = async () => {
  loadingEntities.value = true;
  try {
    const response = await fetch('/api/entities/list', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    entities.value = data.entities || [];
  } catch (error) {
    console.error('获取实体数据失败:', error);
    entities.value = [];
  } finally {
    loadingEntities.value = false;
  }
};

// 新增: 处理选择变化
const handleSelectionChange = (selection) => {
  selectedEntities.value = selection;
};

// 新增: 全选功能
const selectAll = () => {
  nextTick(() => {
    entityTable.value.toggleAllSelection();
  });
};

// 新增: 清空选择
const clearSelection = () => {
  nextTick(() => {
    entityTable.value.clearSelection();
  });
};

// 处理文件上传
const handleFileUpload = (file) => {
  uploadedFile.value = file.raw;
};

// 修改: 开始构建知识图谱
const startBuilding = async () => {
  if (!databaseName.value) {
    alert('请输入数据库名称');
    return;
  }

  if (selectedEntities.value.length === 0) {
    alert('请选择至少一个实体');
    return;
  }

  isBuilding.value = true;
  buildResult.value = '';
  buildProgress.value = 0;
  buildStatus.value = '';
  buildStatusText.value = '正在初始化构建任务...';

  try {
    const formData = new FormData();
    formData.append('file', uploadedFile.value);
    formData.append('database_name', databaseName.value);
    formData.append('prompt', prompt.value);
    formData.append('selected_entities', JSON.stringify(selectedEntities.value.map(e => e.id)));

    const response = await fetch('/api/build/kg_build', {
      method: 'POST',
      body: formData
    });

    const result = await response.json();
    buildResult.value = result.success
      ? '知识图谱构建成功!'
      : '构建失败: ' + result.message;
  } catch (error) {
    console.error('构建失败:', error);
    buildResult.value = '构建过程中发生错误';
  } finally {
    isBuilding.value = false;
  }
};
</script>

<style scoped>
.build-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  width: 95%;
}

.steps-container {
  width: 100%;
  margin: 30px 0;
  padding: 15px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.el-steps {
  width: 100%;
}

.el-steps--simple {
  background: transparent !important;
  padding: 0 !important;
}

.el-step {
  flex: 1;
  min-width: 0;
}

.step-content {
  margin: 30px 0;
}

.step {
  padding: 25px;
  border-radius: 8px;
  background-color: #fff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.ontology-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-top: 20px;
}

.ontology-item {
  cursor: pointer;
  transition: all 0.3s;
}

.ontology-item.selected {
  border-color: #409eff;
  background-color: #f0f7ff;
}

.prompt-textarea {
  margin-top: 15px;
}

.uploaded-file {
  margin-top: 15px;
  color: #666;
}

.result-alert {
  margin-top: 20px;
}

.step-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 30px;
}

.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #666;
}

.loading-container .el-icon {
  margin-right: 10px;
  font-size: 20px;
  animation: rotating 2s linear infinite;
}

/* 新增: 实体选择相关样式 */
.entity-selection {
  margin-top: 20px;
}

.selection-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
  padding: 10px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.selection-count {
  color: #666;
  font-size: 14px;
  margin-left: auto;
}

.entity-table-container {
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.properties-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.property-tag {
  margin: 2px 0;
}

.build-summary {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f0f9ff;
  border-radius: 4px;
  border-left: 4px solid #409eff;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

h1 {
  text-align: left;
  margin-bottom: 30px;
  color: #303133;
  font-size: 30px;
}

h2 {
  margin-bottom: 20px;
  color: #606266;
}
</style>