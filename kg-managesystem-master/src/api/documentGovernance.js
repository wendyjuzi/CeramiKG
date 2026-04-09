/**
 * 文档治理API接口
 * 与后端 /api/document-governance 对接
 */
import axios from './axios'

export const documentGovernanceAPI = {
  /**
   * 获取文档列表
   * @param {Object} params - 查询参数
   * @param {number} [params.status] - 状态筛选：0=待审核, 1=已审核, 2=已删除
   * @param {number} [params.limit] - 每页数量
   * @param {number} [params.offset] - 偏移量
   */
  getDocuments(params = {}) {
    return axios.get('/api/document-governance/documents', { params })
  },

  /**
   * 获取文档总数
   * @param {Object} params - 查询参数
   * @param {number} [params.status] - 状态筛选
   */
  getDocumentsCount(params = {}) {
    return axios.get('/api/document-governance/documents/count', { params })
  },

  /**
   * 创建新文档
   * @param {Object} documentData - 文档数据
   */
  createDocument(documentData) {
    return axios.post('/api/document-governance/documents', documentData)
  },

  /**
   * 更新文档信息
   * @param {number} documentId - 文档ID
   * @param {Object} updateData - 更新数据
   */
  updateDocument(documentId, updateData) {
    return axios.put(`/api/document-governance/documents/${documentId}`, updateData)
  },

  /**
   * 删除文档（逻辑删除）
   * @param {number} documentId - 文档ID
   * @param {boolean} [forceDelete=false] - 是否强制删除（物理删除）
   */
  deleteDocument(documentId, forceDelete = false) {
    const params = forceDelete ? { force_delete: true } : {}
    return axios.delete(`/api/document-governance/documents/${documentId}`, { params })
  },

  /**
   * 获取文档审核详情
   * @param {number} documentId - 文档ID
   */
  getDocumentForReview(documentId) {
    return axios.get(`/api/document-governance/documents/${documentId}/review`)
  },

  /**
   * 保存审核修改
   * @param {number} documentId - 文档ID
   * @param {Object} reviewData - 审核数据
   * @param {number} reviewData.document_id - 文档ID
   * @param {Array} reviewData.json_data - 修改后的JSON数据
   */
  saveReviewChanges(documentId, reviewData) {
    return axios.post(`/api/document-governance/documents/${documentId}/review/save`, reviewData)
  },

  /**
   * 完成文档审核
   * @param {number} documentId - 文档ID
   * @param {Object} completeData - 完成审核数据
   * @param {number} completeData.document_id - 文档ID
   * @param {Array} completeData.json_data - 最终审核后的JSON数据
   */
  completeReview(documentId, completeData) {
    return axios.post(`/api/document-governance/documents/${documentId}/review/complete`, completeData)
  },

  /**
   * 撤销审核修改
   * @param {number} documentId - 文档ID
   */
  undoReviewChanges(documentId) {
    return axios.post(`/api/document-governance/documents/${documentId}/review/undo`)
  },

  /**
   * 健康检查
   */
  healthCheck() {
    return axios.get('/api/document-governance/health')
  }
}

// 默认导出
export default documentGovernanceAPI