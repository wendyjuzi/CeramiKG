/**
 * 前端JSON处理工具 - 异常12修复
 * 提供安全的JSON解析和数据处理功能
 */

/**
 * 安全的JSON解析
 * @param {string} jsonStr - JSON字符串
 * @returns {Object} - 解析结果 {success: boolean, data: any, error: string}
 */
export function safeJsonParse(jsonStr) {
  if (!jsonStr || typeof jsonStr !== 'string') {
    return {
      success: false,
      data: null,
      error: '输入不是有效的字符串'
    }
  }

  try {
    const parsed = JSON.parse(jsonStr)
    return {
      success: true,
      data: parsed,
      error: null
    }
  } catch (error) {
    // 尝试修复常见的JSON格式问题
    try {
      const repaired = repairJsonString(jsonStr)
      const parsed = JSON.parse(repaired)
      return {
        success: true,
        data: parsed,
        error: null,
        repaired: true
      }
    } catch (repairError) {
      return {
        success: false,
        data: null,
        error: `JSON解析失败: ${error.message}`,
        originalError: error,
        repairError: repairError
      }
    }
  }
}

/**
 * 修复损坏的JSON字符串
 * @param {string} jsonStr - 损坏的JSON字符串
 * @returns {string} - 修复后的JSON字符串
 */
function repairJsonString(jsonStr) {
  let repaired = jsonStr.trim()

  // 修复单引号为双引号
  repaired = repaired.replace(/'/g, '"')
  
  // 修复Python的None/True/False
  repaired = repaired.replace(/\bNone\b/g, 'null')
  repaired = repaired.replace(/\bTrue\b/g, 'true')
  repaired = repaired.replace(/\bFalse\b/g, 'false')
  
  // 移除尾随逗号
  repaired = repaired.replace(/,(\s*[}\]])/g, '$1')
  
  // 修复未加引号的对象键
  repaired = repaired.replace(/([{,]\s*)(\w+)(\s*:)/g, '$1"$2"$3')

  return repaired
}

/**
 * 安全提取文档内容
 * @param {Object} document - 文档对象
 * @returns {string} - 提取的文本内容
 */
export function safeExtractDocumentContent(document) {
  if (!document) {
    return '暂无内容'
  }

  try {
    // 方法1: 优先使用json_data
    if (document.json_data) {
      // 如果json_data是对象且有text字段
      if (typeof document.json_data === 'object' && document.json_data.text) {
        return truncateText(document.json_data.text, 800)
      }
      
      // 如果json_data是数组，提取text字段
      if (Array.isArray(document.json_data)) {
        const textParts = []
        for (const item of document.json_data) {
          if (item && typeof item === 'object' && item.text) {
            textParts.push(item.text.trim())
          }
        }
        if (textParts.length > 0) {
          return truncateText(textParts.join(' '), 800)
        }
      }
      
      // 如果json_data是字符串，尝试解析
      if (typeof document.json_data === 'string') {
        const parseResult = safeJsonParse(document.json_data)
        if (parseResult.success && parseResult.data) {
          if (parseResult.data.text) {
            return truncateText(parseResult.data.text, 800)
          }
          if (Array.isArray(parseResult.data)) {
            const textParts = parseResult.data
              .filter(item => item && item.text)
              .map(item => item.text.trim())
            if (textParts.length > 0) {
              return truncateText(textParts.join(' '), 800)
            }
          }
        }
      }
    }

    // 方法2: 使用content字段
    if (document.content) {
      // 如果content是字符串，尝试解析
      if (typeof document.content === 'string') {
        const parseResult = safeJsonParse(document.content)
        if (parseResult.success && parseResult.data && parseResult.data.text) {
          return truncateText(parseResult.data.text, 800)
        } else {
          // 直接使用content内容
          return truncateText(document.content, 800)
        }
      }
      
      // 如果content是对象
      if (typeof document.content === 'object' && document.content.text) {
        return truncateText(document.content.text, 800)
      }
    }

    return '暂无内容预览'

  } catch (error) {
    console.warn('提取文档内容时出错:', error)
    return '内容提取失败'
  }
}

/**
 * 截断文本到指定长度
 * @param {string} text - 原始文本
 * @param {number} maxLength - 最大长度
 * @returns {string} - 截断后的文本
 */
function truncateText(text, maxLength = 800) {
  if (!text || typeof text !== 'string') {
    return ''
  }
  
  if (text.length <= maxLength) {
    return text
  }
  
  return text.slice(0, maxLength) + '...'
}

/**
 * 安全的axios请求拦截器配置
 */
export function setupAxiosInterceptors(axiosInstance) {
  // 请求拦截器 - 确保发送的数据是有效JSON
  axiosInstance.interceptors.request.use(
    config => {
      if (config.data && typeof config.data === 'object') {
        try {
          // 确保数据可以序列化
          JSON.stringify(config.data)
        } catch (error) {
          console.error('请求数据JSON序列化失败:', error)
          throw new Error('请求数据格式错误')
        }
      }
      return config
    },
    error => {
      return Promise.reject(error)
    }
  )

  // 响应拦截器 - 处理响应中的JSON问题
  axiosInstance.interceptors.response.use(
    response => {
      // 检查响应数据格式
      if (response.data && typeof response.data === 'string') {
        const parseResult = safeJsonParse(response.data)
        if (parseResult.success) {
          response.data = parseResult.data
          if (parseResult.repaired) {
            console.warn('响应JSON已自动修复')
          }
        }
      }
      return response
    },
    error => {
      // 增强错误信息
      if (error.response && error.response.data) {
        if (typeof error.response.data === 'string') {
          try {
            error.response.data = JSON.parse(error.response.data)
          } catch (parseError) {
            console.warn('错误响应JSON解析失败:', parseError)
          }
        }
      }
      return Promise.reject(error)
    }
  )
}

/**
 * 验证JSON数据的完整性
 * @param {any} data - 要验证的数据
 * @returns {Object} - 验证结果
 */
export function validateJsonData(data) {
  const result = {
    isValid: false,
    issues: [],
    suggestions: []
  }

  try {
    // 尝试序列化和反序列化
    const serialized = JSON.stringify(data)
    JSON.parse(serialized)
    result.isValid = true
  } catch (error) {
    result.issues.push(`JSON序列化失败: ${error.message}`)
    result.suggestions.push('检查数据中是否包含循环引用或不支持的数据类型')
  }

  // 检查特定的数据结构问题
  if (typeof data === 'object' && data !== null) {
    // 检查是否有undefined值
    const checkForUndefined = (obj, path = '') => {
      for (const [key, value] of Object.entries(obj)) {
        const currentPath = path ? `${path}.${key}` : key
        if (value === undefined) {
          result.issues.push(`发现undefined值: ${currentPath}`)
          result.suggestions.push(`将${currentPath}的undefined值替换为null或删除该字段`)
        } else if (typeof value === 'object' && value !== null) {
          checkForUndefined(value, currentPath)
        }
      }
    }
    
    checkForUndefined(data)
  }

  return result
}