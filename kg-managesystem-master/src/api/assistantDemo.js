const DEMO_SCOPES = [
  {
    document_id: 'demo-zro2',
    display_name: '氧化锆陶瓷烧结与相变研究',
    table_count: 24
  },
  {
    document_id: 'demo-alumina',
    display_name: '氧化铝陶瓷致密化研究',
    table_count: 18
  }
]

const delay = (milliseconds) => new Promise(resolve => setTimeout(resolve, milliseconds))

const scopedLabel = (names) => names?.length ? names.join('、') : '全部演示文献与图谱'

export async function demoChat(payload) {
  await delay(420)

  const includeLiterature = payload.mode !== 'graph'
  const includeGraph = payload.mode !== 'literature'
  const question = String(payload.question || '当前问题')
  const scope = scopedLabel(payload.document_names)
  const sources = includeLiterature ? [
    {
      citation: '[文献1]',
      title: '氧化锆陶瓷烧结与相变研究',
      excerpt: '提高烧结温度有助于致密化，但同时会促进晶粒长大。通过控制保温时间和添加剂含量，可在致密度与晶粒尺寸之间取得平衡。',
      score: 8.76,
      page_num: 6,
      document_id: 101,
      repository: null,
      preview_path: null
    },
    {
      citation: '[文献2]',
      title: '氧化铝陶瓷致密化研究',
      excerpt: '粉体粒径、成型密度和烧结制度共同影响氧化铝陶瓷的孔隙率与力学性能，应采用对照实验评估关键变量。',
      score: 7.94,
      page_num: 4,
      document_id: 102,
      repository: null,
      preview_path: null
    }
  ] : []
  const graphEvidence = includeGraph ? [
    {
      citation: '[图谱1]',
      head: '烧结温度',
      relation: '影响',
      tail: '致密化程度',
      document_id: null,
      paper_title: '氧化锆陶瓷烧结与相变研究',
      evidence_text: '图谱证据表明，烧结温度与致密化程度存在直接关联。'
    },
    {
      citation: '[图谱2]',
      head: '保温时间',
      relation: '促进',
      tail: '晶粒长大',
      document_id: null,
      paper_title: '氧化锆陶瓷烧结与相变研究',
      evidence_text: '延长保温时间可能提高致密度，也可能引发异常晶粒长大。'
    }
  ] : []

  return {
    answer: `针对“${question}”，演示知识库显示：烧结温度、保温时间与粉体条件是影响陶瓷致密化和性能的关键因素。提高温度通常有利于致密化，但需同步控制晶粒长大；建议通过温度、保温时间和添加剂的对照实验验证具体窗口。[文献1][图谱1]\n\n当前检索范围：${scope}。`,
    sources,
    graph_evidence: graphEvidence,
    suggested_questions: [
      '如何设计烧结温度与保温时间的对照实验？',
      '请比较致密化程度与晶粒长大的权衡关系',
      '哪些表征方法可验证上述结论？'
    ],
    warnings: ['当前为本地演示数据，未连接 Docker 服务。'],
    metadata: {
      mode: payload.mode || 'hybrid',
      literature_count: sources.length,
      graph_count: graphEvidence.length,
      document_ids: payload.document_ids || [],
      document_names: payload.document_names || [],
      generated_by: 'demo',
      model: '本地演示'
    }
  }
}

export async function demoGraphScopes() {
  await delay(120)
  return DEMO_SCOPES
}

export async function demoCreateTask(payload) {
  await delay(180)
  return {
    status: 'success',
    message: 'Demo task created',
    data: {
      id: `demo-task-${Date.now()}`,
      ...payload
    }
  }
}
