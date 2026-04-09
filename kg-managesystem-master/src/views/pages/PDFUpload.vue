<template>
  <div class="page-container">
    <div class="main-content">
      <div class="content-header">
        <h2 class="content-title">文档管理</h2>
        <div class="file-count-wrapper">
          <span>文件总数</span>
          <span class="file-count-number">{{ totalFiles }}</span>
        </div>
      </div>

      <div class="upload-section">
        <el-row :gutter="20">
          <el-col :span="8" v-for="repo in repositories" :key="repo.type">
            <div class="upload-card" @click="triggerUpload(repo.type)">
               <el-icon class="upload-card-icon" :size="28"><component :is="repo.icon" /></el-icon>
              <span class="upload-card-title">{{ repo.name }}</span>
              <span class="upload-card-description">{{ repo.description }}</span>
            </div>
          </el-col>
        </el-row>
        <div class="upload-tip">支持拖拽或点击上传，单个文件最大50MB，可多选</div>
        <el-upload
          ref="uploadRef"
          style="position: absolute; width: 1px; height: 1px; overflow: hidden; opacity: 0;"
          name="files"
          drag
          multiple
          :action="uploadUrl"
          :data="uploadData"
          :on-success="handleUploadSuccess"
          :on-error="handleUploadError"
          :before-upload="beforeUpload"
          :show-file-list="false"
          accept=".pdf, .doc, .docx, .xls, .xlsx,.ppt, .pptx, .jpg, .jpeg, .png"
        >
        </el-upload>
      </div>

      <div class="file-list-section">
        <div class="list-header">
          <h3 class="list-title">文件列表</h3>
          <div class="list-actions">
            <el-input
              v-model="searchQuery"
              placeholder="搜索文件名、量化索引码"
              :prefix-icon="Search"
              clearable
              @keyup.enter="handleSearch"
              @clear="fetchFiles"
            />
            <el-button @click="refreshList">查询</el-button>
          </div>
        </div>
        <el-table :data="fileList" style="width: 100%" v-loading="loading" stripe>
          <el-table-column prop="file_name" label="文件名" min-width="250">
            <template #default="scope">
              <div class="file-name-cell">
                <img :src="getFileIcon(scope.row.file_name)" class="file-type-icon" alt="icon"/>
                <!-- 编辑状态只显示文件名主体，非编辑状态显示完整文件名（含后缀） -->
                <template v-if="editingId === scope.row.id">
                  <el-input 
                    v-model="editingFileName"
                    size="small" 
                    @keyup.enter="saveEdit(scope.row)"  
                    @blur="saveEdit(scope.row)"       
                    placeholder="请输入文件名"
                  />
                  <!-- 可选：显示灰色的后缀提示 -->
                  <span class="edit-mode-extension">.{{ editingFileExt }}</span>
                </template>
                <span v-else>{{ scope.row.file_name }}</span>
              </div>
            </template>
          </el-table-column>
          <!-- 所属库列：新增编辑状态逻辑 -->
          <el-table-column prop="repository" label="所属库" width="120" align="center">
            <template #default="scope">
            <!-- 编辑状态：显示下拉选择器 -->
            <template v-if="editingId === scope.row.id">
              <el-select
                v-model="editingRepoType"
                size="small"
                placeholder="选择所属库"
              style="width: 100px"
              >
              <el-option
                v-for="repo in repositories"
                :key="repo.type"
                :label="repo.name"
                :value="repo.type"
              />
              </el-select>
            </template>
            <!-- 非编辑状态：显示原有标签 -->
              <template v-else>
                <el-tag 
                  :color="getRepositoryTagColor(scope.row.repository).light" 
                  :style="{ color: getRepositoryTagColor(scope.row.repository).dark, border: 'none' }" 
                  size="small"
                > 
                  {{ repoMap[scope.row.repository] || '未知库' }}
                </el-tag>
              </template>
            </template>
          </el-table-column>
          <el-table-column prop="file_size" label="大小" width="120" align="center">
            <template #default="scope">
                {{ formatFileSize(scope.row.file_size) }}
            </template>
          </el-table-column>
          <el-table-column prop="es_code" label="量化索引码" width="150">
              <template #default="scope">
                <div class="es-code-cell">
                  <!-- 索引码文本（超长时省略） -->
                  <span class="es-code-text" :title="scope.row.es_code">{{ scope.row.es_code || '-' }}</span>
                  <!-- 绑定提示 tooltip -->
                  <el-tooltip 
                    content="索引码与文件绑定，修改文件名/所属库不改变此码" 
                    placement="top"
                    effect="light"
                  >
                    <el-icon class="es-code-bind-icon" size="14"><Lock /></el-icon>
                  </el-tooltip>
                </div>
              </template>
          </el-table-column>
          <el-table-column prop="upload_time" label="上传时间" width="180" sortable>
              <template #default="scope">
                {{ formatTime(scope.row.upload_time) }}
              </template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right" align="center">
            <template #default="scope">
            <!-- 查看按钮：添加格式判断的禁用逻辑 -->
            <el-button 
              type="primary" 
              link 
              @click="handlePreview(scope.row)"
              
              :disabled="!isPreviewable(scope.row.file_name)"
      
              :class="{ 'preview-disabled': !isPreviewable(scope.row.file_name) }"
      
              @click.prevent="!isPreviewable(scope.row.file_name) ? null : handlePreview(scope.row)"
            >
              查看
            </el-button>
            <!-- 其他按钮（下载/编辑/保存/删除）保持不变 -->
          <el-button type="primary" link @click="handleDownload(scope.row)">下载</el-button>
          <el-button type="primary" link @click="startEdit(scope.row)" v-if="editingId !== scope.row.id">编辑</el-button>
          <el-button type="primary" link @click="saveEdit(scope.row)" v-else>保存</el-button>
          <el-button type="danger" link @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
        </el-table>
        <div class="pagination-wrapper">
          <div class="total-count">总计: {{ totalFiles }} 个文件</div>
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :small="false"
            :disabled="loading"
            :background="true"
            layout="total, sizes, prev, pager, next, jumper"
            :total="totalFiles"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </div>
    </div>

    <el-drawer v-model="previewVisible" :title="`预览: ${previewFile?.file_name}`" size="80%">
      <!-- 图片格式用 img 预览 -->
      <img 
        v-if="['jpg', 'jpeg', 'png'].includes(previewFile?.file_name.toLowerCase().split('.').pop())"
        :src="previewUrl" 
        style="width: 100%; height: auto; object-fit: contain;" 
        alt="预览图片"
      />
      <!-- 其他格式用 iframe 预览 -->
      <iframe 
        v-else
        v-if="previewUrl" 
        :src="previewUrl" 
        width="100%" 
        height="100%" 
        allow="fullscreen"
        style="border: none;"
      />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, shallowRef, onBeforeUnmount } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Search, Setting, Opportunity, Document, Lock } from '@element-plus/icons-vue';
import { onBeforeRouteLeave } from 'vue-router';
import axios from 'axios';

// --- 配置 ---
// 通过nginx将 /pdf/* 反代到 pdf-flask-handler:8001
const API_BASE_URL = '/pdf';

// --- 组件状态 ---
const fileList = ref([]);
const loading = ref(false);
const totalFiles = ref(0);
const searchQuery = ref('');
const previewVisible = ref(false);
const previewFile = ref(null);
const previewUrl = ref('');
const editingId = ref(null);
const editingFileName = ref(''); // 只存储文件名主体（不含后缀）
const editingFileExt = ref('');  // 存储文件后缀（不可编辑）
const uploadRef = ref(null);
const currentLibraryType = ref('');

// --- 分页状态 ---
const currentPage = ref(1);      // 当前页码
const pageSize = ref(10);        // 每页显示数量
const totalPages = ref(0);       // 总页数

// --- 计算属性 ---
const uploadUrl = computed(() => `${API_BASE_URL}/upload/batch`);
const uploadData = computed(() => ({ library_type: currentLibraryType.value }));

// --- 静态数据 ---
const repositories = ref([
  { name: '维修库', type: 'maintenance', description: '上传设备维修相关文档', icon: shallowRef(Setting) },
  { name: '经验库', type: 'experience', description: '上传操作经验相关文档', icon: shallowRef(Opportunity) },
  { name: '操作库', type: 'operation', description: '上传标准操作相关文档', icon: shallowRef(Document) }
]);
const repoMap = {
  maintenance: '维修库',
  experience: '经验库',
  operation: '操作库'
};

// --- 生命周期钩子 ---
onMounted(() => {
  fetchFiles();
});

// --- 数据获取 ---
const fetchFiles = async () => {
  console.log(`🔍 获取文件列表 - 页码:${currentPage.value}, 大小:${pageSize.value}, 搜索:"${searchQuery.value}"`);
  loading.value = true;
  try {
    const response = await axios.get(`${API_BASE_URL}/files`, {
      params: { 
        search: searchQuery.value || undefined,
        page: currentPage.value,
        size: pageSize.value
      }
    });
    if (response.data.status === 'success') {
      fileList.value = response.data.data.files;
      totalFiles.value = response.data.data.pagination.total;
      totalPages.value = Math.ceil(totalFiles.value / pageSize.value);
      console.log(`✅ 文件列表加载成功 - 共${totalFiles.value}个文件, ${fileList.value.length}个当前页文件`);
    } else {
      ElMessage.error('获取文件列表失败: ' + response.data.message);
    }
  } catch (error) {
    ElMessage.error('获取文件列表失败，请检查后端服务是否开启。');
    console.error("获取文件列表时出错:", error);
  } finally {
    loading.value = false;
  }
};

// --- 事件处理 ---
const handleSearch = () => { 
  currentPage.value = 1; // 搜索时重置到第一页
  fetchFiles(); 
};
const refreshList = () => { 
  searchQuery.value = ''; 
  currentPage.value = 1; // 刷新时重置到第一页
  fetchFiles(); 
};

// --- 分页事件处理 ---
const handleCurrentChange = (page) => {
  currentPage.value = page;
  fetchFiles();
};

const handleSizeChange = (size) => {
  pageSize.value = size;
  currentPage.value = 1; // 改变页大小时重置到第一页
  fetchFiles();
};

// --- 上传逻辑 ---
const triggerUpload = (libraryType) => {
  console.log(`📤 触发上传 - 库类型: ${libraryType}`);
  currentLibraryType.value = libraryType;
  uploadRef.value?.$el.querySelector('input').click();
};

const beforeUpload = (file) => {
  console.log(`⏳ 文件上传前检查: ${file.name}, 类型: ${file.type}, 大小: ${file.size}`);
  
  const allowedTypes = [
    // PDF
    'application/pdf',
    // Word
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    // Excel
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    // PPT
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    // 新增：图片格式（JPG/JPEG/PNG）对应的 MIME 类型
    'image/jpeg',   // JPG、JPEG 通用 MIME 类型
    'image/png'     // PNG 对应的 MIME 类型
  ];
  const isAllowed = allowedTypes.includes(file.type);
  if (!isAllowed) {
    // 修正提示文本，补充图片格式说明
    ElMessage.error('只能上传 PDF、Word、Excel、PPT、JPG、JPEG 或 PNG 格式的文件!');
    return false;
  }
  const isLt50M = file.size / 1024 / 1024 < 50;
  if (!isLt50M) {
    ElMessage.error('文件大小不能超过 50MB!');
    return false;
  }
  console.log(`✅ 文件检查通过: ${file.name}`);
  return true;
};

// 修改：handleUploadSuccess 函数，强化es_code存在性判定
const handleUploadSuccess = (response, uploadFile, uploadFiles) => {
  console.log('🚀 上传成功回调触发:', response);
  
  if (response.status !== 'success') {
    ElMessage.error(response.message || `文件上传请求失败`);
    return;
  }

  const { success_files, failed_files, success_count, failed_count } = response.data;
  let actualSuccessCount = 0;
  let actualFailedFiles = [...failed_files]; // 初始包含后端返回的失败文件

  // 核心判定：success_files中必须包含es_code才视为真正成功，否则归为失败
  success_files.forEach(file => {
    if (file.es_code && file.es_code.trim()) {
      actualSuccessCount++; // 有es_code，算成功
    } else {
      // 无es_code，归为失败，补充原因
      actualFailedFiles.push({
        file_name: file.file_name,
        reason: "索引码（es_code）生成失败，文件上传终止"
      });
    }
  });

  // 提示最终结果（仅统计有es_code的文件为成功）
  if (actualSuccessCount > 0 && actualFailedFiles.length === 0) {
    ElMessage.success(`所有文件上传成功！共 ${actualSuccessCount} 个，索引码已生成`);
  } else if (actualSuccessCount > 0 && actualFailedFiles.length > 0) {
    ElMessage.warning(`部分文件上传成功（${actualSuccessCount} 个），${actualFailedFiles.length} 个失败：${actualFailedFiles.map(f => f.file_name).join('、')}`);
    // 显示上传失败详情
    showUploadFailDetail(actualFailedFiles);
  } else {
    ElMessage.error(`所有文件上传失败（${actualFailedFiles.length} 个），请检查索引服务`);
    showUploadFailDetail(actualFailedFiles);
  }

  // 上传完成后重置到第一页并清空搜索，显示最新文件
  console.log('📝 准备刷新文件列表...');
  searchQuery.value = '';  // 先清空搜索
  currentPage.value = 1;   // 重置到第一页
  setTimeout(() => {
    console.log('🔄 执行文件列表刷新');
    fetchFiles();          // 刷新文件列表
  }, 500);  // 增加延迟确保后端处理完成
};

// 新增：显示上传失败详情的弹窗
const showUploadFailDetail = (failedFiles) => {
  ElMessageBox.alert(
    `<div style="max-height: 200px; overflow-y: auto;">
      ${failedFiles.map((file, index) => `
        <div style="margin: 8px 0;">
          <span>${index + 1}. 文件名：${file.file_name}</span>
          <br>
          <span style="color: #f56c6c; font-size: 12px;">原因：${file.reason}</span>
        </div>
      `).join('')}
    </div>`,
    '上传失败详情',
    {
      dangerouslyUseHTMLString: true,
      confirmButtonText: '确认',
      type: 'error'
    }
  );
};




const handleUploadError = (error, uploadFile) => {
  console.log('❌ 上传失败回调触发:', error);
  
  try {
    const errorData = JSON.parse(error.message);
    ElMessage.error(errorData.message || `文件 ${uploadFile.name} 上传失败`);
  } catch {
    ElMessage.error(`文件 ${uploadFile.name} 上传失败，服务器无响应或发生网络错误`);
  }
  console.error("上传失败:", error);
  
  // 上传失败时也刷新列表，确保状态一致
  console.log('🔄 上传失败，刷新文件列表');
  setTimeout(() => {
    fetchFiles();
  }, 300);
};

// --- 文件操作 ---
const handlePreview = (file) => {
  previewFile.value = file;
  previewUrl.value = `${API_BASE_URL}/files/${file.repository}/${file.id}/preview`;
  previewVisible.value = true;
};

const handleDownload = async (file) => {
    try {
        const response = await axios.get(
            `${API_BASE_URL}/files/${file.repository}/${file.id}/download`,
            { 
                responseType: 'blob',
                withCredentials: true,
                headers: {
                    'Accept': '*/*'
                }
            }
        );    
        const blob = new Blob([response.data]);
        const url = window.URL.createObjectURL(blob);

        const link = document.createElement('a');
        link.href = url;
        link.download = file.file_name;
        document.body.appendChild(link);
        link.click();

        window.URL.revokeObjectURL(url);
        document.body.removeChild(link);

        ElMessage.success('文件下载开始');
  } catch (error) {
    console.error('下载失败:', error);
    ElMessage.error('文件下载失败');
  }
};
// --- 新增：存储待修改的所属库类型 ---
const editingRepoType = ref(''); // 存储编辑中的所属库type（如maintenance）

// 修改：startEdit 函数，添加索引码不变提示
const startEdit = (file) => {
  editingId.value = file.id;
  
  // 原有逻辑：拆分文件名和后缀
  const lastDotIndex = file.file_name.lastIndexOf('.');
  if (lastDotIndex > 0) { 
    editingFileName.value = file.file_name.slice(0, lastDotIndex);
    editingFileExt.value = file.file_name.slice(lastDotIndex + 1);
  } else { 
    editingFileName.value = file.file_name;
    editingFileExt.value = '';
  }

  // 原有逻辑：初始化所属库
  editingRepoType.value = file.repository;

  // 新增：提示索引码不变
  ElMessage.info(`当前文件索引码：${file.es_code}，修改文件名/所属库不改变此码`);
};

// --- 原有saveEdit函数：修改为同时提交文件名和所属库 ---
const saveEdit = async (file) => {
  if (editingId.value !== file.id) return;

  // 1. 原有：文件名校验（保持不变）
  let newFileName = editingFileName.value.trim();
  if (!newFileName) {
    ElMessage.error('文件名不能为空！');
    return;
  }
  const invalidChars = /[\\/:*?"<>|.]/g;
  if (invalidChars.test(newFileName)) {
    ElMessage.error('文件名不能包含 \\ / : * ? " < > | 或 . 这些字符！');
    return;
  }
  const fullFileName = editingFileExt.value 
    ? `${newFileName}.${editingFileExt.value}` 
    : newFileName;

  // 2. 新增：判断是否需要修改（文件名或所属库有一个变化即需要提交）
  const isFileNameChanged = fullFileName !== file.file_name;
  const isRepoChanged = editingRepoType.value !== file.repository;
  if (!isFileNameChanged && !isRepoChanged) {
    editingId.value = null; // 无变化则取消编辑
    return;
  }

  // 3. 原有：调用后端接口（修改参数，新增repository字段）
  try {
    const response = await axios.put(
      `${API_BASE_URL}/files/${file.repository}/${file.id}`, // 注意：URL中的旧库类型保持不变（后端可能需要旧库路径定位文件）
      { 
        file_name: fullFileName,       // 原有：新文件名
        repository: editingRepoType.value // 新增：新所属库类型
      }
    );
    if (response.data.status === 'success') {
      ElMessage.success('文件信息修改成功！');
      // 4. 自动刷新文件列表以确保数据一致性
      fetchFiles();
    } else {
      ElMessage.error(response.data.message || '文件信息修改失败');
    }
  } catch (error) {
    ElMessage.error('修改请求失败，请检查网络');
    console.error('保存文件信息失败:', error);
  } finally {
    editingId.value = null; // 无论成功失败，都退出编辑状态
  }
};

const handleDelete = async (file) => {
  try {
    await ElMessageBox.confirm(`确定要删除文件 "${file.file_name}" 吗？`, '删除确认', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning',
    });
    const response = await axios.delete(`${API_BASE_URL}/files/${file.repository}/${file.id}`);
    if (response.data.status === 'success') {
      ElMessage.success('删除成功');
      fetchFiles();
    } else {
       ElMessage.error(response.data.message || '删除失败');
    }
  } catch (error) {
    if (error.response) {
       ElMessage.error(error.response.data.message || '删除失败');
    } else if (error !== 'cancel') {
      ElMessage.error('删除请求失败');
      console.error(error);
    }
  }
};

// --- 辅助函数 ---
const formatFileSize = (bytes) => {
    if (bytes == null || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const getFileIcon = (fileName) => {
  if (fileName.toLowerCase().endsWith('.pdf')) return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAACVUlEQVRoQ+2Z61HDMAxF250gG5ANyAZkA7IB2QA3gWxANkAbsAHZgGxDNuAYfU/VlcrJLVYp78/lJDudXn/6NOL3AgkCgUBcAcYBCY4AYiAO0OACGIgDaHABIeB9/w8wDphc+u1sC4yA5qA8AzwDTgEV4BvgGvAX2AdugJ9AFLgB/AW2QQtgB/gF1nAIlAEXgC/gQSkwBGwBG8B+YAtkgn0gGtAEXGAYuAbAQR/gG8BWYB3oBTpgCwgFzIDfAELgE3AZeAW8Av4EvgKXAEngDtCagB8BV4BzYN8FFoBdwCvgFhADvAc2QBHwBPAOuAX8S0g/5e0FfAJOAHfAV8AFcIXcAw4BR4BDwCFgBrgGXAb+BNYA84BTQL/kPQIeA2cB04AZ4BPwCDgCvAQ2QIfk/QW8Ao4Az4C3gDdgE/CVkH7Kuwf8e2APOA4sB04AM8A+8B9YBWaBx4CfwGkAB7gEnGSUn/K+AnsBG8A74BOwDzwFjgDdgDvwGbgG3Ac2gL3gE5Bf8j6BTeA0cAZ4ALwGXgK/gT3gNfAR+Aq8As4BR4BDwAngA7AF/Aa+Al8BN4B/gGzgA7gGDAIfAb8BfwFjgBtwG9gB7gB7wB5wA5wA3wEXgGdgF/gB3AEWAK3gE3AHeAA8BNwAjoAPwAvgA/AJeAacgI/AJ2A8sARw/4ACngFngMmgD7wDngEngBfgO9AI/gI2Q/sl5Uf+H/A+gU3gK8D9EnBwBBycAQcnwMEJcMh/D/gAh0H/cKmsjY0AAAAASUVORK5CYII=';
  return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAA7ElEQVRoQ+2Z3Q2DMAxAcQN2gG7QDVgEJ2gG6AZ0g24QN2gG6AZkwyYpQh6Rkh/34T+yH/b5EdO9CAQCAQHCAbgB7IuQeAG8AJtCUg1cAfeFtCfQCeAF2JaSAXABl4V0BvQA3wBbkpIAcJ/LwlogAXgD3iXVB8AJ8B7YlgwBcC/LwnpTE8Af8C6pbiIAHOCdEL0AOoB3QLcmIADwBfwW0o14B9we0grgAfgN3JQ0AFwA74Dt2JUAYB/LwjpbEwAvgB/Bc0kKAPwBfwS3JQnAARwBvgO3JSUA+AN8D9xKAoFAINwB/gB3rD9UcYTAkAAAAABJRU5ErkJggg==';
};

const formatTime = (time) => {
  if (!time) return '-';
  return new Date(time).toLocaleString('zh-CN', { hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }).replace(/\//g, '-');
};

const getRepositoryTagColor = (repoType) => {
  switch (repoType) {
    case 'maintenance': return { light: '#ecf5ff', dark: '#409eff' };
    case 'experience': return { light: '#fdf6ec', dark: '#e6a23c' };
    case 'operation': return { light: '#f0f9eb', dark: '#67c23a' };
    default: return { light: '#f4f4f5', dark: '#909399' };
  }
};

// 新增：判断文件是否支持预览（仅PDF、JPG、JPEG、PNG）
const isPreviewable = (fileName) => {
  if (!fileName) return false;
  // 获取文件后缀（转小写统一判断）
  const fileExt = fileName.toLowerCase().split('.').pop();
  // 可预览的格式列表
  const previewableExts = ['pdf', 'jpg', 'jpeg', 'png'];
  return previewableExts.includes(fileExt);
};

// 路由守卫：清理进行中的请求
onBeforeRouteLeave((to, from, next) => {
  console.log('PDFUpload: onBeforeRouteLeave triggered', 'to:', to.path, 'from:', from.path)
  
  // 取消所有进行中的上传
  loading.value = false
  
  // 清理预览状态
  previewVisible.value = false
  previewFile.value = null
  previewUrl.value = ''
  
  console.log('PDFUpload: Cleared all states, allowing navigation')
  next()
})

// 组件卸载清理
onBeforeUnmount(() => {
  console.log('PDFUpload: Component is being unmounted')
  // 清理所有状态
  loading.value = false
  previewVisible.value = false
  editingId.value = null
})

</script>

<style scoped>
/* --- 其他样式保持不变 --- */

/* 编辑模式下的后缀样式 */
.edit-mode-extension {
  margin-left: 5px;
  color: #909399;
  font-size: 12px;
  user-select: none; /* 防止选中 */
}

/* --- 其他原有样式 --- */
.page-container {
  background-color: #f7f8fa;
  min-height: 100vh;
  padding: 24px;
  font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "微软雅黑", Arial, sans-serif;
}
.main-content {
  max-width: 1400px;
  margin: 0 auto;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  background-color: #ffffff;
  padding: 16px 24px;
  border-radius: 4px;
  border: 1px solid #e6ebf5;
}
.content-title {
  font-size: 18px;
  font-weight: 500;
  color: #303133;
  margin: 0;
}
.file-count-wrapper {
  background-color: #f7f8fa;
  padding: 4px 12px;
  border: 1px solid #e6ebf5;
  border-radius: 4px;
  display: flex;
  align-items: center;
  font-size: 14px;
  color: #606266;
}
.file-count-number {
  margin-left: 8px;
  font-weight: 600;
  color: #409eff;
  font-size: 16px;
  padding: 0 4px;
}

.upload-section {
    background-color: #ffffff;
    padding: 24px;
    border-radius: 4px;
    border: 1px solid #e6ebf5;
}
.upload-card {
  border: 1px solid #e6ebf5;
  background-color: #ffffff;
  border-radius: 4px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.upload-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px 0 rgba(0, 0, 0, 0.08);
}
.upload-card-icon {
  color: #8c939d;
}
.upload-card-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}
.upload-card-description {
  font-size: 13px;
  color: #909399;
}
.upload-tip {
  text-align: center;
  margin-top: 16px;
  font-size: 13px;
  color: #a8abb2;
}

.file-list-section {
  background-color: #ffffff;
  padding: 20px 24px;
  border-radius: 4px;
  border: 1px solid #e6ebf5;
  margin-top: 20px;
}
.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.list-title {
  font-size: 16px;
  margin: 0;
  color: #303133;
}
.list-actions {
  display: flex;
  gap: 10px;
}
.list-actions .el-input {
  width: 280px;
}
:deep(.el-input__wrapper) {
  border-radius: 4px;
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #303133;
}
.file-type-icon {
    width: 20px;
    height: 20px;
    flex-shrink: 0;
}
:deep(.el-table th.el-table__cell) {
  background-color: #f7f8fa !important;
  color: #606266;
  font-weight: 500;
}
:deep(.el-table td.el-table__cell), :deep(.el-table th.el-table__cell) {
  border-bottom: 1px solid #f0f2f5;
}
.el-button.is-link {
  font-size: 13px;
  margin: 0 5px;
}
.el-button.is-link.el-button--danger {
  color: #f56c6c;
}

.pagination-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  padding: 16px 0;
}
.total-count {
  font-size: 14px;
  color: #606266;
  padding: 8px 16px;
  background-color: #f7f8fa;
  border-radius: 4px;
  border: 1px solid #e6ebf5;
}
/* 分页组件样式优化 */
:deep(.el-pagination) {
  justify-content: flex-end;
}
:deep(.el-pagination .el-pager li) {
  min-width: 32px;
  height: 32px;
  line-height: 30px;
  border-radius: 4px;
}
:deep(.el-pagination .btn-prev),
:deep(.el-pagination .btn-next) {
  border-radius: 4px;
}
/* 索引码单元格样式 */
.es-code-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.es-code-text {
  max-width: 120px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #303133;
}
.es-code-bind-icon {
  color: #409eff;
  cursor: help;
}

</style>
