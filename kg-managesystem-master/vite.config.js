import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

const pdfProxyTarget = process.env.VITE_PDF_PROXY_TARGET || 'http://127.0.0.1:8001'
const workspaceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function readLocalEnv() {
  const envPath = path.join(workspaceRoot, '.env')
  if (!fs.existsSync(envPath)) return {}

  return fs.readFileSync(envPath, 'utf8')
    .split(/\r?\n/)
    .reduce((values, line) => {
      const normalized = line.trim()
      if (!normalized || normalized.startsWith('#')) return values
      const separator = normalized.indexOf('=')
      if (separator <= 0) return values
      values[normalized.slice(0, separator).trim()] = normalized.slice(separator + 1).trim()
      return values
    }, {})
}

function sendJson(response, statusCode, body) {
  response.statusCode = statusCode
  response.setHeader('Content-Type', 'application/json; charset=utf-8')
  response.end(JSON.stringify(body))
}

async function readJsonBody(request) {
  const chunks = []
  for await (const chunk of request) chunks.push(chunk)
  const raw = Buffer.concat(chunks).toString('utf8')
  return raw ? JSON.parse(raw) : {}
}

function localQwenDemoPlugin() {
  return {
    name: 'local-qwen-demo-proxy',
    configureServer(server) {
      server.middlewares.use('/__demo/qwen/chat', async (request, response, next) => {
        if (request.method !== 'POST') {
          sendJson(response, 405, { detail: 'Method not allowed' })
          return
        }

        try {
          const payload = await readJsonBody(request)
          const question = String(payload.question || '').trim()
          if (!question) {
            sendJson(response, 400, { detail: '问题不能为空' })
            return
          }

          const config = { ...readLocalEnv(), ...process.env }
          const apiKey = config.QWEN_API_KEY
          const baseUrl = String(config.QWEN_API_BASE || '').replace(/\/$/, '')
          if (!apiKey || !baseUrl) {
            sendJson(response, 503, { detail: '本地 .env 未配置 QWEN_API_KEY 或 QWEN_API_BASE' })
            return
          }

          const history = Array.isArray(payload.history)
            ? payload.history
              .filter(item => ['user', 'assistant'].includes(item?.role) && item?.content)
              .slice(-6)
              .map(item => ({ role: item.role, content: String(item.content) }))
            : []
          const systemPrompt = [
            '你是 CeramiKG 陶瓷材料知识助手，正在进行本地真实模型演示。',
            '优先依据以下演示证据回答，结论后用 [文献1]、[文献2] 或 [图谱1] 标注。',
            '[文献1] 烧结温度提高通常有利于致密化，但可能促进晶粒长大；保温时间和添加剂需要协同控制。',
            '[文献2] 粉体粒径、成型密度和烧结制度共同影响孔隙率与力学性能。',
            '[图谱1] 烧结温度影响致密化程度；保温时间促进晶粒长大。',
            '请用中文回答，保持专业、简洁，并明确说明证据不足之处。'
          ].join('\n')

          const upstream = await fetch(`${baseUrl}/chat/completions`, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${apiKey}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              model: config.MODEL_NAME || 'qwen-plus',
              messages: [
                { role: 'system', content: systemPrompt },
                ...history,
                { role: 'user', content: question }
              ],
              temperature: 0.2
            })
          })
          const data = await upstream.json()
          if (!upstream.ok) {
            sendJson(response, upstream.status, { detail: data?.error?.message || '千问 API 请求失败' })
            return
          }

          const answer = data?.choices?.[0]?.message?.content?.trim()
          if (!answer) {
            sendJson(response, 502, { detail: '千问 API 返回了空答案' })
            return
          }

          sendJson(response, 200, {
            answer,
            metadata: {
              generated_by: 'llm',
              model: config.MODEL_NAME || 'qwen-plus'
            }
          })
        } catch (error) {
          next(error)
        }
      })
    }
  }
}

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
  plugins: command === 'serve' ? [vue(), localQwenDemoPlugin()] : [vue()],
  resolve: {
    alias: {
      "@": path.resolve("./src"),
    },
  },
  publicDir: "./public",
  server: {
    proxy: {
      '/api': {
        target: pdfProxyTarget,
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('Sending Request to the Target:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
          });
        },
      }
      ,
      '/pdf': {
        target: pdfProxyTarget,
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/pdf/, ''),
      },
      '/files': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
}))
