import axios from 'axios'


const assistantClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 90000
})


export const assistantAPI = {
  async chat(payload) {
    const response = await assistantClient.post('/api/assistant/chat', payload)
    return response.data
  },
  async getGraphScopes() {
    const response = await assistantClient.get('/api/graph/knowledge-graph-options')
    return response.data
  },
  async createTask(payload) {
    const response = await assistantClient.post('/pdf/tasks', payload)
    return response.data
  }
}
