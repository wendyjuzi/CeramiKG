import axios from 'axios'
import { demoChat, demoCreateTask, demoGraphScopes } from './assistantDemo'


const assistantClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 90000
})

const demoMode = import.meta.env.DEV
  ? new URLSearchParams(window.location.search).get('demo')
  : null
const liveDemoEnabled = import.meta.env.DEV && demoMode === 'live'
const demoEnabled = liveDemoEnabled || (import.meta.env.DEV && (
  import.meta.env.VITE_ASSISTANT_DEMO === 'true'
  || demoMode === '1'
))

async function liveDemoChat(payload) {
  const [demoResult, liveResponse] = await Promise.all([
    demoChat(payload),
    assistantClient.post('/__demo/qwen/chat', payload)
  ])
  return {
    ...demoResult,
    answer: liveResponse.data.answer,
    warnings: ['文献与图谱证据来自本地演示数据，回答由真实千问 API 生成。'],
    metadata: {
      ...demoResult.metadata,
      ...liveResponse.data.metadata
    }
  }
}


export const assistantAPI = {
  async chat(payload) {
    if (liveDemoEnabled) return liveDemoChat(payload)
    if (demoEnabled) return demoChat(payload)
    const response = await assistantClient.post('/api/assistant/chat', payload)
    return response.data
  },
  async getGraphScopes() {
    if (demoEnabled) return demoGraphScopes()
    const response = await assistantClient.get('/api/graph/knowledge-graph-options')
    return response.data
  },
  async createTask(payload) {
    if (demoEnabled) return demoCreateTask(payload)
    const response = await assistantClient.post('/pdf/tasks', payload)
    return response.data
  }
}
