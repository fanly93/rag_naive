import { useEffect, useRef, useState } from 'react'
import { Button } from './components/ui/Button'
import { Card } from './components/ui/Card'
import { Input } from './components/ui/Input'
import { Modal } from './components/ui/Modal'
import './App.css'

type ChatSession = {
  id: string
  title: string
  updatedAt: string
  isDraft: boolean
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  isLoading?: boolean
  isError?: boolean
  topKCitations?: RecallChunk[]
  topNCitations?: RecallChunk[]
}

type SessionError = {
  failedQuery: string
  message: string
}

type QueryMode = 'none' | 'vector' | 'hybrid' | 'hybrid_rerank'
type ChatProvider = 'deepseek' | 'openai' | 'dashscope'

type BuildForm = {
  knowledgeBaseName: string
  chunkSize: number
  chunkOverlap: number
}

type KBFile = {
  id: string
  filename: string
  status: 'uploaded' | 'indexing' | 'ready' | 'failed'
}

type KnowledgeBaseConfig = BuildForm & {
  knowledgeBaseId: string
  status: 'empty' | 'building' | 'ready' | 'failed'
  files: KBFile[]
}

type RecallChannel = 'Vector' | 'BM25' | 'Rerank'

type RecallChunk = {
  id: string
  title: string
  source: string
  score: number
  content: string
  hitMode: string
  channel: RecallChannel
}

type SessionRecallState = {
  queryMode: QueryMode
  topN: number
  topK: number
  advancedOpen: boolean
  initialExpanded: boolean
  queryInput: string
  lastQuery: string
  isLoading: boolean
  initialResults: RecallChunk[]
  rerankedResults: RecallChunk[]
}

type ApiResponse<T> = {
  code: number
  message: string
  data: T
}

type BuildTask = {
  task_id: string
  knowledge_base_id: string
  stage: 'uploaded' | 'chunking' | 'indexing' | 'vectorizing' | 'done' | 'failed'
  progress: number
  error_message: string | null
}

type BackendSession = {
  id: string
  title: string
  updated_at: string
  is_draft: boolean
  knowledge_base_id: string | null
}

type BackendKB = {
  id: string
  name: string
  chunk_size: number
  chunk_overlap: number
  status: 'empty' | 'building' | 'ready' | 'failed'
  files: Array<{
    id: string
    filename: string
    status: 'uploaded' | 'indexing' | 'ready' | 'failed'
  }>
}

const buildStages = ['上传完成', '切分中', '索引构建中', '向量库构建中'] as const

const API_PREFIX = '/api/v1'

const defaultBuildForm: BuildForm = {
  knowledgeBaseName: '',
  chunkSize: 1024,
  chunkOverlap: 100,
}

const defaultSessionRecallState: SessionRecallState = {
  queryMode: 'hybrid_rerank',
  topN: 20,
  topK: 3,
  advancedOpen: true,
  initialExpanded: false,
  queryInput: '',
  lastQuery: '',
  isLoading: false,
  initialResults: [],
  rerankedResults: [],
}

function getNowLabel() {
  const now = new Date()
  const hh = String(now.getHours()).padStart(2, '0')
  const mm = String(now.getMinutes()).padStart(2, '0')
  return `今天 ${hh}:${mm}`
}

function truncateTitle(text: string) {
  const normalized = text.replace(/\s+/g, ' ').trim()
  return normalized.length > 20 ? `${normalized.slice(0, 20)}...` : normalized
}

function getQueryModeLabel(mode: QueryMode) {
  if (mode === 'none') return '不使用知识库'
  if (mode === 'vector') return '仅向量检索'
  if (mode === 'hybrid') return '向量 + BM25'
  return '向量 + BM25 + 精排'
}

function truncateText(text: string, maxLength: number) {
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text
}

function validateBuildForm(form: BuildForm) {
  if (!form.knowledgeBaseName.trim()) {
    return '知识库名称为必填项。'
  }
  if (form.knowledgeBaseName.trim().length < 2 || form.knowledgeBaseName.trim().length > 50) {
    return '知识库名称长度需在 2-50 字符之间。'
  }
  if (form.chunkSize < 256 || form.chunkSize > 4096) {
    return 'Chunk Size 需在 256-4096 之间。'
  }
  if (form.chunkOverlap < 0 || form.chunkOverlap > 512) {
    return 'Chunk Overlap 需在 0-512 之间。'
  }
  if (form.chunkOverlap >= form.chunkSize) {
    return 'Chunk Overlap 必须小于 Chunk Size。'
  }

  return ''
}

function formatUpdatedAt(isoText: string) {
  const date = new Date(isoText)
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `今天 ${hh}:${mm}`
}

function mapSession(item: BackendSession): ChatSession {
  return {
    id: item.id,
    title: item.title,
    updatedAt: formatUpdatedAt(item.updated_at),
    isDraft: item.is_draft,
  }
}

function mapKnowledgeBase(item: BackendKB): KnowledgeBaseConfig {
  return {
    knowledgeBaseId: item.id,
    knowledgeBaseName: item.name,
    chunkSize: item.chunk_size,
    chunkOverlap: item.chunk_overlap,
    status: item.status,
    files: item.files.map((file) => ({
      id: file.id,
      filename: file.filename,
      status: file.status,
    })),
  }
}

async function request<T>(path: string, init?: RequestInit) {
  const response = await fetch(`${API_PREFIX}${path}`, init)
  const payload = (await response.json()) as ApiResponse<T> | { code?: number; message?: string }
  if (!response.ok || !('code' in payload) || payload.code !== 0) {
    const message = 'message' in payload && payload.message ? payload.message : `请求失败: ${response.status}`
    throw new Error(message)
  }
  return (payload as ApiResponse<T>).data
}

function mapRetrieveChunk(item: {
  chunk_id: string
  title: string
  source: string
  score: number
  content: string
  channel: 'vector' | 'bm25' | 'rerank'
  hit_mode: string
}): RecallChunk {
  const channelMap: Record<'vector' | 'bm25' | 'rerank', RecallChannel> = {
    vector: 'Vector',
    bm25: 'BM25',
    rerank: 'Rerank',
  }
  return {
    id: item.chunk_id,
    title: item.title,
    source: item.source,
    score: item.score,
    content: item.content,
    hitMode: item.hit_mode,
    channel: channelMap[item.channel],
  }
}

type StreamMetaPayload = {
  provider: ChatProvider
  model: string
  mode: QueryMode
  top_n: number
  top_k: number
  initial_results: Array<{
    chunk_id: string
    title: string
    source: string
    score: number
    content: string
    channel: 'vector' | 'bm25' | 'rerank'
    hit_mode: string
  }>
  final_results: Array<{
    chunk_id: string
    title: string
    source: string
    score: number
    content: string
    channel: 'vector' | 'bm25' | 'rerank'
    hit_mode: string
  }>
}

async function streamChatCompletions(
  payload: {
    session_id: string
    query: string
    mode: QueryMode
    top_n: number
    top_k: number
    knowledge_base_id: string | null
    provider: ChatProvider
    model: string | null
  },
  onMeta: (meta: StreamMetaPayload) => void,
  onDelta: (token: string) => void,
) {
  const response = await fetch(`${API_PREFIX}/chat/completions/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    let message = `请求失败: ${response.status}`
    try {
      const errorPayload = (await response.json()) as { message?: string; detail?: { message?: string } }
      message = errorPayload.detail?.message ?? errorPayload.message ?? message
    } catch {
      // no-op: keep default message
    }
    throw new Error(message)
  }
  if (!response.body) {
    throw new Error('流式响应不可用')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalAnswer = ''
  let topNCitations: RecallChunk[] = []
  let topKCitations: RecallChunk[] = []

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    let separatorIndex = buffer.indexOf('\n\n')
    while (separatorIndex >= 0) {
      const block = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)
      const lines = block.split('\n')
      let event = ''
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event:')) {
          event = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          data += line.slice(5).trim()
        }
      }
      if (!event || !data) {
        separatorIndex = buffer.indexOf('\n\n')
        continue
      }
      const parsed = JSON.parse(data) as Record<string, unknown>
      if (event === 'meta') {
        const meta = parsed as unknown as StreamMetaPayload
        topNCitations = meta.initial_results.map(mapRetrieveChunk)
        topKCitations = meta.final_results.map(mapRetrieveChunk)
        onMeta(meta)
      } else if (event === 'delta') {
        const token = typeof parsed.content === 'string' ? parsed.content : ''
        if (token) {
          finalAnswer += token
          onDelta(token)
        }
      } else if (event === 'done') {
        if (typeof parsed.answer === 'string' && parsed.answer.trim()) {
          finalAnswer = parsed.answer
        }
      } else if (event === 'error') {
        const message = typeof parsed.message === 'string' ? parsed.message : '流式生成失败'
        throw new Error(message)
      }
      separatorIndex = buffer.indexOf('\n\n')
    }
  }

  return { answer: finalAnswer, topNCitations, topKCitations }
}

function App() {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState('')
  const [messagesBySession, setMessagesBySession] =
    useState<Record<string, ChatMessage[]>>({})
  const [queryInput, setQueryInput] = useState('')
  const [sendingSessionId, setSendingSessionId] = useState<string | null>(null)
  const [sessionErrorMap, setSessionErrorMap] = useState<Record<string, SessionError | undefined>>({})
  const [searchKeyword, setSearchKeyword] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<ChatSession | null>(null)
  const [deleteKnowledgeBaseConfirmOpen, setDeleteKnowledgeBaseConfirmOpen] = useState(false)
  const [showUploadWizard, setShowUploadWizard] = useState(false)
  const [uploadWizardMode, setUploadWizardMode] = useState<'create' | 'append'>('create')
  const [uploadStep, setUploadStep] = useState<'upload' | 'config'>('upload')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [buildForm, setBuildForm] = useState<BuildForm>(defaultBuildForm)
  const [buildFormError, setBuildFormError] = useState('')
  const [knowledgeBaseBySession, setKnowledgeBaseBySession] =
    useState<Record<string, KnowledgeBaseConfig | null>>({})
  const [isBuilding, setIsBuilding] = useState(false)
  const [buildStageIndex, setBuildStageIndex] = useState(0)
  const [isBuildMinimized, setIsBuildMinimized] = useState(false)
  const [showBuildFailModal, setShowBuildFailModal] = useState(false)
  const [chatQueryMode, setChatQueryMode] = useState<QueryMode>('hybrid_rerank')
  const [chatTopN, setChatTopN] = useState(20)
  const [chatTopK, setChatTopK] = useState(3)
  const [chatProvider, setChatProvider] = useState<ChatProvider>('deepseek')
  const [chatModel, setChatModel] = useState('')
  const [chatAdvancedOpen, setChatAdvancedOpen] = useState(false)
  const [expandedTopNByMessage, setExpandedTopNByMessage] = useState<Record<string, boolean>>({})
  const [recallStateBySession, setRecallStateBySession] =
    useState<Record<string, SessionRecallState>>({})
  const [selectedChunk, setSelectedChunk] = useState<RecallChunk | null>(null)
  const buildTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (buildTimerRef.current) {
        window.clearTimeout(buildTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const sessionData = await request<{ items: BackendSession[] }>('/sessions')
        const mapped = sessionData.items.map(mapSession)
        setSessions(mapped)
        if (mapped.length > 0) {
          setActiveSessionId(mapped[0].id)
        }
        setMessagesBySession(() => {
          const next: Record<string, ChatMessage[]> = {}
          mapped.forEach((session, idx) => {
            next[session.id] = [{
              id: `bootstrap-${session.id}`,
              role: 'assistant',
              content: idx === 0
                ? '会话已从后端加载完成，你可以直接进行知识库构建与召回测试。'
                : '会话已加载，可继续测试知识库与召回流程。',
            }]
          })
          return next
        })
        setRecallStateBySession(() => {
          const next: Record<string, SessionRecallState> = {}
          mapped.forEach((session) => {
            next[session.id] = { ...defaultSessionRecallState }
          })
          return next
        })
        const kbEntries = await Promise.all(mapped.map(async (session) => {
          try {
            const kb = await request<BackendKB | null>(`/sessions/${session.id}/knowledge-base`)
            return [session.id, kb ? mapKnowledgeBase(kb) : null] as const
          } catch {
            return [session.id, null] as const
          }
        }))
        setKnowledgeBaseBySession(Object.fromEntries(kbEntries))
      } catch (error) {
        console.error(error)
      }
    }
    void bootstrap()
  }, [])

  const filteredSessions = sessions.filter((session) =>
    session.title.toLowerCase().includes(searchKeyword.trim().toLowerCase()),
  )

  const activeMessages = activeSessionId ? (messagesBySession[activeSessionId] ?? []) : []
  const activeKnowledgeBase = activeSessionId ? (knowledgeBaseBySession[activeSessionId] ?? null) : null
  const activeRecallState = activeSessionId
    ? (recallStateBySession[activeSessionId] ?? { ...defaultSessionRecallState })
    : { ...defaultSessionRecallState }

  const updateActiveRecallState = (updater: (previous: SessionRecallState) => SessionRecallState) => {
    if (!activeSessionId) {
      return
    }
    setRecallStateBySession((previous) => ({
      ...previous,
      [activeSessionId]: updater(previous[activeSessionId] ?? { ...defaultSessionRecallState }),
    }))
  }

  const touchSession = (sessionId: string, updatedTitle?: string) => {
    setSessions((previous) => {
      const target = previous.find((session) => session.id === sessionId)
      if (!target) {
        return previous
      }

      const updatedSession: ChatSession = {
        ...target,
        title: updatedTitle ?? target.title,
        updatedAt: getNowLabel(),
        isDraft: updatedTitle ? false : target.isDraft,
      }

      const others = previous.filter((session) => session.id !== sessionId)
      return [updatedSession, ...others]
    })
  }

  const handleCreateSession = async () => {
    const existingDraft = sessions.find((session) => session.isDraft)

    if (existingDraft) {
      setActiveSessionId(existingDraft.id)
      return
    }

    try {
      const created = await request<BackendSession>('/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: '新会话' }),
      })
      const newSession = mapSession(created)
      setSessions((previous) => [newSession, ...previous])
      setMessagesBySession((previous) => ({
        ...previous,
        [newSession.id]: [
          {
            id: `msg-${Date.now()}-assistant`,
            role: 'assistant',
            content: '这是一个空白新会话，请输入你的第一个问题开始。',
          },
        ],
      }))
      setKnowledgeBaseBySession((previous) => ({
        ...previous,
        [newSession.id]: null,
      }))
      setRecallStateBySession((previous) => ({
        ...previous,
        [newSession.id]: { ...defaultSessionRecallState },
      }))
      setActiveSessionId(newSession.id)
    } catch (error) {
      setBuildFormError(error instanceof Error ? error.message : '创建会话失败')
    }
  }

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await request<{ session_id: string }>(`/sessions/${sessionId}`, { method: 'DELETE' })
    } catch (error) {
      setBuildFormError(error instanceof Error ? error.message : '删除会话失败')
      return
    }
    const remaining = sessions.filter((session) => session.id !== sessionId)
    setSessions(remaining)
    setMessagesBySession((previous) => {
      const next = { ...previous }
      delete next[sessionId]
      return next
    })
    setSessionErrorMap((previous) => {
      const next = { ...previous }
      delete next[sessionId]
      return next
    })
    setKnowledgeBaseBySession((previous) => {
      const next = { ...previous }
      delete next[sessionId]
      return next
    })
    setRecallStateBySession((previous) => {
      const next = { ...previous }
      delete next[sessionId]
      return next
    })

    if (remaining.length === 0) {
      setActiveSessionId('')
      return
    }

    if (activeSessionId === sessionId) {
      setActiveSessionId(remaining[0].id)
    }
  }

  const handleSendMessage = async (query: string, options?: { fromRetry?: boolean }) => {
    if (!activeSessionId) {
      return
    }

    const normalized = query.trim()
    if (!normalized) {
      return
    }

    const sessionId = activeSessionId
    const loadingMessageId = `msg-${Date.now()}-loading`

    setSessionErrorMap((previous) => ({ ...previous, [activeSessionId]: undefined }))

    if (!options?.fromRetry) {
      setMessagesBySession((previous) => ({
        ...previous,
        [sessionId]: [
          ...(previous[sessionId] ?? []),
          { id: `msg-${Date.now()}-user`, role: 'user', content: normalized },
        ],
      }))
    }

    setMessagesBySession((previous) => ({
      ...previous,
      [sessionId]: [
        ...(previous[sessionId] ?? []),
        {
          id: loadingMessageId,
          role: 'assistant',
          content: '',
          isLoading: true,
        },
      ],
    }))

    if (queryInput === normalized) {
      setQueryInput('')
    }
    setSendingSessionId(sessionId)

    const currentSession = sessions.find((session) => session.id === sessionId)
    if (currentSession?.isDraft) {
      touchSession(sessionId, truncateTitle(normalized))
    } else {
      touchSession(sessionId)
    }

    try {
      const streamed = await streamChatCompletions({
        session_id: sessionId,
        query: normalized,
        mode: chatQueryMode,
        top_n: chatTopN,
        top_k: chatTopK,
        knowledge_base_id: activeKnowledgeBase?.knowledgeBaseId ?? null,
        provider: chatProvider,
        model: chatModel.trim() || null,
      }, () => {
        // meta currently used for citations; no extra UI action needed here
      }, (token) => {
        setMessagesBySession((previous) => ({
          ...previous,
          [sessionId]: (previous[sessionId] ?? []).map((message) =>
            message.id === loadingMessageId
              ? {
                  ...message,
                  content: `${message.content}${token}`,
                }
              : message,
          ),
        }))
      })

      setMessagesBySession((previous) => ({
        ...previous,
        [sessionId]: (previous[sessionId] ?? []).map((message) =>
          message.id === loadingMessageId
            ? {
                id: `msg-${Date.now()}-assistant`,
                role: 'assistant',
                content: streamed.answer || '未返回文本内容。',
                topKCitations: streamed.topKCitations,
                topNCitations: streamed.topNCitations,
              }
            : message,
        ),
      }))
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '发生未知错误，请稍后再试。'
      setMessagesBySession((previous) => ({
        ...previous,
        [sessionId]: (previous[sessionId] ?? []).map((item) =>
          item.id === loadingMessageId
            ? {
                id: `msg-${Date.now()}-assistant-error`,
                role: 'assistant',
                content: message,
                isError: true,
              }
            : item,
        ),
      }))
      setSessionErrorMap((previous) => ({
        ...previous,
        [sessionId]: {
          failedQuery: normalized,
          message,
        },
      }))
    } finally {
      setSendingSessionId(null)
    }
  }

  const stageToStepIndex: Record<BuildTask['stage'], number> = {
    uploaded: 0,
    chunking: 1,
    indexing: 2,
    vectorizing: 3,
    done: 3,
    failed: 3,
  }

  const syncSessionKnowledgeBase = async (sessionId: string) => {
    const kb = await request<BackendKB | null>(`/sessions/${sessionId}/knowledge-base`)
    setKnowledgeBaseBySession((previous) => ({
      ...previous,
      [sessionId]: kb ? mapKnowledgeBase(kb) : null,
    }))
  }

  const pollBuildTask = async (taskId: string) => {
    let latest: BuildTask | null = null
    for (let i = 0; i < 120; i += 1) {
      const task = await request<BuildTask>(`/build-tasks/${taskId}`)
      latest = task
      setBuildStageIndex(stageToStepIndex[task.stage])
      if (task.stage === 'done' || task.stage === 'failed') {
        return task
      }
      await new Promise((resolve) => {
        buildTimerRef.current = window.setTimeout(resolve, 1000)
      })
    }
    throw new Error(latest ? `构建超时，当前阶段：${latest.stage}` : '构建超时')
  }

  const handleStartBuild = async () => {
    const error = validateBuildForm(buildForm)
    if (!selectedFile) {
      setBuildFormError('请先上传一个文档文件。')
      return
    }
    if (error) {
      setBuildFormError(error)
      return
    }
    if (!activeSessionId) {
      setBuildFormError('请先选择会话')
      return
    }

    try {
      setBuildFormError('')
      setShowUploadWizard(false)
      setIsBuilding(true)
      setIsBuildMinimized(false)
      setBuildStageIndex(0)

      const formData = new FormData()
      formData.append('session_id', activeSessionId)
      formData.append('name', buildForm.knowledgeBaseName.trim())
      formData.append('chunk_size', String(buildForm.chunkSize))
      formData.append('chunk_overlap', String(buildForm.chunkOverlap))
      formData.append('file', selectedFile)

      const created = await request<{ knowledge_base_id: string; task_id: string }>('/knowledge-bases', {
        method: 'POST',
        body: formData,
      })
      const task = await pollBuildTask(created.task_id)
      await syncSessionKnowledgeBase(activeSessionId)
      if (task.stage === 'failed') {
        setShowBuildFailModal(true)
      } else {
        updateActiveRecallState((previous) => ({
          ...previous,
          queryInput: '',
          lastQuery: '',
          initialResults: [],
          rerankedResults: [],
        }))
      }
    } catch (buildError) {
      setBuildFormError(buildError instanceof Error ? buildError.message : '创建知识库失败')
      setShowBuildFailModal(true)
    } finally {
      setIsBuilding(false)
      setIsBuildMinimized(false)
    }
  }

  const handleAppendFile = async () => {
    if (!selectedFile) {
      setBuildFormError('请先选择一个文档。')
      return
    }
    if (!activeKnowledgeBase) {
      setBuildFormError('请先创建知识库。')
      return
    }

    try {
      setBuildFormError('')
      setShowUploadWizard(false)
      setIsBuilding(true)
      setIsBuildMinimized(false)
      setBuildStageIndex(0)

      const formData = new FormData()
      formData.append('file', selectedFile)
      const appended = await request<{ knowledge_base_id: string; task_id: string }>(
        `/knowledge-bases/${activeKnowledgeBase.knowledgeBaseId}/files`,
        {
          method: 'POST',
          body: formData,
        },
      )
      const task = await pollBuildTask(appended.task_id)
      if (activeSessionId) {
        await syncSessionKnowledgeBase(activeSessionId)
      }
      if (task.stage === 'failed') {
        setShowBuildFailModal(true)
      }
    } catch (appendError) {
      setBuildFormError(appendError instanceof Error ? appendError.message : '追加文档失败')
      setShowBuildFailModal(true)
    } finally {
      setIsBuilding(false)
      setIsBuildMinimized(false)
    }
  }

  const handleRecallTest = async () => {
    const normalized = activeRecallState.queryInput.trim()
    if (!normalized || !activeKnowledgeBase) {
      return
    }
    if (activeRecallState.topN < 1 || activeRecallState.topK < 1) {
      return
    }
    if (activeRecallState.topK > activeRecallState.topN) {
      return
    }
    if (activeRecallState.queryMode === 'none') {
      updateActiveRecallState((previous) => ({
        ...previous,
        lastQuery: normalized,
        initialResults: [],
        rerankedResults: [],
      }))
      return
    }
    updateActiveRecallState((previous) => ({ ...previous, isLoading: true }))
    try {
      const data = await request<{
        query: string
        initial_results: Array<{
          chunk_id: string
          title: string
          source: string
          score: number
          content: string
          channel: 'vector' | 'bm25' | 'rerank'
          hit_mode: string
        }>
        final_results: Array<{
          chunk_id: string
          title: string
          source: string
          score: number
          content: string
          channel: 'vector' | 'bm25' | 'rerank'
          hit_mode: string
        }>
      }>(`/knowledge-bases/${activeKnowledgeBase.knowledgeBaseId}/retrieve-test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: normalized,
          mode: activeRecallState.queryMode,
          top_n: activeRecallState.topN,
          top_k: activeRecallState.topK,
        }),
      })
      updateActiveRecallState((previous) => ({
        ...previous,
        initialResults: data.initial_results.map(mapRetrieveChunk),
        rerankedResults: data.final_results.map(mapRetrieveChunk),
        lastQuery: normalized,
        isLoading: false,
      }))
    } catch (error) {
      updateActiveRecallState((previous) => ({ ...previous, isLoading: false }))
      setBuildFormError(error instanceof Error ? error.message : '召回测试失败')
    }
  }

  const handleOpenChunk = async (chunk: RecallChunk) => {
    if (!activeKnowledgeBase) {
      setSelectedChunk(chunk)
      return
    }
    try {
      const detail = await request<{
        chunk_id: string
        title: string
        source: string
        score: number
        content: string
        channel: 'vector' | 'bm25' | 'rerank'
        hit_mode: string
      }>(`/knowledge-bases/${activeKnowledgeBase.knowledgeBaseId}/chunks/${chunk.id}`)
      setSelectedChunk(mapRetrieveChunk(detail))
    } catch {
      setSelectedChunk(chunk)
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <h1 className="app-title">RAG本地知识库问答引擎</h1>
      </header>

      <main className="workspace">
        <aside className="column left-column">
          <Card title="历史会话" subtitle="支持搜索、新建、切换与删除">
            <Input
              placeholder="搜索会话标题..."
              value={searchKeyword}
              onChange={(event) => setSearchKeyword(event.target.value)}
            />

            <div className="session-list">
              {filteredSessions.length === 0 ? (
                <div className="session-empty">没有匹配的会话</div>
              ) : (
                filteredSessions.map((session) => (
                  <div
                    key={session.id}
                    role="button"
                    tabIndex={0}
                    className={`session-item ${session.id === activeSessionId ? 'is-active' : ''}`}
                    onClick={() => setActiveSessionId(session.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        setActiveSessionId(session.id)
                      }
                    }}
                  >
                    <div className="session-main">
                      <span className="session-title" title={session.title}>
                        {session.title}
                      </span>
                      {session.isDraft ? <span className="session-badge">空白</span> : null}
                    </div>
                    <div className="session-meta">
                      <span>{session.updatedAt}</span>
                      <button
                        type="button"
                        className="session-delete"
                        aria-label="删除会话"
                        onClick={(event) => {
                          event.stopPropagation()
                          setDeleteTarget(session)
                        }}
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            <Button variant="secondary" fullWidth onClick={() => void handleCreateSession()}>
              新建会话
            </Button>
          </Card>
        </aside>

        <section className="column center-column">
          <Card title="问答聊天区" subtitle="已支持发送、加载态、会话绑定与错误重试">
            <div className="chat-stream">
              {activeMessages.map((message) => (
                <div key={message.id} className="chat-message">
                  <div
                    className={`chat-bubble ${message.role} ${message.isError ? 'is-error' : ''}`}
                  >
                    {message.isLoading
                      ? (message.content
                        ? `${message.content}▌`
                        : <span className="typing-dots">思考中...</span>)
                      : message.content}
                  </div>
                  {message.role === 'assistant' && message.topKCitations && message.topKCitations.length > 0 ? (
                    <div className="citation-panel">
                      <div className="citation-panel-title">Top-K 引用来源</div>
                      <div className="citation-panel-list">
                        {message.topKCitations.map((chunk, index) => (
                          <button
                            key={`${message.id}-k-${chunk.id}`}
                            type="button"
                            className="citation-dropdown-item"
                            onClick={() => void handleOpenChunk(chunk)}
                            title={chunk.content}
                          >
                            <span className="citation-index">[{index + 1}]</span>
                            <span className="citation-preview">{truncateText(chunk.content, 30)}</span>
                            <span className="citation-score">相关性 {chunk.score.toFixed(4)}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {message.role === 'assistant' && message.topNCitations && message.topNCitations.length > 0 ? (
                    <div className="citation-dropdown">
                      <button
                        type="button"
                        className="citation-dropdown-trigger"
                        onClick={() =>
                          setExpandedTopNByMessage((previous) => ({
                            ...previous,
                            [message.id]: !previous[message.id],
                          }))
                        }
                      >
                        初召回（Top-N）{expandedTopNByMessage[message.id] ? '▲' : '▼'}
                      </button>
                      {expandedTopNByMessage[message.id] ? (
                        <div className="citation-dropdown-list">
                          {message.topNCitations.map((chunk, index) => (
                            <button
                              key={`${message.id}-n-${chunk.id}`}
                              type="button"
                              className="citation-dropdown-item"
                              onClick={() => void handleOpenChunk(chunk)}
                              title={chunk.content}
                            >
                              <span className="citation-index">[{index + 1}]</span>
                              <span className="citation-preview">{truncateText(chunk.content, 30)}</span>
                              <span className="citation-score">相关性 {chunk.score.toFixed(4)}</span>
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ))}
              {activeMessages.length === 0 ? (
                <div className="chat-empty-tip">请选择或创建会话开始聊天。</div>
              ) : null}
            </div>

            {activeSessionId && sessionErrorMap[activeSessionId] ? (
              <div className="retry-bar">
                <span className="retry-text">{sessionErrorMap[activeSessionId]?.message}</span>
                <Button
                  variant="secondary"
                  onClick={() => {
                    const failed = sessionErrorMap[activeSessionId]
                    if (failed) {
                      void handleSendMessage(failed.failedQuery, { fromRetry: true })
                    }
                  }}
                  disabled={sendingSessionId === activeSessionId}
                >
                  重试
                </Button>
              </div>
            ) : null}

            <div className="advanced-panel">
              <div className="advanced-panel__head">
                <span className="advanced-summary">
                  {getQueryModeLabel(chatQueryMode)} · Top-N {chatTopN} · Top-K {chatTopK}
                </span>
                <button
                  type="button"
                  className="advanced-toggle"
                  onClick={() => setChatAdvancedOpen((previous) => !previous)}
                >
                  {chatAdvancedOpen ? '收起设置' : '高级设置'}
                </button>
              </div>
              {chatAdvancedOpen ? (
                <div className="advanced-grid">
                  <label className="advanced-field">
                    <span>问答模式</span>
                    <select
                      className="query-mode-select"
                      value={chatQueryMode}
                      onChange={(event) => setChatQueryMode(event.target.value as QueryMode)}
                    >
                      <option value="none">不使用知识库</option>
                      <option value="vector">仅向量检索</option>
                      <option value="hybrid">向量 + BM25</option>
                      <option value="hybrid_rerank">向量 + BM25 + 精排</option>
                    </select>
                  </label>
                  <label className="advanced-field">
                    <span>Top-N</span>
                    <Input
                      className="query-number-input"
                      type="number"
                      min={1}
                      value={chatTopN}
                      onChange={(event) => setChatTopN(Math.max(1, Number(event.target.value || 1)))}
                    />
                  </label>
                  <label className="advanced-field">
                    <span>Top-K</span>
                    <Input
                      className="query-number-input"
                      type="number"
                      min={1}
                      value={chatTopK}
                      onChange={(event) => setChatTopK(Math.max(1, Number(event.target.value || 1)))}
                    />
                  </label>
                  <label className="advanced-field">
                    <span>模型提供商</span>
                    <select
                      className="query-mode-select"
                      value={chatProvider}
                      onChange={(event) => setChatProvider(event.target.value as ChatProvider)}
                    >
                      <option value="deepseek">DeepSeek</option>
                      <option value="openai">OpenAI</option>
                      <option value="dashscope">DashScope</option>
                    </select>
                  </label>
                  <label className="advanced-field">
                    <span>模型名（可选覆盖）</span>
                    <Input
                      placeholder="留空使用后端默认模型"
                      value={chatModel}
                      onChange={(event) => setChatModel(event.target.value)}
                    />
                  </label>
                </div>
              ) : null}
            </div>

            <div className="composer composer-main">
              <Input
                placeholder="输入你的问题..."
                value={queryInput}
                onChange={(event) => setQueryInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    void handleSendMessage(queryInput)
                  }
                }}
                disabled={!activeSessionId || sendingSessionId === activeSessionId}
              />
              <Button
                onClick={() => void handleSendMessage(queryInput)}
                disabled={!activeSessionId || !queryInput.trim() || sendingSessionId === activeSessionId}
              >
                {sendingSessionId === activeSessionId ? '发送中...' : '发送'}
              </Button>
            </div>
          </Card>
        </section>

        <aside className="column right-column">
          <Card title="知识库与召回测试" subtitle="已实现上传、参数配置与构建状态流转">
            {activeKnowledgeBase ? (
              <>
                <div className="kb-summary">
                  <div className="kb-row">
                    <span>知识库名称</span>
                    <strong>{activeKnowledgeBase.knowledgeBaseName}</strong>
                  </div>
                  <div className="kb-row">
                    <span>参数</span>
                    <strong>
                      Chunk {activeKnowledgeBase.chunkSize}/{activeKnowledgeBase.chunkOverlap}
                    </strong>
                  </div>
                </div>

                <div className="kb-actions">
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setUploadWizardMode('append')
                      setShowUploadWizard(true)
                      setUploadStep('upload')
                      setSelectedFile(null)
                      setBuildFormError('')
                    }}
                  >
                    继续上传文档
                  </Button>
                  <Button variant="secondary" onClick={() => setDeleteKnowledgeBaseConfirmOpen(true)}>
                    删除知识库
                  </Button>
                </div>

                <div className="kb-files">
                  <h4 className="kb-files-title">已上传文件</h4>
                  {activeKnowledgeBase.files.length === 0 ? (
                    <p className="hint-line">暂无文件</p>
                  ) : (
                    activeKnowledgeBase.files.map((fileItem) => (
                      <div key={fileItem.id} className="kb-file-item">
                        <span title={fileItem.filename}>{fileItem.filename}</span>
                        <button
                          type="button"
                          onClick={async () => {
                            if (!activeKnowledgeBase || !activeSessionId) {
                              return
                            }
                            try {
                              await request<{ knowledge_base_id: string; file_id: string }>(
                                `/knowledge-bases/${activeKnowledgeBase.knowledgeBaseId}/files/${fileItem.id}`,
                                { method: 'DELETE' },
                              )
                              await syncSessionKnowledgeBase(activeSessionId)
                            } catch (error) {
                              setBuildFormError(error instanceof Error ? error.message : '删除文件失败')
                            }
                          }}
                        >
                          删除
                        </button>
                      </div>
                    ))
                  )}
                </div>

                <div className="recall-box">
                  <h4 className="recall-title">召回测试（Phase 4）</h4>
                  <div className="advanced-panel">
                    <div className="advanced-panel__head">
                      <span className="advanced-summary">
                        {getQueryModeLabel(activeRecallState.queryMode)} · Top-N {activeRecallState.topN} · Top-K {activeRecallState.topK}
                      </span>
                      <button
                        type="button"
                        className="advanced-toggle"
                        onClick={() =>
                          updateActiveRecallState((previous) => ({
                            ...previous,
                            advancedOpen: !previous.advancedOpen,
                          }))
                        }
                      >
                        {activeRecallState.advancedOpen ? '收起设置' : '高级设置'}
                      </button>
                    </div>
                    {activeRecallState.advancedOpen ? (
                      <div className="advanced-grid">
                        <label className="advanced-field">
                          <span>召回模式</span>
                          <select
                            className="query-mode-select"
                            value={activeRecallState.queryMode}
                            onChange={(event) =>
                              updateActiveRecallState((previous) => ({
                                ...previous,
                                queryMode: event.target.value as QueryMode,
                              }))
                            }
                          >
                            <option value="vector">仅向量检索</option>
                            <option value="hybrid">向量 + BM25</option>
                            <option value="hybrid_rerank">向量 + BM25 + 精排</option>
                          </select>
                        </label>
                        <label className="advanced-field">
                          <span>Top-N</span>
                          <Input
                            className="query-number-input"
                            type="number"
                            min={1}
                            value={activeRecallState.topN}
                            onChange={(event) =>
                              updateActiveRecallState((previous) => ({
                                ...previous,
                                topN: Math.max(1, Number(event.target.value || 1)),
                              }))
                            }
                          />
                        </label>
                        <label className="advanced-field">
                          <span>Top-K</span>
                          <Input
                            className="query-number-input"
                            type="number"
                            min={1}
                            value={activeRecallState.topK}
                            onChange={(event) =>
                              updateActiveRecallState((previous) => ({
                                ...previous,
                                topK: Math.max(1, Number(event.target.value || 1)),
                              }))
                            }
                          />
                        </label>
                      </div>
                    ) : null}
                  </div>

                  <div className="composer composer-main">
                    <Input
                      placeholder="输入测试查询..."
                      value={activeRecallState.queryInput}
                      onChange={(event) =>
                        updateActiveRecallState((previous) => ({
                          ...previous,
                          queryInput: event.target.value,
                        }))
                      }
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' && !event.shiftKey) {
                          event.preventDefault()
                          void handleRecallTest()
                        }
                      }}
                    />
                    <Button
                      onClick={() => void handleRecallTest()}
                      disabled={!activeRecallState.queryInput.trim() || activeRecallState.isLoading}
                    >
                      发送
                    </Button>
                  </div>
                  {activeRecallState.lastQuery ? (
                    <p className="hint-line">最近一次召回测试：{activeRecallState.lastQuery}</p>
                  ) : null}
                  {activeRecallState.topK > activeRecallState.topN ? (
                    <p className="form-error">Top-K 不能大于 Top-N。</p>
                  ) : null}

                  <div className="recall-actions">
                    <button
                      type="button"
                      className="recall-collapse-trigger"
                      onClick={() =>
                        updateActiveRecallState((previous) => ({
                          ...previous,
                          initialExpanded: !previous.initialExpanded,
                        }))
                      }
                      disabled={activeRecallState.initialResults.length === 0}
                    >
                      初召回结果（Top-N）{activeRecallState.initialExpanded ? '▲' : '▼'}
                    </button>
                  </div>

                  {activeRecallState.isLoading ? <p className="hint-line">正在检索并重排，请稍候...</p> : null}

                  {activeRecallState.lastQuery && activeRecallState.queryMode === 'none' ? (
                    <p className="hint-line">当前模式为不使用知识库，不展示召回结果。</p>
                  ) : null}

                  {activeRecallState.lastQuery && !activeRecallState.isLoading ? (
                    <div className="recall-result-list">
                      {activeRecallState.rerankedResults.map((chunk) => (
                        <button
                          key={chunk.id}
                          type="button"
                          className="recall-result-item"
                          onClick={() => void handleOpenChunk(chunk)}
                        >
                          <div className="recall-result-head">
                            <span>{chunk.title}</span>
                            <strong>相关性 {chunk.score}</strong>
                          </div>
                          <p>{truncateText(chunk.content, 100)}</p>
                        </button>
                      ))}
                    </div>
                  ) : null}

                  {activeRecallState.initialExpanded ? (
                    <div className="initial-result-list inline-initial-list">
                      {activeRecallState.initialResults.map((chunk) => (
                        <button
                          key={chunk.id}
                          type="button"
                          className="initial-result-item"
                          onClick={() => void handleOpenChunk(chunk)}
                        >
                          <div className="recall-result-head">
                            <span>{chunk.title}</span>
                            <strong>相关性 {chunk.score}</strong>
                          </div>
                          <div className="initial-result-meta">
                            <span className={`channel-badge ${chunk.channel === 'BM25' ? 'is-bm25' : 'is-vector'}`}>
                              {chunk.channel}
                            </span>
                            <span>{chunk.source}</span>
                          </div>
                          <p>{truncateText(chunk.content, 100)}</p>
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </>
            ) : (
              <>
                <div className="empty-state">暂无知识库，请先上传文档开始构建</div>
                <Button
                  fullWidth
                  onClick={() => {
                    setUploadWizardMode('create')
                    setShowUploadWizard(true)
                    setUploadStep('upload')
                    setSelectedFile(null)
                    setBuildFormError('')
                  }}
                >
                  上传文档
                </Button>
              </>
            )}
          </Card>
        </aside>
      </main>

      <Modal
        open={Boolean(deleteTarget)}
        title="确认删除会话？"
        description="删除后不可恢复。"
        onClose={() => setDeleteTarget(null)}
      >
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
            取消
          </Button>
          <Button
            onClick={() => {
              if (deleteTarget) {
                void handleDeleteSession(deleteTarget.id)
              }
              setDeleteTarget(null)
            }}
          >
            确认删除
          </Button>
        </div>
      </Modal>

      <Modal
        open={showUploadWizard}
        title={uploadStep === 'upload' ? '上传文档' : '配置构建参数'}
        description={
          uploadStep === 'upload'
            ? '支持格式：.txt / .md / .pdf，单次仅上传 1 个文件。'
            : '请确认参数后开始构建向量数据库。'
        }
        onClose={() => {
          setShowUploadWizard(false)
          setBuildFormError('')
        }}
      >
        {uploadStep === 'upload' ? (
          <div className="wizard-block">
            <input
              className="file-input"
              type="file"
              accept=".txt,.md,.pdf,text/plain,application/pdf,text/markdown"
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null
                setSelectedFile(file)
              }}
            />
            {selectedFile ? <p className="hint-line">已选择：{selectedFile.name}</p> : null}
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setShowUploadWizard(false)}>
                取消
              </Button>
              <Button
                onClick={() => {
                  if (!selectedFile) {
                    setBuildFormError('请先选择一个文档。')
                    return
                  }
                  if (uploadWizardMode === 'append') {
                    void handleAppendFile()
                    return
                  }
                  setBuildFormError('')
                  setUploadStep('config')
                }}
              >
                {uploadWizardMode === 'append' ? '上传并构建' : '下一步'}
              </Button>
            </div>
          </div>
        ) : (
          <div className="wizard-block">
            <div className="form-grid">
              <label className="form-item">
                <span>知识库名称</span>
                <Input
                  value={buildForm.knowledgeBaseName}
                  onChange={(event) =>
                    setBuildForm((previous) => ({
                      ...previous,
                      knowledgeBaseName: event.target.value,
                    }))
                  }
                  placeholder="请输入知识库名称"
                />
              </label>
              <label className="form-item">
                <span>Chunk Size</span>
                <Input
                  type="number"
                  min={256}
                  max={4096}
                  value={buildForm.chunkSize}
                  onChange={(event) =>
                    setBuildForm((previous) => ({
                      ...previous,
                      chunkSize: Number(event.target.value || 0),
                    }))
                  }
                />
              </label>
              <label className="form-item">
                <span>Chunk Overlap</span>
                <Input
                  type="number"
                  min={0}
                  max={512}
                  value={buildForm.chunkOverlap}
                  onChange={(event) =>
                    setBuildForm((previous) => ({
                      ...previous,
                      chunkOverlap: Number(event.target.value || 0),
                    }))
                  }
                />
              </label>
            </div>
            <p className="hint-line">
              提示：Top-N / Top-K 已移至问答区与召回测试区选择；若需模拟失败，可在知识库名称中包含“失败”进行测试。
            </p>
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setUploadStep('upload')}>
                上一步
              </Button>
              <Button variant="secondary" onClick={() => setShowUploadWizard(false)}>
                取消
              </Button>
              <Button onClick={() => void handleStartBuild()}>开始构建</Button>
            </div>
          </div>
        )}
        {buildFormError ? <p className="form-error">{buildFormError}</p> : null}
      </Modal>

      <Modal
        open={deleteKnowledgeBaseConfirmOpen}
        title="确认删除知识库？"
        description="删除后将清空右侧已上传文件与召回结果。"
        onClose={() => setDeleteKnowledgeBaseConfirmOpen(false)}
      >
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => setDeleteKnowledgeBaseConfirmOpen(false)}>
            取消
          </Button>
          <Button
            onClick={async () => {
              if (!activeSessionId || !activeKnowledgeBase) {
                setDeleteKnowledgeBaseConfirmOpen(false)
                return
              }
              try {
                await request<{ knowledge_base_id: string }>(
                  `/knowledge-bases/${activeKnowledgeBase.knowledgeBaseId}`,
                  { method: 'DELETE' },
                )
                setKnowledgeBaseBySession((previous) => ({
                  ...previous,
                  [activeSessionId]: null,
                }))
                updateActiveRecallState((previous) => ({
                  ...previous,
                  initialResults: [],
                  rerankedResults: [],
                  lastQuery: '',
                  queryInput: '',
                }))
              } catch (error) {
                setBuildFormError(error instanceof Error ? error.message : '删除知识库失败')
              } finally {
                setDeleteKnowledgeBaseConfirmOpen(false)
              }
            }}
          >
            确认删除
          </Button>
        </div>
      </Modal>

      {isBuilding && !isBuildMinimized ? (
        <section className="build-dialog">
          <div className="build-dialog__header">
            <h3>构建进行中</h3>
            <button type="button" onClick={() => setIsBuildMinimized(true)}>
              最小化
            </button>
          </div>
          <p className="build-hint">正在切分并构建向量索引，请稍候...</p>
          <ul className="build-steps">
            {buildStages.map((stage, index) => (
              <li key={stage} className={index <= buildStageIndex ? 'is-done' : ''}>
                {stage}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {isBuilding && isBuildMinimized ? (
        <button
          className="build-mini"
          type="button"
          onClick={() => setIsBuildMinimized(false)}
        >
          构建中：{buildStages[buildStageIndex]}（点击展开）
        </button>
      ) : null}

      <Modal
        open={showBuildFailModal}
        title="创建向量数据库失败，请重试"
        onClose={() => setShowBuildFailModal(false)}
      >
        <div className="modal-actions">
          <Button onClick={() => setShowBuildFailModal(false)}>确认</Button>
        </div>
      </Modal>

      <Modal
        open={Boolean(selectedChunk)}
        title={selectedChunk?.title ?? '片段详情'}
        description={selectedChunk ? `相关性 ${selectedChunk.score}` : ''}
        onClose={() => setSelectedChunk(null)}
      >
        {selectedChunk ? (
          <div className="chunk-detail">
            <div className="chunk-detail-row">
              <span>来源文档</span>
              <strong>{selectedChunk.source}</strong>
            </div>
            <div className="chunk-detail-row">
              <span>命中方式</span>
              <strong>{selectedChunk.hitMode}</strong>
            </div>
            <article className="chunk-detail-content">{selectedChunk.content}</article>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}

export default App
