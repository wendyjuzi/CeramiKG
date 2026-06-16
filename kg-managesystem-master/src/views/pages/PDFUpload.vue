<template>
  <div class="page-container">
    <div class="main-content">
      <div class="content-header">
        <div>
          <h2 class="content-title">陶瓷材料文献管理</h2>
          <p class="content-subtitle">支持文献导入、集中存储、检索分类、预览下载和任务创建</p>
        </div>
        <div class="file-count-wrapper">
          <span>文件总数</span>
          <strong>{{ totalFiles }}</strong>
        </div>
      </div>

      <div class="upload-section">
        <div class="upload-card" @click="triggerUpload('ceramic_papers')">
          <div class="upload-card-main">
            <div class="upload-card-icon-wrap">
              <el-icon :size="30"><Document /></el-icon>
            </div>
            <div>
              <h3>陶瓷文献库</h3>
              <p>上传 PDF、Word、Excel、PPT 或图片文件，文献会进入统一列表，后续可用于解析和任务关联。</p>
            </div>
          </div>
          <div class="card-actions">
            <el-button type="primary" @click.stop="triggerUpload('ceramic_papers')">上传文献</el-button>
            <el-button :loading="syncLoading" @click.stop="syncCeramicPapers">同步文献库</el-button>
          </div>
        </div>

        <el-upload
          ref="uploadRef"
          class="hidden-upload"
          name="files"
          multiple
          :action="uploadUrl"
          :data="uploadData"
          :on-success="handleUploadSuccess"
          :on-error="handleUploadError"
          :before-upload="beforeUpload"
          :show-file-list="false"
          accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png"
        />
      </div>

      <div class="file-list-section">
        <div class="list-header">
          <h3 class="list-title">文件列表</h3>
          <div class="list-actions">
            <el-input
              v-model="searchQuery"
              placeholder="搜索标题、DOI、原始文件名、索引码"
              :prefix-icon="Search"
              clearable
              @keyup.enter="handleSearch"
              @clear="fetchFiles"
            />
            <el-select v-model="sortMode" placeholder="排序" class="sort-select" @change="handleSortChange">
              <el-option label="正序" value="id_asc" />
              <el-option label="倒序" value="id_desc" />
            </el-select>
            <el-select v-model="categoryFilter" placeholder="分类" class="category-select" clearable @change="handleCategoryChange">
              <el-option label="有 DOI" value="has_doi" />
              <el-option label="缺失 DOI" value="missing_doi" />
              <el-option label="待审核" value="pending_review" />
              <el-option label="已审核" value="reviewed" />
              <el-option label="元数据增强" value="metadata_enriched" />
            </el-select>
            <el-button @click="refreshList">查询</el-button>
          </div>
        </div>

        <el-table :data="fileList" style="width: 100%" v-loading="loading" stripe>
          <el-table-column prop="file_name" label="真实标题" min-width="300">
            <template #default="scope">
              <div class="file-name-cell">
                <img :src="getFileIcon(scope.row.original_name || scope.row.file_name)" class="file-type-icon" alt="icon" />
                <template v-if="editingId === scope.row.id">
                  <el-input
                    v-model="editingFileName"
                    size="small"
                    placeholder="请输入文件名"
                    @keyup.enter="saveEdit(scope.row)"
                    @blur="saveEdit(scope.row)"
                  />
                  <span v-if="editingFileExt" class="edit-mode-extension">.{{ editingFileExt }}</span>
                </template>
                <span v-else>{{ scope.row.file_name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="original_name" label="原始文件名 / DOI名" min-width="180" show-overflow-tooltip />
          <el-table-column prop="doi" label="DOI" min-width="160" show-overflow-tooltip>
            <template #default="scope">
              {{ scope.row.doi || scope.row.recovered_doi || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="repository" label="所属库" width="120" align="center">
            <template #default="scope">
              <template v-if="editingId === scope.row.id">
                <el-select v-model="editingRepoType" size="small" placeholder="选择所属库">
                  <el-option v-for="repo in repositories" :key="repo.type" :label="repo.name" :value="repo.type" />
                </el-select>
              </template>
              <el-tag v-else :color="getRepositoryTagColor(scope.row.repository).light" :style="{ color: getRepositoryTagColor(scope.row.repository).dark, border: 'none' }" size="small">
                {{ repoMap[scope.row.repository] || '未知库' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="file_size" label="大小" width="110" align="center">
            <template #default="scope">{{ formatFileSize(scope.row.file_size) }}</template>
          </el-table-column>
          <el-table-column prop="es_code" label="量化索引码" width="150">
            <template #default="scope">
              <div class="es-code-cell">
                <span class="es-code-text" :title="scope.row.es_code">{{ scope.row.es_code || '-' }}</span>
                <el-tooltip content="索引码与文件绑定，修改文件名或所属库不会改变此码" placement="top" effect="light">
                  <el-icon class="es-code-bind-icon" size="14"><Lock /></el-icon>
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="upload_time" label="上传时间" width="180" sortable>
            <template #default="scope">{{ formatTime(scope.row.upload_time) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right" align="center">
            <template #default="scope">
              <el-button type="primary" link :disabled="!isPreviewable(scope.row.original_name || scope.row.file_name)" @click="handlePreview(scope.row)">查看</el-button>
              <el-button type="primary" link @click="handleDownload(scope.row)">下载</el-button>
              <el-button type="primary" link @click="openCreateTask(scope.row)">建任务</el-button>
              <el-button v-if="editingId !== scope.row.id" type="primary" link @click="startEdit(scope.row)">编辑</el-button>
              <el-button v-else type="primary" link @click="saveEdit(scope.row)">保存</el-button>
              <el-button type="danger" link @click="handleDelete(scope.row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper">
          <div class="total-count">总计：{{ totalFiles }} 个文件</div>
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :disabled="loading"
            background
            layout="total, sizes, prev, pager, next, jumper"
            :total="totalFiles"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </div>
    </div>

    <el-drawer v-model="previewVisible" :title="`预览：${previewFile?.file_name || ''}`" size="80%">
      <img
        v-if="isImageFile(previewFile?.original_name || previewFile?.file_name)"
        :src="previewUrl"
        class="preview-image"
        alt="预览图片"
      />
      <iframe v-else-if="previewUrl" :src="previewUrl" width="100%" height="100%" allow="fullscreen" class="preview-frame" />
    </el-drawer>

    <el-dialog v-model="taskDialogVisible" title="基于文献创建任务" width="620px">
      <el-form :model="taskForm" label-width="92px">
        <el-form-item label="关联文献">
          <el-input :model-value="selectedTaskDocument?.file_name || '-'" disabled />
        </el-form-item>
        <el-form-item label="任务标题">
          <el-input v-model="taskForm.title" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="任务类型">
            <el-select v-model="taskForm.task_type" class="full-width">
              <el-option label="文献整理" value="literature" />
              <el-option label="图谱构建" value="kg_build" />
              <el-option label="文档审核" value="review" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="taskForm.priority" class="full-width">
              <el-option label="低" value="low" />
              <el-option label="中" value="medium" />
              <el-option label="高" value="high" />
              <el-option label="紧急" value="urgent" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="任务说明">
          <el-input v-model="taskForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="taskSaving" @click="createTaskFromDocument">创建任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Document, Lock, Search } from '@element-plus/icons-vue';
import { onBeforeRouteLeave } from 'vue-router';
import axios from 'axios';

const API_BASE_URL = '/pdf';

const fileList = ref([]);
const loading = ref(false);
const totalFiles = ref(0);
const searchQuery = ref('');
const sortMode = ref('id_asc');
const categoryFilter = ref('');
const syncLoading = ref(false);
const taskDialogVisible = ref(false);
const taskSaving = ref(false);
const selectedTaskDocument = ref(null);
const previewVisible = ref(false);
const previewFile = ref(null);
const previewUrl = ref('');
const editingId = ref(null);
const editingFileName = ref('');
const editingFileExt = ref('');
const editingRepoType = ref('');
const uploadRef = ref(null);
const currentLibraryType = ref('ceramic_papers');
const currentPage = ref(1);
const pageSize = ref(10);
const taskForm = ref({ title: '', description: '', task_type: 'literature', priority: 'medium' });

const uploadUrl = computed(() => `${API_BASE_URL}/upload/batch`);
const uploadData = computed(() => ({ library_type: currentLibraryType.value || 'ceramic_papers' }));

const repositories = ref([
  {
    name: '陶瓷文献库',
    type: 'ceramic_papers',
    description: '陶瓷材料文献统一导入、存储、检索和任务复用',
    icon: shallowRef(Document)
  }
]);

const repoMap = {
  ceramic_papers: '陶瓷文献库'
};

onMounted(() => {
  fetchFiles();
});

const fetchFiles = async () => {
  loading.value = true;
  try {
    const response = await axios.get(`${API_BASE_URL}/files`, {
      params: {
        search: searchQuery.value || undefined,
        page: currentPage.value,
        per_page: pageSize.value,
        sort: sortMode.value,
        category: categoryFilter.value || undefined
      }
    });
    if (response.data.status === 'success') {
      fileList.value = response.data.data.files || [];
      totalFiles.value = response.data.data.pagination?.total || 0;
    } else {
      ElMessage.error(response.data.message || '获取文件列表失败');
    }
  } catch (error) {
    ElMessage.error('获取文件列表失败，请检查后端服务是否开启');
    console.error('获取文件列表失败:', error);
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  currentPage.value = 1;
  fetchFiles();
};

const refreshList = () => {
  currentPage.value = 1;
  fetchFiles();
};

const handleSortChange = () => {
  currentPage.value = 1;
  fetchFiles();
};

const handleCategoryChange = () => {
  currentPage.value = 1;
  fetchFiles();
};

const handleCurrentChange = (page) => {
  currentPage.value = page;
  fetchFiles();
};

const handleSizeChange = (size) => {
  pageSize.value = size;
  currentPage.value = 1;
  fetchFiles();
};

const syncCeramicPapers = async () => {
  if (syncLoading.value) return;
  syncLoading.value = true;
  try {
    const response = await axios.post(`${API_BASE_URL}/files/sync/ceramic-papers`);
    if (response.data.status === 'success') {
      const count = response.data.data?.synced_count || 0;
      ElMessage.success(`同步完成：${count} 篇文献`);
      currentPage.value = 1;
      await fetchFiles();
    } else {
      ElMessage.error(response.data.message || '同步文献库失败');
    }
  } catch (error) {
    ElMessage.error('同步文献库失败，请检查后端服务是否开启');
    console.error('同步陶瓷文献库失败:', error);
  } finally {
    syncLoading.value = false;
  }
};

const triggerUpload = (libraryType) => {
  currentLibraryType.value = libraryType;
  uploadRef.value?.$el.querySelector('input[type="file"]')?.click();
};

const beforeUpload = (file) => {
  const allowedTypes = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'image/jpeg',
    'image/png'
  ];
  const allowedExts = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png'];
  const ext = getFileExt(file.name);
  if (!allowedTypes.includes(file.type) && !allowedExts.includes(ext)) {
    ElMessage.error('只能上传 PDF、Word、Excel、PPT、JPG、JPEG 和 PNG 格式的文件');
    return false;
  }
  if (file.size / 1024 / 1024 >= 50) {
    ElMessage.error('文件大小不能超过 50MB');
    return false;
  }
  return true;
};

const handleUploadSuccess = (response) => {
  if (response.status !== 'success') {
    ElMessage.error(response.message || '文件上传失败');
    return;
  }

  const data = response.data || {};
  const successFiles = data.success_files || [];
  const failedFiles = data.failed_files || [];

  if (successFiles.length > 0 && failedFiles.length === 0) {
    ElMessage.success(`上传成功：${successFiles.length} 个文件`);
  } else if (successFiles.length > 0) {
    ElMessage.warning(`部分上传成功：${successFiles.length} 个成功，${failedFiles.length} 个失败`);
    showUploadFailDetail(failedFiles);
  } else {
    ElMessage.error(`上传失败：${failedFiles.length || 1} 个文件未成功`);
    if (failedFiles.length) showUploadFailDetail(failedFiles);
  }

  currentPage.value = 1;
  fetchFiles();
};

const handleUploadError = (error, uploadFile) => {
  console.error('上传失败:', error);
  ElMessage.error(`文件 ${uploadFile?.name || ''} 上传失败，请检查后端服务`);
  fetchFiles();
};

const showUploadFailDetail = (failedFiles) => {
  ElMessageBox.alert(
    `<div style="max-height: 240px; overflow-y: auto;">
      ${failedFiles.map((file, index) => `
        <div style="margin: 8px 0;">
          <span>${index + 1}. 文件名：${file.file_name || file.name || '-'}</span><br>
          <span style="color: #f56c6c; font-size: 12px;">原因：${file.reason || '未知错误'}</span>
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

const openCreateTask = (file) => {
  selectedTaskDocument.value = file;
  taskForm.value = {
    title: `处理文献：${file.file_name}`,
    description: `基于文献 ${file.file_name} 创建的科研任务。`,
    task_type: file.status === 0 ? 'review' : 'literature',
    priority: 'medium'
  };
  taskDialogVisible.value = true;
};

const createTaskFromDocument = async () => {
  if (!selectedTaskDocument.value) return;
  taskSaving.value = true;
  try {
    await axios.post(`${API_BASE_URL}/tasks`, {
      ...taskForm.value,
      status: 'pending',
      related_document_id: selectedTaskDocument.value.id
    });
    ElMessage.success('任务已创建');
    taskDialogVisible.value = false;
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '创建任务失败');
  } finally {
    taskSaving.value = false;
  }
};

const handlePreview = (file) => {
  previewFile.value = file;
  previewUrl.value = `${API_BASE_URL}/files/${file.repository}/${file.id}/preview`;
  previewVisible.value = true;
};

const handleDownload = async (file) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/files/${file.repository}/${file.id}/download`, {
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.download = file.original_name || file.file_name;
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

const startEdit = (file) => {
  editingId.value = file.id;
  const fullName = file.file_name || '';
  const lastDotIndex = fullName.lastIndexOf('.');
  if (lastDotIndex > 0) {
    editingFileName.value = fullName.slice(0, lastDotIndex);
    editingFileExt.value = fullName.slice(lastDotIndex + 1);
  } else {
    editingFileName.value = fullName;
    editingFileExt.value = '';
  }
  editingRepoType.value = file.repository || 'ceramic_papers';
};

const saveEdit = async (file) => {
  if (editingId.value !== file.id) return;
  const baseName = editingFileName.value.trim();
  if (!baseName) {
    ElMessage.error('文件名不能为空');
    return;
  }
  if (/[\\/:*?"<>|]/.test(baseName)) {
    ElMessage.error('文件名不能包含 \\ / : * ? " < > | 这些字符');
    return;
  }
  const newFileName = editingFileExt.value ? `${baseName}.${editingFileExt.value}` : baseName;
  const isFileNameChanged = newFileName !== file.file_name;
  const isRepoChanged = editingRepoType.value !== file.repository;
  if (!isFileNameChanged && !isRepoChanged) {
    editingId.value = null;
    return;
  }

  try {
    const response = await axios.put(`${API_BASE_URL}/files/${file.repository}/${file.id}`, {
      file_name: newFileName,
      repository: editingRepoType.value
    });
    if (response.data.status === 'success') {
      ElMessage.success('文件信息修改成功');
      fetchFiles();
    } else {
      ElMessage.error(response.data.message || '文件信息修改失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '修改请求失败');
    console.error('保存文件信息失败:', error);
  } finally {
    editingId.value = null;
  }
};

const handleDelete = async (file) => {
  try {
    await ElMessageBox.confirm(`确定要删除文件 "${file.file_name}" 吗？`, '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    const response = await axios.delete(`${API_BASE_URL}/files/${file.repository}/${file.id}`);
    if (response.data.status === 'success') {
      ElMessage.success('删除成功');
      fetchFiles();
    } else {
      ElMessage.error(response.data.message || '删除失败');
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.message || '删除请求失败');
      console.error('删除失败:', error);
    }
  }
};

const formatFileSize = (bytes) => {
  if (!bytes) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

const formatTime = (time) => {
  if (!time) return '-';
  return new Date(time).toLocaleString('zh-CN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).replace(/\//g, '-');
};

const getRepositoryTagColor = (repoType) => {
  if (repoType === 'ceramic_papers') return { light: '#f0f2ff', dark: '#5b5fc7' };
  return { light: '#f4f4f5', dark: '#909399' };
};

const getFileExt = (fileName = '') => fileName.toLowerCase().split('.').pop() || '';

const isImageFile = (fileName) => ['jpg', 'jpeg', 'png'].includes(getFileExt(fileName));

const isPreviewable = (fileName) => ['pdf', 'jpg', 'jpeg', 'png'].includes(getFileExt(fileName));

const getFileIcon = (fileName = '') => {
  if (getFileExt(fileName) === 'pdf') {
    return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAACVUlEQVRoQ+2Z61HDMAxF250gG5ANyAZkA7IB2QA3gWxANkAbsAHZgGxDNuAYfU/VlcrJLVYp78/lJDudXn/6NOL3AgkCgUBcAcYBCY4AYiAO0OACGIgDaHABIeB9/w8wDphc+u1sC4yA5qA8AzwDTgEV4BvgGvAX2AdugJ9AFLgB/AW2QQtgB/gF1nAIlAEXgC/gQSkwBGwBG8B+YAtkgn0gGtAEXGAYuAbAQR/gG8BWYB3oBTpgCwgFzIDfAELgE3AZeAW8Av4EvgKXAEngDtCagB8BV4BzYN8FFoBdwCvgFhADvAc2QBHwBPAOuAX8S0g/5e0FfAJOAHfAV8AFcIXcAw4BR4BDwCFgBrgGXAb+BNYA84BTQL/kPQIeA2cB04AZ4BPwCDgCvAQ2QIfk/QW8Ao4Az4C3gDdgE/CVkH7Kuwf8e2APOA4sB04AM8A+8B9YBWaBx4CfwGkAB7gEnGSUn/K+AnsBG8A74BOwDzwFjgDdgDvwGbgG3Ac2gL3gE5Bf8j6BTeA0cAZ4ALwGXgK/gT3gNfAR+Aq8As4BR4BDwAngA7AF/Aa+Al8BN4B/gGzgA7gGDAIfAb8BfwFjgBtwG9gB7gB7wB5wA5wA3wEXgGdgF/gB3AEWAK3gE3AHeAA8BNwAjoAPwAvgA/AJeAacgI/AJ2A8sARw/4ACngFngMmgD7wDngEngBfgO9AI/gI2Q/sl5Uf+H/A+gU3gK8D9EnBwBBycAQcnwMEJcMh/D/gAh0H/cKmsjY0AAAAASUVORK5CYII=';
  }
  return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAA7ElEQVRoQ+2Z3Q2DMAxAcQN2gG7QDVgEJ2gG6AZ0g24QN2gG6AZkwyYpQh6Rkh/34T+yH/b5EdO9CAQCAQHCAbgB7IuQeAG8AJtCUg1cAfeFtCfQCeAF2JaSAXABl4V0BvQA3wBbkpIAcJ/LwlogAXgD3iXVB8AJ8B7YlgwBcC/LwnpTE8Af8C6pbiIAHOCdEL0AOoB3QLcmIADwBfwW0o14B9we0grgAfgN3JQ0AFwA74Dt2JUAYB/LwjpbEwAvgB/Bc0kKAPwBfwS3JQnAARwBvgO3JSUA+AN8D9xKAoFAINwB/gB3rD9UcYTAkAAAAABJRU5ErkJggg==';
};

const clearTransientState = () => {
  loading.value = false;
  previewVisible.value = false;
  previewFile.value = null;
  previewUrl.value = '';
  editingId.value = null;
};

onBeforeRouteLeave((to, from, next) => {
  clearTransientState();
  next();
});

onBeforeUnmount(() => {
  clearTransientState();
});
</script>

<style scoped>
.page-container {
  min-height: 100vh;
  padding: 24px;
  background: #f6f8fb;
  font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
}

.main-content {
  max-width: 1400px;
  margin: 0 auto;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 20px;
}

.content-title {
  margin: 0;
  color: #1f2d3d;
  font-size: 24px;
  font-weight: 650;
}

.content-subtitle {
  margin: 8px 0 0;
  color: #606266;
  font-size: 14px;
}

.file-count-wrapper {
  min-width: 128px;
  padding: 12px 16px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
  color: #606266;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.file-count-wrapper strong {
  color: #409eff;
  font-size: 24px;
}

.upload-section,
.file-list-section {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
}

.upload-section {
  padding: 20px;
}

.upload-card {
  min-height: 150px;
  padding: 22px;
  border: 1px dashed #b7d6ff;
  border-radius: 4px;
  background: #f8fbff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.upload-card:hover {
  border-color: #409eff;
  background: #f3f8ff;
  box-shadow: 0 6px 18px rgba(64, 158, 255, 0.12);
}

.upload-card-main {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.upload-card-icon-wrap {
  width: 58px;
  height: 58px;
  border-radius: 4px;
  background: #eaf4ff;
  color: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.upload-card h3 {
  margin: 0 0 8px;
  color: #303133;
  font-size: 18px;
}

.upload-card p {
  max-width: 680px;
  margin: 0;
  color: #606266;
  line-height: 1.7;
  font-size: 14px;
}

.card-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.hidden-upload {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
}

.file-list-section {
  margin-top: 20px;
  padding: 20px 24px;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.list-title {
  margin: 0;
  color: #303133;
  font-size: 17px;
}

.list-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.list-actions .el-input {
  width: 320px;
}

.sort-select {
  width: 120px;
}

.category-select {
  width: 150px;
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

.edit-mode-extension {
  margin-left: 5px;
  color: #909399;
  font-size: 12px;
  user-select: none;
}

.es-code-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.es-code-text {
  max-width: 112px;
  overflow: hidden;
  color: #303133;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.es-code-bind-icon {
  color: #409eff;
  cursor: help;
}

.pagination-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 20px;
  padding-top: 16px;
}

.total-count {
  padding: 8px 14px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #f7f8fa;
  color: #606266;
  font-size: 14px;
}

.preview-frame {
  height: calc(100vh - 150px);
  border: none;
}

.preview-image {
  width: 100%;
  height: auto;
  object-fit: contain;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.full-width {
  width: 100%;
}

:deep(.el-table th.el-table__cell) {
  background-color: #f7f8fa !important;
  color: #606266;
  font-weight: 500;
}

:deep(.el-table td.el-table__cell),
:deep(.el-table th.el-table__cell) {
  border-bottom: 1px solid #f0f2f5;
}

:deep(.el-input__wrapper),
:deep(.el-button),
:deep(.el-select__wrapper) {
  border-radius: 4px;
}

.el-button.is-link {
  margin: 0 4px;
  font-size: 13px;
}

@media (max-width: 980px) {
  .content-header,
  .upload-card,
  .list-header,
  .pagination-wrapper {
    align-items: stretch;
    flex-direction: column;
  }

  .list-actions,
  .card-actions {
    justify-content: flex-start;
  }

  .list-actions .el-input,
  .sort-select,
  .category-select {
    width: 100%;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
