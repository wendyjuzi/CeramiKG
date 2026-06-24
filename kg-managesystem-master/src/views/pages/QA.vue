<template>
  <div class="assistant-page">
    <aside class="session-panel">
      <div class="session-header">
        <span>对话记录</span>
        <div class="session-actions">
          <el-tooltip content="导出当前对话" placement="top">
            <el-button :icon="Download" circle text :disabled="!messages.length" @click="exportSession" />
          </el-tooltip>
          <el-tooltip content="新建对话" placement="top">
            <el-button :icon="Plus" circle text @click="createSession" />
          </el-tooltip>
        </div>
      </div>

      <div class="session-list">
        <button
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === activeSessionId }"
          @click="activeSessionId = session.id"
        >
          <ChatDotRound class="session-icon" />
          <span class="session-copy">
            <span class="session-title">{{ session.title }}</span>
            <span class="session-time">{{ formatTime(session.updatedAt) }}</span>
          </span>
          <el-button
            class="session-delete"
            :icon="Delete"
            circle
            text
            @click.stop="removeSession(session.id)"
          />
        </button>
      </div>
    </aside>

    <section class="assistant-workspace">
      <header class="workspace-header">
        <div>
          <h1>智能交互</h1>
          <div class="service-status">
            <span><i class="status-dot literature"></i>文献检索</span>
            <span><i class="status-dot graph"></i>知识图谱</span>
            <span><i class="status-dot model"></i>大模型</span>
          </div>
        </div>

        <div class="header-controls">
          <el-select
            v-model="selectedDocumentIds"
            class="scope-select"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            :loading="scopeLoading"
            placeholder="全部文献与图谱"
          >
            <el-option
              v-for="scope in graphScopes"
              :key="scope.document_id"
              :label="scope.display_name"
              :value="scope.document_id"
            >
              <div class="scope-option">
                <span>{{ scope.display_name }}</span>
                <small>{{ scope.table_count || 0 }} 项</small>
              </div>
            </el-option>
          </el-select>

          <el-radio-group v-model="mode" size="small">
            <el-radio-button label="hybrid">综合</el-radio-button>
            <el-radio-button label="literature">文献</el-radio-button>
            <el-radio-button label="graph">图谱</el-radio-button>
          </el-radio-group>

          <el-tooltip content="检索参数" placement="top">
            <el-button :icon="Setting" circle text @click="settingsVisible = true" />
          </el-tooltip>
          <el-tooltip content="对比已选回答" placement="top">
            <el-button :icon="DataAnalysis" circle text :disabled="!comparisonReady" @click="openComparison" />
          </el-tooltip>
        </div>
      </header>

      <div class="workspace-body">
        <main class="chat-panel">
          <div ref="messageListRef" class="message-list">
            <div v-if="messages.length === 0" class="empty-state">
              <div class="assistant-mark"><Search /></div>
              <h2>从陶瓷材料知识中寻找答案</h2>
              <div class="prompt-grid">
                <button v-for="prompt in starterPrompts" :key="prompt" @click="usePrompt(prompt)">
                  {{ prompt }}
                </button>
              </div>
            </div>

            <article
              v-for="message in messages"
              :key="message.id"
              class="message-row"
              :class="message.role"
              @click="selectEvidence(message)"
            >
              <div class="message-avatar">
                <User v-if="message.role === 'user'" />
                <ChatDotRound v-else />
              </div>
              <div class="message-content">
                <div class="message-bubble">{{ message.content }}</div>

                <div v-if="message.warnings?.length" class="warning-list">
                  <span v-for="warning in message.warnings" :key="warning">{{ warning }}</span>
                </div>

                <div v-if="message.role === 'assistant'" class="message-meta">
                  <button v-if="message.sources?.length" @click.stop="openEvidence(message, 'literature')">
                    <Document />{{ message.sources.length }} 篇文献
                  </button>
                  <button v-if="message.graphEvidence?.length" @click.stop="openEvidence(message, 'graph')">
                    <Connection />{{ message.graphEvidence.length }} 条关系
                  </button>
                  <el-tooltip content="创建问答任务" placement="top">
                    <el-button :icon="Tickets" circle text @click.stop="openTaskDialog(message)" />
                  </el-tooltip>
                  <el-tooltip content="回答有帮助" placement="top">
                    <el-button
                      :icon="CircleCheck"
                      circle
                      text
                      class="feedback-button"
                      :class="{ active: message.feedback === 'helpful' }"
                      @click.stop="toggleHelpfulFeedback(message)"
                    />
                  </el-tooltip>
                  <el-tooltip content="需要核验" placement="top">
                    <el-button
                      :icon="WarningFilled"
                      circle
                      text
                      class="feedback-button"
                      :class="{ review: message.feedback === 'needs_review' }"
                      @click.stop="openFeedbackDialog(message)"
                    />
                  </el-tooltip>
                  <el-tooltip content="选择用于对比" placement="top">
                    <el-button
                      :icon="ScaleToOriginal"
                      circle
                      text
                      class="compare-button"
                      :class="{ active: comparisonMessageIds.includes(message.id) }"
                      @click.stop="toggleComparison(message)"
                    />
                  </el-tooltip>
                  <el-tooltip content="生成阅读或实验计划" placement="top">
                    <el-button :icon="Operation" circle text @click.stop="openPlanDialog(message)" />
                  </el-tooltip>
                  <span v-if="message.scopeLabel" class="scope-meta">{{ message.scopeLabel }}</span>
                  <span>{{ message.metadata?.generated_by === 'llm' ? message.metadata?.model : message.metadata?.generated_by === 'demo' ? '本地演示' : '检索结果' }}</span>
                </div>

                <div
                  v-if="message.role === 'assistant' && isLatestAssistant(message) && message.suggestedQuestions?.length"
                  class="suggestions"
                >
                  <button
                    v-for="suggestion in message.suggestedQuestions"
                    :key="suggestion"
                    @click.stop="usePrompt(suggestion)"
                  >
                    {{ suggestion }}
                  </button>
                </div>
              </div>
            </article>

            <article v-if="sending" class="message-row assistant">
              <div class="message-avatar"><ChatDotRound /></div>
              <div class="message-content">
                <div class="message-bubble thinking">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </article>
          </div>

          <div class="composer">
            <el-input
              v-model="draft"
              type="textarea"
              resize="none"
              :rows="3"
              maxlength="2000"
              placeholder="输入关于陶瓷材料、工艺或文献的问题"
              @keydown="handleComposerKeydown"
            />
            <div class="composer-footer">
              <span>Enter 发送，Shift + Enter 换行</span>
              <el-tooltip content="发送问题" placement="top">
                <el-button
                  type="primary"
                  :icon="Promotion"
                  circle
                  :loading="sending"
                  :disabled="!draft.trim()"
                  @click="sendMessage"
                />
              </el-tooltip>
            </div>
          </div>
        </main>

        <aside class="evidence-panel">
          <div class="evidence-header">
            <span>回答依据</span>
            <el-tooltip content="显示最近一条回答的依据" placement="top">
              <el-button :icon="Refresh" circle text @click="selectLatestEvidence" />
            </el-tooltip>
          </div>

          <el-tabs v-model="evidenceTab" stretch>
            <el-tab-pane name="literature">
              <template #label>文献 {{ activeEvidence.sources.length }}</template>
              <div v-if="activeEvidence.sources.length" class="evidence-list">
                <div v-for="source in activeEvidence.sources" :key="source.citation" class="evidence-item">
                  <div class="evidence-title">
                    <span>{{ source.citation }}</span>
                    <strong>{{ source.title }}</strong>
                  </div>
                  <p>{{ source.excerpt }}</p>
                  <div class="evidence-info">
                    <span v-if="source.page_num">第 {{ source.page_num }} 页</span>
                    <span v-if="source.score != null">相关度 {{ formatScore(source.score) }}</span>
                    <el-tooltip content="预览文献" placement="top">
                      <el-button
                        :icon="View"
                        circle
                        text
                        size="small"
                        :disabled="!source.preview_path"
                        @click="openSourcePreview(source)"
                      />
                    </el-tooltip>
                  </div>
                </div>
              </div>
              <el-empty v-else :image-size="72" description="暂无文献依据" />
            </el-tab-pane>

            <el-tab-pane name="graph">
              <template #label>图谱 {{ activeEvidence.graphEvidence.length }}</template>
              <div v-if="activeEvidence.graphEvidence.length" class="evidence-list">
                <div
                  v-for="item in activeEvidence.graphEvidence"
                  :key="`${item.citation}-${item.head}-${item.tail}`"
                  class="evidence-item graph-fact"
                >
                  <span class="citation">{{ item.citation }}</span>
                  <div class="fact-node">{{ item.head }}</div>
                  <div v-if="item.tail" class="fact-relation">{{ item.relation }}</div>
                  <div v-if="item.tail" class="fact-node tail">{{ item.tail }}</div>
                  <p v-if="item.evidence_text">{{ item.evidence_text }}</p>
                  <div class="evidence-info graph-source">
                    <span v-if="item.paper_title || item.document_id">{{ item.paper_title || `图谱范围：${item.document_id}` }}</span>
                    <div class="graph-actions">
                      <el-tooltip v-if="item.document_id" content="在知识图谱中定位" placement="top">
                        <el-button
                          :icon="Connection"
                          circle
                          text
                          size="small"
                          @click="openGraphEvidence(item)"
                        />
                      </el-tooltip>
                      <el-tooltip content="围绕此关系追问" placement="top">
                        <el-button :icon="Promotion" circle text size="small" @click="askAboutRelation(item)" />
                      </el-tooltip>
                    </div>
                  </div>
                </div>
              </div>
              <el-empty v-else :image-size="72" description="暂无图谱依据" />
            </el-tab-pane>
          </el-tabs>
        </aside>
      </div>
    </section>

    <el-dialog
      v-model="previewVisible"
      :title="`文献预览：${previewSource?.title || ''}`"
      width="min(1100px, 92vw)"
      destroy-on-close
    >
      <iframe v-if="previewUrl" :src="previewUrl" class="preview-frame" title="文献预览" />
      <el-empty v-else description="该文献暂不可预览" />
    </el-dialog>

    <el-dialog v-model="taskDialogVisible" title="创建问答任务" width="min(560px, 92vw)" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="任务标题">
          <el-input v-model="taskDraft.title" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="taskDraft.priority" style="width: 100%">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联文献（可选）">
          <el-select
            v-model="taskDraft.relatedDocumentId"
            clearable
            placeholder="未找到可关联的已登记文献"
            style="width: 100%"
          >
            <el-option
              v-for="source in taskSources"
              :key="source.document_id"
              :label="source.title"
              :value="source.document_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="任务说明">
          <el-input v-model="taskDraft.description" type="textarea" :rows="8" maxlength="5000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="taskCreating" @click="createTask">创建任务</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="feedbackDialogVisible" title="提交核验反馈" width="min(520px, 92vw)" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="需要核验的内容（可选）">
          <el-input
            v-model="feedbackNote"
            type="textarea"
            :rows="5"
            maxlength="1500"
            show-word-limit
            placeholder="例如：结论与原文不一致、引用范围不足或需要补充实验条件"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="feedbackDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="feedbackSubmitting" @click="createFeedbackTask">创建核验任务</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="settingsVisible" title="检索参数" width="min(480px, 92vw)">
      <el-form label-position="top">
        <el-form-item label="文献检索数量">
          <el-slider v-model="retrievalTopK" :min="1" :max="10" show-input />
        </el-form-item>
        <el-form-item label="图谱关系数量">
          <el-slider v-model="retrievalGraphLimit" :min="1" :max="20" show-input />
        </el-form-item>
      </el-form>
    </el-dialog>

    <el-dialog v-model="comparisonVisible" title="回答对比" width="min(1180px, 94vw)" destroy-on-close>
      <div class="comparison-grid">
        <section v-for="(message, index) in comparisonMessages" :key="message.id" class="comparison-column">
          <div class="comparison-heading">
            <span>回答 {{ index + 1 }}</span>
            <small>{{ questionForMessage(message) }}</small>
          </div>
          <div class="comparison-answer">{{ message.content }}</div>
          <div class="comparison-meta">
            <span>{{ message.scopeLabel || '未记录范围' }}</span>
            <span>{{ message.metadata?.mode || '未记录模式' }}</span>
            <span>文献 Top {{ message.retrievalSettings?.topK || 5 }}</span>
            <span>图谱 {{ message.retrievalSettings?.graphLimit || 8 }} 条</span>
          </div>
          <div v-if="message.sources?.length" class="comparison-evidence">
            <strong>文献依据</strong>
            <ul>
              <li v-for="source in message.sources" :key="source.citation">
                {{ source.citation }} {{ source.title }}
              </li>
            </ul>
          </div>
          <div v-if="message.graphEvidence?.length" class="comparison-evidence">
            <strong>图谱依据</strong>
            <ul>
              <li v-for="item in message.graphEvidence" :key="`${item.citation}-${item.head}-${item.tail}`">
                {{ item.citation }} {{ item.head }}{{ item.tail ? ` -[${item.relation}]-> ${item.tail}` : '' }}
              </li>
            </ul>
          </div>
        </section>
      </div>
      <template #footer>
        <el-button @click="clearComparison">清除选择</el-button>
        <el-button type="primary" @click="comparisonVisible = false">完成</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="planDialogVisible" title="自动计划" width="min(680px, 94vw)" destroy-on-close>
      <el-radio-group v-model="planType" size="small" class="plan-type-switch">
        <el-radio-button label="reading">阅读计划</el-radio-button>
        <el-radio-button label="experiment">实验验证计划</el-radio-button>
      </el-radio-group>
      <el-steps direction="vertical" :active="0" class="plan-steps">
        <el-step
          v-for="(step, index) in generatedPlan.steps"
          :key="`${planType}-${index}`"
          :title="step.title"
          :description="step.description"
        />
      </el-steps>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="planTaskCreating" @click="createPlanTask">创建计划任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ChatDotRound,
  CircleCheck,
  Connection,
  DataAnalysis,
  Delete,
  Download,
  Document,
  Operation,
  Plus,
  Promotion,
  Refresh,
  ScaleToOriginal,
  Search,
  Setting,
  Tickets,
  User,
  View,
  WarningFilled
} from '@element-plus/icons-vue'
import { assistantAPI } from '@/api/assistant'


const STORAGE_KEY = 'ceramikg-assistant-sessions-v1'
const mode = ref('hybrid')
const draft = ref('')
const sending = ref(false)
const sessions = ref([])
const activeSessionId = ref('')
const selectedMessageId = ref('')
const evidenceTab = ref('literature')
const messageListRef = ref(null)
const graphScopes = ref([])
const scopeLoading = ref(false)
const previewVisible = ref(false)
const previewSource = ref(null)
const taskDialogVisible = ref(false)
const taskCreating = ref(false)
const taskSources = ref([])
const taskDraft = ref({
  title: '',
  description: '',
  priority: 'medium',
  relatedDocumentId: null
})
const feedbackDialogVisible = ref(false)
const feedbackSubmitting = ref(false)
const feedbackMessage = ref(null)
const feedbackNote = ref('')
const settingsVisible = ref(false)
const comparisonMessageIds = ref([])
const comparisonVisible = ref(false)
const planDialogVisible = ref(false)
const planTaskCreating = ref(false)
const planMessage = ref(null)
const planType = ref('reading')
const router = useRouter()

const DEFAULT_RETRIEVAL_SETTINGS = {
  topK: 5,
  graphLimit: 8
}

const starterPrompts = [
  '氧化铝陶瓷的主要烧结影响因素有哪些？',
  '请总结当前文献中的陶瓷增韧方法',
  '知识图谱中与烧结温度相关的实体有哪些？',
  '比较不同陶瓷材料的力学性能研究结论'
]

const activeSession = computed(() => (
  sessions.value.find(item => item.id === activeSessionId.value) || sessions.value[0]
))

const messages = computed(() => activeSession.value?.messages || [])

function updateRetrievalSetting(key, value) {
  if (!activeSession.value) return
  activeSession.value.retrievalSettings = {
    ...DEFAULT_RETRIEVAL_SETTINGS,
    ...(activeSession.value.retrievalSettings || {}),
    [key]: Number(value)
  }
  activeSession.value.updatedAt = Date.now()
}

const retrievalTopK = computed({
  get: () => activeSession.value?.retrievalSettings?.topK || DEFAULT_RETRIEVAL_SETTINGS.topK,
  set: value => updateRetrievalSetting('topK', value)
})

const retrievalGraphLimit = computed({
  get: () => activeSession.value?.retrievalSettings?.graphLimit || DEFAULT_RETRIEVAL_SETTINGS.graphLimit,
  set: value => updateRetrievalSetting('graphLimit', value)
})

const selectedDocumentIds = computed({
  get: () => activeSession.value?.documentIds || [],
  set: value => {
    if (activeSession.value) activeSession.value.documentIds = value
  }
})

const selectedScopeLabel = computed(() => {
  const ids = selectedDocumentIds.value
  if (!ids.length) return '全部文献与图谱'
  const names = graphScopes.value
    .filter(scope => ids.includes(scope.document_id))
    .map(scope => scope.display_name)
  if (names.length === 1) return names[0]
  return `${names.length || ids.length} 篇图谱`
})

const selectedDocumentNames = computed(() => {
  const ids = selectedDocumentIds.value
  if (!ids.length) return []
  return graphScopes.value
    .filter(scope => ids.includes(scope.document_id))
    .map(scope => scope.display_name)
    .filter(Boolean)
})

const selectedEvidenceMessage = computed(() => (
  messages.value.find(item => item.id === selectedMessageId.value && item.role === 'assistant')
  || [...messages.value].reverse().find(item => item.role === 'assistant')
  || null
))

const activeEvidence = computed(() => ({
  sources: selectedEvidenceMessage.value?.sources || [],
  graphEvidence: selectedEvidenceMessage.value?.graphEvidence || []
}))

const comparisonMessages = computed(() => comparisonMessageIds.value
  .map(messageId => messages.value.find(item => item.id === messageId && item.role === 'assistant'))
  .filter(Boolean))

const comparisonReady = computed(() => comparisonMessages.value.length === 2)

const generatedPlan = computed(() => buildGeneratedPlan(planMessage.value, planType.value))

const previewUrl = computed(() => (
  previewSource.value?.preview_path ? `/pdf${previewSource.value.preview_path}` : ''
))

function newId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function createSession() {
  const session = {
    id: newId('session'),
    title: '新对话',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    documentIds: [],
    retrievalSettings: { ...DEFAULT_RETRIEVAL_SETTINGS },
    messages: []
  }
  sessions.value.unshift(session)
  activeSessionId.value = session.id
  selectedMessageId.value = ''
  draft.value = ''
}

async function removeSession(sessionId) {
  if (sessions.value.length === 1 && sessions.value[0].messages.length === 0) return
  try {
    await ElMessageBox.confirm('删除这条对话记录？', '删除对话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    sessions.value = sessions.value.filter(item => item.id !== sessionId)
    if (!sessions.value.length) createSession()
    if (activeSessionId.value === sessionId) activeSessionId.value = sessions.value[0].id
  } catch {
    // User cancelled.
  }
}

function usePrompt(prompt) {
  draft.value = prompt
  nextTick(() => sendMessage())
}

async function sendMessage() {
  const question = draft.value.trim()
  if (!question || sending.value || !activeSession.value) return

  const history = messages.value.slice(-8).map(item => ({
    role: item.role,
    content: item.content
  }))
  activeSession.value.messages.push({
    id: newId('message'),
    role: 'user',
    content: question,
    createdAt: Date.now()
  })
  if (activeSession.value.title === '新对话') {
    activeSession.value.title = question.length > 20 ? `${question.slice(0, 20)}…` : question
  }
  activeSession.value.updatedAt = Date.now()
  draft.value = ''
  sending.value = true
  await scrollToBottom()

  try {
    const result = await assistantAPI.chat({
      question,
      history,
      mode: mode.value,
      document_ids: selectedDocumentIds.value,
      document_names: selectedDocumentNames.value,
      top_k: retrievalTopK.value,
      graph_limit: retrievalGraphLimit.value
    })
    const assistantMessage = {
      id: newId('message'),
      role: 'assistant',
      content: result.answer,
      sources: result.sources || [],
      graphEvidence: result.graph_evidence || [],
      suggestedQuestions: result.suggested_questions || [],
      warnings: result.warnings || [],
      metadata: result.metadata || {},
      scopeLabel: selectedScopeLabel.value,
      retrievalSettings: {
        topK: retrievalTopK.value,
        graphLimit: retrievalGraphLimit.value
      },
      createdAt: Date.now()
    }
    activeSession.value.messages.push(assistantMessage)
    activeSession.value.updatedAt = Date.now()
    selectedMessageId.value = assistantMessage.id
    if (!assistantMessage.sources.length && assistantMessage.graphEvidence.length) {
      evidenceTab.value = 'graph'
    }
  } catch (error) {
    const detail = error.response?.data?.detail || '智能问答服务暂时不可用，请稍后重试'
    activeSession.value.messages.push({
      id: newId('message'),
      role: 'assistant',
      content: detail,
      warnings: ['请求未完成'],
      sources: [],
      graphEvidence: [],
      suggestedQuestions: [],
      metadata: {},
      createdAt: Date.now()
    })
    ElMessage.error(detail)
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

function handleComposerKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

function openEvidence(message, tab) {
  selectedMessageId.value = message.id
  evidenceTab.value = tab
}

function selectEvidence(message) {
  if (message.role === 'assistant') selectedMessageId.value = message.id
}

function selectLatestEvidence() {
  const latest = [...messages.value].reverse().find(item => item.role === 'assistant')
  if (latest) selectedMessageId.value = latest.id
}

function isLatestAssistant(message) {
  return [...messages.value].reverse().find(item => item.role === 'assistant')?.id === message.id
}

function toggleComparison(message) {
  const selected = comparisonMessageIds.value
  if (selected.includes(message.id)) {
    comparisonMessageIds.value = selected.filter(id => id !== message.id)
    return
  }
  if (selected.length >= 2) {
    ElMessage.warning('已选择两条回答，请先取消其中一条')
    return
  }
  comparisonMessageIds.value = [...selected, message.id]
  if (comparisonMessageIds.value.length === 2) {
    ElMessage.success('已选择两条回答，可点击顶部对比按钮查看')
  }
}

function openComparison() {
  if (!comparisonReady.value) {
    ElMessage.warning('请先选择两条助手回答')
    return
  }
  comparisonVisible.value = true
}

function clearComparison() {
  comparisonMessageIds.value = []
  comparisonVisible.value = false
}

function askAboutRelation(item) {
  if (!item?.head) return
  const relation = item.tail
    ? `“${item.head}”与“${item.tail}”之间“${item.relation}”的关系`
    : `“${item.head}”相关的图谱关系`
  const paper = item.paper_title ? `，并重点核对《${item.paper_title}》中的证据` : ''
  usePrompt(`请结合当前文献与知识图谱，说明${relation}的证据、可能机制和仍需验证的问题${paper}。`)
}

function compactText(text, limit = 180) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim()
  return normalized.length > limit ? `${normalized.slice(0, limit - 1)}…` : normalized
}

function buildGeneratedPlan(message, type) {
  if (!message) return { label: '', steps: [] }

  const question = questionForMessage(message)
  const sources = message.sources || []
  const relations = message.graphEvidence || []
  const relationSummary = relations
    .slice(0, 2)
    .map(item => item.tail ? `${item.head} -[${item.relation}]-> ${item.tail}` : item.head)
    .join('；')

  if (type === 'experiment') {
    return {
      label: '实验验证计划',
      steps: [
        {
          title: '明确验证目标',
          description: `围绕“${question}”将本次回答拆成可验证的材料、工艺或性能假设。`
        },
        {
          title: '建立变量与对照',
          description: relationSummary
            ? `优先围绕图谱关系“${relationSummary}”设置自变量、对照组和重复样。`
            : '从回答中抽取关键工艺参数，设置单变量或正交对照组。'
        },
        {
          title: '制备与表征',
          description: sources.length
            ? `参考 ${sources.slice(0, 2).map(source => source.title).join('、')} 中的条件，记录制备、烧结和表征参数。`
            : '先补充可复现实验条件，再安排制备、性能测试与显微表征。'
        },
        {
          title: '分析与复核',
          description: '将结果与回答结论、文献片段和图谱关系逐项比对，记录支持、偏差及下一轮问题。'
        }
      ]
    }
  }

  const readingSteps = sources.slice(0, 3).map((source, index) => ({
    title: `精读文献 ${index + 1}`,
    description: `${source.title}${source.page_num ? `（重点第 ${source.page_num} 页）` : ''}：${compactText(source.excerpt)}`
  }))
  return {
    label: '阅读计划',
    steps: [
      {
        title: '定位问题与结论',
        description: `先核对问题“${question}”与本次回答中的核心结论、适用条件和不确定性。`
      },
      ...(readingSteps.length ? readingSteps : [{
        title: '补充核心文献',
        description: '本次回答未返回文献依据，先扩展检索范围并补充可阅读的原始文献。'
      }]),
      {
        title: '核验图谱关系',
        description: relationSummary
          ? `对照图谱关系“${relationSummary}”，确认实体、关系类型和证据是否一致。`
          : '记录回答中的关键实体与术语，继续检索其关联关系。'
      },
      {
        title: '形成阅读笔记',
        description: '输出证据矩阵：结论、引用位置、实验条件、局限性和后续追问。'
      }
    ]
  }
}

function openPlanDialog(message) {
  planMessage.value = message
  planType.value = 'reading'
  planDialogVisible.value = true
}

async function createPlanTask() {
  const message = planMessage.value
  if (!message || !generatedPlan.value.steps.length) return

  const question = questionForMessage(message)
  const plan = generatedPlan.value
  const planText = plan.steps
    .map((step, index) => `${index + 1}. ${step.title}\n${step.description}`)
    .join('\n\n')
  const description = [
    `计划类型：${plan.label}`,
    `原始问题：${question}`,
    `自动计划：\n${planText}`,
    '',
    buildTaskDescription(message, question)
  ].join('\n\n')

  planTaskCreating.value = true
  try {
    await assistantAPI.createTask({
      title: `${plan.label}：${question}`.slice(0, 255),
      description: description.length > 5000 ? `${description.slice(0, 4999)}…` : description,
      task_type: planType.value === 'reading' ? 'literature' : 'qa',
      status: 'pending',
      priority: 'medium',
      related_document_id: (message.sources || []).find(source => source.document_id)?.document_id || null
    })
    planDialogVisible.value = false
    ElMessage.success(`${plan.label}任务已创建`)
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '创建计划任务失败，请稍后重试')
  } finally {
    planTaskCreating.value = false
  }
}

function quoteMarkdown(text) {
  return String(text || '').split('\n').map(line => `> ${line}`).join('\n')
}

function formatExportTime(timestamp) {
  return new Date(timestamp || Date.now()).toLocaleString('zh-CN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function exportSession() {
  const session = activeSession.value
  if (!session?.messages?.length) {
    ElMessage.warning('当前对话暂无可导出的内容')
    return
  }

  const lines = [
    '# CeramiKG 智能问答记录',
    '',
    `- 对话：${session.title || '未命名对话'}`,
    `- 导出时间：${formatExportTime()}`,
    `- 当前范围：${selectedScopeLabel.value}`,
    ''
  ]

  session.messages.forEach((message, index) => {
    const heading = message.role === 'user' ? '用户问题' : '系统回答'
    lines.push(`## ${index + 1}. ${heading}`, '', quoteMarkdown(message.content), '')

    if (message.role !== 'assistant') return

    if (message.scopeLabel || message.metadata?.mode) {
      lines.push(`- 检索范围：${message.scopeLabel || '未记录'}`)
      lines.push(`- 问答模式：${message.metadata?.mode || '未记录'}`)
    }
    if (message.metadata?.generated_by) {
      lines.push(`- 生成方式：${message.metadata.generated_by === 'llm' ? message.metadata.model || '大模型' : '检索结果'}`)
    }
    if (message.feedback === 'helpful') lines.push('- 反馈：有帮助')
    if (message.feedback === 'needs_review') lines.push('- 反馈：已创建核验任务')
    if (message.warnings?.length) lines.push(`- 提示：${message.warnings.join('；')}`)

    if (message.sources?.length) {
      lines.push('', '### 文献依据')
      message.sources.forEach(source => {
        const page = source.page_num ? `，第 ${source.page_num} 页` : ''
        lines.push(`- ${source.citation} ${source.title}${page}`)
        lines.push(`  - 摘要：${source.excerpt}`)
      })
    }

    if (message.graphEvidence?.length) {
      lines.push('', '### 图谱依据')
      message.graphEvidence.forEach(item => {
        const relation = item.tail ? `${item.head} -[${item.relation}]-> ${item.tail}` : item.head
        const paper = item.paper_title || item.document_id
        lines.push(`- ${item.citation} ${relation}${paper ? `（${paper}）` : ''}`)
        if (item.evidence_text) lines.push(`  - 证据：${item.evidence_text}`)
      })
    }
    lines.push('')
  })

  const filename = `${String(session.title || 'ceramikg-qa')
    .replace(/[\\/:*?"<>|]/g, '_')
    .replace(/\s+/g, '_')
    .slice(0, 48) || 'ceramikg-qa'}-${new Date().toISOString().slice(0, 10)}.md`
  const blob = new Blob([`\uFEFF${lines.join('\n')}`], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = window.document.createElement('a')
  link.href = url
  link.download = filename
  window.document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
  ElMessage.success('当前对话已导出')
}

function openSourcePreview(source) {
  if (!source.preview_path) {
    ElMessage.warning('该文献尚未关联到本地文献库，暂不可预览')
    return
  }
  previewSource.value = source
  previewVisible.value = true
}

function openGraphEvidence(item) {
  if (!item.document_id) {
    ElMessage.warning('该图谱关系没有可定位的文献范围')
    return
  }
  router.push({ name: 'BuildKG', query: { document_id: item.document_id } })
}

function questionForMessage(message) {
  const index = messages.value.findIndex(item => item.id === message.id)
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    if (messages.value[cursor]?.role === 'user') return messages.value[cursor].content
  }
  return '请核验本次智能问答结论'
}

function buildTaskDescription(message, question) {
  const references = [
    ...(message.sources || []).map(source => `${source.citation} ${source.title}`),
    ...(message.graphEvidence || []).map(item => `${item.citation} ${item.paper_title || item.document_id || '图谱关系'}`)
  ]
  const content = [
    `问答问题：${question}`,
    `系统回答：${message.content}`,
    references.length ? `核对来源：\n${references.join('\n')}` : '核对来源：本次回答未返回可关联证据。'
  ].join('\n\n')
  return content.length > 5000 ? `${content.slice(0, 4999)}…` : content
}

function openTaskDialog(message) {
  const question = questionForMessage(message)
  taskSources.value = (message.sources || []).filter(source => source.document_id)
  taskDraft.value = {
    title: `核验问答：${question}`.slice(0, 255),
    description: buildTaskDescription(message, question),
    priority: 'medium',
    relatedDocumentId: taskSources.value[0]?.document_id || null
  }
  taskDialogVisible.value = true
}

function toggleHelpfulFeedback(message) {
  message.feedback = message.feedback === 'helpful' ? null : 'helpful'
  activeSession.value.updatedAt = Date.now()
  ElMessage.success(message.feedback === 'helpful' ? '已记录为有帮助' : '已取消反馈')
}

function openFeedbackDialog(message) {
  if (message.feedback === 'needs_review') {
    ElMessage.info('这条回答已创建核验任务')
    return
  }
  feedbackMessage.value = message
  feedbackNote.value = ''
  feedbackDialogVisible.value = true
}

async function createFeedbackTask() {
  const message = feedbackMessage.value
  if (!message) return

  const question = questionForMessage(message)
  const feedback = feedbackNote.value.trim() || '用户标记该回答需要进一步核验。'
  const description = [
    buildTaskDescription(message, question),
    `核验反馈：${feedback}`
  ].join('\n\n')

  feedbackSubmitting.value = true
  try {
    await assistantAPI.createTask({
      title: `核验反馈：${question}`.slice(0, 255),
      description: description.length > 5000 ? `${description.slice(0, 4999)}…` : description,
      task_type: 'qa',
      status: 'pending',
      priority: 'high',
      related_document_id: (message.sources || []).find(source => source.document_id)?.document_id || null
    })
    message.feedback = 'needs_review'
    activeSession.value.updatedAt = Date.now()
    feedbackDialogVisible.value = false
    ElMessage.success('核验任务已创建')
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '创建核验任务失败，请稍后重试')
  } finally {
    feedbackSubmitting.value = false
  }
}

async function createTask() {
  const title = taskDraft.value.title.trim()
  if (!title) {
    ElMessage.warning('请填写任务标题')
    return
  }

  taskCreating.value = true
  try {
    await assistantAPI.createTask({
      title,
      description: taskDraft.value.description.trim(),
      task_type: 'qa',
      status: 'pending',
      priority: taskDraft.value.priority,
      related_document_id: taskDraft.value.relatedDocumentId || null
    })
    taskDialogVisible.value = false
    ElMessage.success('问答任务已创建，可在任务管理中继续跟进')
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '创建任务失败，请稍后重试')
  } finally {
    taskCreating.value = false
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

function formatScore(score) {
  const value = Number(score)
  if (!Number.isFinite(value)) return '-'
  return value.toFixed(2)
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const today = new Date()
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

async function loadGraphScopes() {
  scopeLoading.value = true
  try {
    const result = await assistantAPI.getGraphScopes()
    graphScopes.value = Array.isArray(result) ? result : []
  } catch (error) {
    graphScopes.value = []
    console.warn('加载图谱范围失败:', error)
  } finally {
    scopeLoading.value = false
  }
}

watch(sessions, value => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
}, { deep: true })

watch(activeSessionId, () => {
  selectedMessageId.value = ''
  comparisonMessageIds.value = []
  comparisonVisible.value = false
  planDialogVisible.value = false
  scrollToBottom()
})

onMounted(() => {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    sessions.value = Array.isArray(saved) ? saved : []
  } catch {
    sessions.value = []
  }
  if (!sessions.value.length) createSession()
  sessions.value.forEach(session => {
    if (!Array.isArray(session.documentIds)) session.documentIds = []
    const settings = session.retrievalSettings || {}
    session.retrievalSettings = {
      topK: Math.max(1, Math.min(10, Number(settings.topK) || DEFAULT_RETRIEVAL_SETTINGS.topK)),
      graphLimit: Math.max(1, Math.min(20, Number(settings.graphLimit) || DEFAULT_RETRIEVAL_SETTINGS.graphLimit))
    }
  })
  activeSessionId.value = sessions.value[0].id
  loadGraphScopes()
})
</script>

<style scoped>
.assistant-page {
  --ink: #263238;
  --muted: #6c7a80;
  --line: #dfe5e7;
  --surface: #ffffff;
  --soft: #f4f7f7;
  --teal: #137a70;
  --blue: #315f86;
  display: grid;
  grid-template-columns: 210px minmax(0, 1fr);
  height: calc(100vh - 148px);
  min-height: 640px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  color: var(--ink);
}

.session-panel {
  min-width: 0;
  min-height: 0;
  border-right: 1px solid var(--line);
  background: #f0f4f3;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.session-header,
.evidence-header {
  height: 54px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}

.session-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.session-list {
  min-height: 0;
  flex: 1;
  padding: 8px;
  overflow-y: auto;
}

.session-item {
  width: 100%;
  height: 58px;
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) 28px;
  align-items: center;
  gap: 8px;
  padding: 0 6px 0 10px;
  border: 1px solid transparent;
  border-radius: 5px;
  background: transparent;
  color: var(--ink);
  text-align: left;
  cursor: pointer;
}

.session-item:hover,
.session-item.active {
  background: #fff;
  border-color: #d5dfdc;
}

.session-icon {
  width: 17px;
  color: var(--teal);
}

.session-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.session-time {
  color: var(--muted);
  font-size: 11px;
}

.session-delete {
  opacity: 0;
}

.session-item:hover .session-delete {
  opacity: 1;
}

.assistant-workspace {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.workspace-header {
  flex: 0 0 auto;
  min-height: 70px;
  padding: 10px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--line);
}

.workspace-header h1 {
  margin: 0 0 7px;
  font-size: 19px;
  font-weight: 600;
  letter-spacing: 0;
}

.header-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
}

.scope-select {
  width: 240px;
}

.scope-option {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.scope-option small {
  color: var(--muted);
}

.service-status {
  display: flex;
  gap: 14px;
  color: var(--muted);
  font-size: 12px;
}

.service-status span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--teal);
}

.status-dot.graph { background: var(--blue); }
.status-dot.model { background: #c85d44; }

.workspace-body {
  min-height: 0;
  flex: 1;
  display: grid;
  grid-template-columns: minmax(480px, 1fr) 320px;
  overflow: hidden;
}

.chat-panel {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.message-list {
  min-height: 0;
  flex: 1;
  padding: 22px max(22px, 5%);
  overflow-y: auto;
  background: #fbfcfc;
}

.empty-state {
  max-width: 660px;
  margin: 12vh auto 0;
  text-align: center;
}

.assistant-mark {
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #e2efec;
  color: var(--teal);
}

.assistant-mark svg { width: 22px; }

.empty-state h2 {
  margin: 0 0 22px;
  font-size: 20px;
  font-weight: 500;
  letter-spacing: 0;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.prompt-grid button,
.suggestions button {
  border: 1px solid var(--line);
  border-radius: 5px;
  background: #fff;
  color: #435158;
  cursor: pointer;
  text-align: left;
}

.prompt-grid button {
  min-height: 54px;
  padding: 10px 12px;
  line-height: 1.45;
}

.prompt-grid button:hover,
.suggestions button:hover {
  border-color: #7fa9a1;
  color: var(--teal);
}

.message-row {
  max-width: 820px;
  margin: 0 auto 22px;
  display: flex;
  gap: 11px;
}

.message-row.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #e2efec;
  color: var(--teal);
}

.message-row.user .message-avatar {
  background: #e6edf4;
  color: var(--blue);
}

.message-avatar svg { width: 16px; }

.message-content {
  min-width: 0;
  max-width: calc(100% - 42px);
}

.message-bubble {
  padding: 11px 14px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  font-size: 14px;
}

.message-row.user .message-bubble {
  border-color: #d5e2ea;
  background: #eef4f8;
}

.warning-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 7px;
}

.warning-list span {
  padding: 3px 7px;
  border-radius: 3px;
  background: #fff1ec;
  color: #a84b37;
  font-size: 11px;
}

.message-meta {
  min-height: 27px;
  margin-top: 5px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--muted);
  font-size: 11px;
}

.message-meta button {
  border: 0;
  padding: 3px 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  color: var(--blue);
  cursor: pointer;
}

.message-meta svg { width: 13px; }

.message-meta :deep(.feedback-button.active) {
  color: #22735f;
  background: #e8f5ef;
}

.message-meta :deep(.feedback-button.review) {
  color: #b85b32;
  background: #fff1e9;
}

.message-meta :deep(.compare-button.active) {
  color: #315f86;
  background: #e6edf4;
}

.message-meta > span { margin-left: auto; }

.message-meta .scope-meta {
  margin-left: 2px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-meta .scope-meta + span {
  margin-left: auto;
}

.suggestions {
  margin-top: 9px;
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.suggestions button {
  padding: 6px 9px;
  font-size: 12px;
}

.thinking {
  width: 64px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
}

.thinking span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #7e9893;
  animation: thinking 1.2s infinite ease-in-out;
}

.thinking span:nth-child(2) { animation-delay: 0.15s; }
.thinking span:nth-child(3) { animation-delay: 0.3s; }

@keyframes thinking {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-4px); opacity: 1; }
}

.composer {
  flex: 0 0 auto;
  padding: 12px 16px 10px;
  border-top: 1px solid var(--line);
  background: #fff;
}

.composer :deep(.el-textarea__inner) {
  min-height: 68px !important;
  border-radius: 5px;
  box-shadow: 0 0 0 1px var(--line) inset;
  font-size: 14px;
}

.composer :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--teal) inset;
}

.composer-footer {
  height: 34px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  color: var(--muted);
  font-size: 11px;
}

.composer-footer :deep(.el-button--primary) {
  background: var(--teal);
  border-color: var(--teal);
}

.evidence-panel {
  min-width: 0;
  min-height: 0;
  border-left: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  background: #fff;
}

.evidence-panel :deep(.el-tabs) {
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.evidence-panel :deep(.el-tabs__header) {
  margin: 0;
}

.evidence-panel :deep(.el-tabs__content) {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
}

.evidence-panel :deep(.el-tab-pane) {
  height: 100%;
}

.evidence-list {
  padding: 12px;
}

.evidence-item {
  padding: 11px;
  margin-bottom: 10px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: var(--soft);
}

.evidence-title {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.evidence-title span,
.citation {
  flex-shrink: 0;
  color: var(--teal);
  font-size: 11px;
  font-weight: 600;
}

.evidence-title strong {
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
  word-break: break-word;
}

.evidence-item p {
  margin: 8px 0 0;
  color: #56656b;
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 5;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.evidence-info {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: space-between;
  color: var(--muted);
  font-size: 10px;
}

.evidence-info :deep(.el-button) {
  margin-left: auto;
  color: var(--blue);
}

.graph-fact {
  position: relative;
}

.graph-source {
  justify-content: flex-start;
}

.graph-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
}

.graph-actions :deep(.el-button) {
  margin-left: 0;
}

.preview-frame {
  display: block;
  width: 100%;
  height: min(72vh, 780px);
  border: 0;
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.comparison-column {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--soft);
}

.comparison-heading {
  display: grid;
  gap: 5px;
  margin-bottom: 10px;
}

.comparison-heading > span {
  color: var(--teal);
  font-size: 13px;
  font-weight: 700;
}

.comparison-heading small,
.comparison-meta {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.45;
}

.comparison-answer {
  white-space: pre-wrap;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.65;
}

.comparison-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 11px;
}

.comparison-meta span {
  padding: 3px 6px;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: #fff;
}

.comparison-evidence {
  margin-top: 13px;
}

.comparison-evidence strong {
  color: var(--blue);
  font-size: 12px;
}

.comparison-evidence ul {
  margin: 6px 0 0;
  padding-left: 18px;
  color: #56656b;
  font-size: 12px;
  line-height: 1.55;
}

.plan-type-switch {
  margin-bottom: 16px;
}

.plan-steps {
  min-height: 280px;
}

.fact-node {
  margin-top: 9px;
  padding: 7px 9px;
  border-left: 3px solid var(--teal);
  background: #fff;
  font-size: 12px;
  font-weight: 600;
  word-break: break-word;
}

.fact-node.tail { border-left-color: var(--blue); }

.fact-relation {
  padding: 5px 9px;
  color: #9a4f3f;
  font-size: 11px;
}

@media (max-width: 1180px) {
  .assistant-page { grid-template-columns: 180px minmax(0, 1fr); }
  .workspace-body { grid-template-columns: minmax(420px, 1fr) 280px; }
}

@media (max-width: 920px) {
  .assistant-page { grid-template-columns: 1fr; height: auto; min-height: 760px; }
  .session-panel { display: none; }
  .workspace-body { grid-template-columns: 1fr; }
  .chat-panel { min-height: 620px; }
  .evidence-panel { border-left: 0; border-top: 1px solid var(--line); min-height: 360px; }
}

@media (max-width: 640px) {
  .workspace-header { align-items: flex-start; flex-direction: column; }
  .header-controls { width: 100%; align-items: stretch; flex-direction: column; }
  .scope-select { width: 100%; }
  .prompt-grid { grid-template-columns: 1fr; }
  .message-list { padding: 16px 10px; }
  .composer-footer > span { display: none; }
  .comparison-grid { grid-template-columns: 1fr; }
}
</style>
