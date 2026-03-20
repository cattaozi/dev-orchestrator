'use client'

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, Loader2, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { parseEventContent } from '@/lib/message-parser'
import { Markdown } from '@/components/ui/markdown'

interface Project {
  id: number
  name: string
  local_path: string
}

interface Session {
  id: number
  issue_id: number | null
  project_id: number
  status: string
}

interface SessionEvent {
  id: number
  role: string
  content: string
}

interface ConversationItem {
  id: string
  type: 'user' | 'assistant'
  text: string
}

interface ChatSessionState {
  project_id: number
  session_id: number | null
  status: string
  last_active_at: string | null
}

interface SlashCommand {
  command: '/init' | '/clear' | '/close'
  description: string
}

function normalizeEventContent(content: string): string {
  return (content || '').replace(/\\n/g, '\n').trim()
}

function extractToolResultTextBlocks(rawContent: string): string[] {
  const texts: string[] = []
  const regex = /'text':\s*'((?:[^'\\]|\\.)*)'/g
  let match: RegExpExecArray | null
  while ((match = regex.exec(rawContent)) !== null) {
    const unescaped = match[1]
      .replace(/\\n/g, '\n')
      .replace(/\\'/g, "'")
      .trim()
    if (unescaped) texts.push(unescaped)
  }
  return texts
}

function isInternalToolErrorText(text: string): boolean {
  return (
    text.includes('API Error:') ||
    text.includes('request_id') ||
    text.includes('agentId:') ||
    text.includes('invalid_parameter_error') ||
    text.includes('not supported')
  )
}

function isAssistantBoilerplate(text: string): boolean {
  const normalized = text
    .replace(/\s+/g, '')
    .replace(/[！!？?。,.，:：]/g, '')
  return (
    normalized.includes('我是项目协作助手') ||
    normalized.includes('请告诉我你需要什么帮助') ||
    (normalized.includes('你可以') && normalized.includes('提问') && normalized.includes('执行修改'))
  )
}

const SLASH_COMMANDS: SlashCommand[] = [
  { command: '/init', description: '生成或补全项目 CLAUDE.md' },
  { command: '/clear', description: '清空当前项目对话记录' },
  { command: '/close', description: '关闭当前项目会话' },
]

export default function ProjectChatPage() {
  const params = useParams()
  const projectId = Number(params.id)

  const [project, setProject] = useState<Project | null>(null)
  const [chatState, setChatState] = useState<ChatSessionState | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [events, setEvents] = useState<SessionEvent[]>([])
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [awaitingAssistant, setAwaitingAssistant] = useState(false)
  const [error, setError] = useState('')
  const [activeCommandIndex, setActiveCommandIndex] = useState(0)

  const lastEventIdRef = useRef(0)
  const waitingSinceEventIdRef = useRef(0)
  const endRef = useRef<HTMLDivElement>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)

  const conversationItems = useMemo<ConversationItem[]>(() => {
    const items: ConversationItem[] = []

    for (const event of events) {
      const rawContent = normalizeEventContent(event.content || '')
      if (!rawContent) continue

      if (event.role === 'user') {
        items.push({
          id: `u-${event.id}`,
          type: 'user',
          text: rawContent,
        })
        continue
      }

      const parsed = parseEventContent(rawContent)
      const textParts: string[] = []
      parsed.forEach((msg) => {
        if (msg.type === 'text' && msg.text) textParts.push(msg.text)
        if (msg.type === 'system_reminder' && msg.reminderText) textParts.push(msg.reminderText)
      })

      if (textParts.length === 0 && rawContent.includes('ToolResultBlock')) {
        const toolTexts = extractToolResultTextBlocks(rawContent)
        textParts.push(...toolTexts.filter((t) => !isInternalToolErrorText(t)))
      }

      if (textParts.length > 0) {
        const mergedText = textParts.join('\n\n').trim()
        if (isAssistantBoilerplate(mergedText)) continue
        items.push({
          id: `a-${event.id}`,
          type: 'assistant',
          text: mergedText,
        })
      }
    }

    return items
  }, [events])
  const slashQuery = useMemo(() => {
    const trimmed = message.trimStart()
    if (!trimmed.startsWith('/')) return null
    return trimmed.slice(1).toLowerCase()
  }, [message])
  const filteredCommands = useMemo(() => {
    if (slashQuery === null) return []
    if (!slashQuery) return SLASH_COMMANDS
    return SLASH_COMMANDS.filter((c) =>
      c.command.slice(1).toLowerCase().includes(slashQuery) ||
      c.description.toLowerCase().includes(slashQuery)
    )
  }, [slashQuery])
  const isCommandMenuOpen = filteredCommands.length > 0

  useEffect(() => {
    if (!projectId) return
    const bootstrap = async () => {
      setLoading(true)
      setError('')
      try {
        const [projectRes, chatRes] = await Promise.all([
          fetch(`/api/projects/${projectId}`),
          fetch(`/api/projects/${projectId}/chat-session`),
        ])

        if (!projectRes.ok) throw new Error('Failed to load project')
        const projectData = await projectRes.json()
        setProject(projectData)

        if (chatRes.ok) {
          const state: ChatSessionState = await chatRes.json()
          setChatState(state)
          if (state.session_id) {
            const sessionRes = await fetch(`/api/sessions/${state.session_id}`)
            if (sessionRes.ok) {
              const sessionData = await sessionRes.json()
              setSession(sessionData)
            }
          }
        }
      } catch (e) {
        setError('加载项目会话失败')
      } finally {
        setLoading(false)
      }
    }
    bootstrap()
  }, [projectId])

  useEffect(() => {
    if (!session?.id) return

    const fetchEvents = async () => {
      const afterId = lastEventIdRef.current
      const url = afterId > 0
        ? `/api/sessions/${session.id}/events?after_id=${afterId}`
        : `/api/sessions/${session.id}/events`

      const res = await fetch(url)
      if (!res.ok) return
      const data = await res.json()
      const newEvents: SessionEvent[] = data.events || []
      if (newEvents.length > 0) {
        setEvents((prev) => [...prev, ...newEvents])
        lastEventIdRef.current = newEvents[newEvents.length - 1].id
      }
      if (data.status && data.status !== session.status) {
        setSession((prev) => (prev ? { ...prev, status: data.status } : prev))
      }
    }

    fetchEvents()
    const interval = setInterval(fetchEvents, 2000)
    return () => clearInterval(interval)
  }, [session?.id, session?.status])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversationItems.length, sending])

  useEffect(() => {
    if (!awaitingAssistant) return
    const hasAssistantReply = events.some(
      (e) => e.role === 'assistant' && e.id > waitingSinceEventIdRef.current
    )
    if (hasAssistantReply) {
      setAwaitingAssistant(false)
    }
  }, [awaitingAssistant, events])

  useEffect(() => {
    const el = composerRef.current
    if (!el) return
    el.style.height = '0px'
    const next = Math.min(el.scrollHeight, 220)
    el.style.height = `${Math.max(next, 44)}px`
  }, [message])
  useEffect(() => {
    setActiveCommandIndex(0)
  }, [slashQuery])

  const ensureSession = async (): Promise<Session> => {
    if (session?.id && session.status === 'running') return session

    const res = await fetch(`/api/projects/${projectId}/chat-session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ runtime: 'agent-sdk' }),
    })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || '创建项目会话失败')
    }
    const created = await res.json()
    setSession(created)
    setChatState({
      project_id: projectId,
      session_id: created.id,
      status: created.status,
      last_active_at: new Date().toISOString(),
    })
    setEvents([])
    lastEventIdRef.current = 0
    return created
  }

  const sendMessageWithRetry = async (sessionId: number, content: string) => {
    for (let i = 0; i < 4; i += 1) {
      const res = await fetch(`/api/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: 'user', content }),
      })
      if (res.ok) return

      const err = await res.json().catch(() => ({}))
      const detail = err.detail || ''
      if (!detail.includes('No active agent')) {
        throw new Error(detail || '发送消息失败')
      }

      await new Promise((resolve) => setTimeout(resolve, 500))
    }
    throw new Error('会话初始化超时，请重试')
  }

  const closeCurrentSession = async () => {
    if (!session?.id) return
    const res = await fetch(`/api/sessions/${session.id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('关闭会话失败')
    setSession((prev) => (prev ? { ...prev, status: 'cancelled' } : prev))
    setChatState((prev) => (prev ? { ...prev, status: 'cancelled' } : prev))
    setAwaitingAssistant(false)
  }

  const handleSend = async () => {
    const text = message.trim()
    if (!text || sending) return
    setSending(true)
    setError('')
    try {
      if (text === '/close') {
        await closeCurrentSession()
        setMessage('')
        return
      }
      if (text === '/clear') {
        if (session?.id) {
          const clearRes = await fetch(`/api/sessions/${session.id}/events`, { method: 'DELETE' })
          if (!clearRes.ok) throw new Error('清空对话失败')
          setEvents([])
          lastEventIdRef.current = 0
          waitingSinceEventIdRef.current = 0
          setAwaitingAssistant(false)
        }
        setMessage('')
        return
      }
      if (text === '/init') {
        const activeSession = await ensureSession()
        const initInstruction = [
          '请在当前项目根目录生成并写入 CLAUDE.md 文件。',
          '要求：',
          '1. 使用中文。',
          '2. 包含项目简介、开发命令、代码规范、提交流程、常见问题。',
          '3. 如果文件已存在，请在保留原有效信息的基础上补全与重构结构。',
          '4. 完成后简要说明你写入了哪些章节。',
        ].join('\n')
        await sendMessageWithRetry(activeSession.id, initInstruction)
        waitingSinceEventIdRef.current = lastEventIdRef.current
        setAwaitingAssistant(true)
        setMessage('')
        return
      }
      const activeSession = await ensureSession()
      await sendMessageWithRetry(activeSession.id, text)
      setMessage('')
      waitingSinceEventIdRef.current = lastEventIdRef.current
      setAwaitingAssistant(true)
    } catch (e) {
      setError((e as Error).message || '发送失败')
      setAwaitingAssistant(false)
    } finally {
      setSending(false)
    }
  }

  const handleComposerKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (isCommandMenuOpen) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveCommandIndex((prev) => (prev + 1) % filteredCommands.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveCommandIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length)
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setMessage('')
        return
      }
      if ((e.key === 'Enter' || e.key === 'Tab') && !e.shiftKey) {
        e.preventDefault()
        const selected = filteredCommands[Math.min(activeCommandIndex, filteredCommands.length - 1)]
        if (selected) setMessage(`${selected.command} `)
        return
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!project) {
    return <div className="py-12 text-center text-muted-foreground">Project not found</div>
  }

  const effectiveStatus = chatState?.status || session?.status || 'idle'

  return (
    <div className="h-[calc(100dvh-5.5rem)] sm:h-[calc(100dvh-6.5rem)] flex flex-col gap-4 overflow-hidden">
      <div>
        <div>
          <Link href="/projects">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back to Projects
            </Button>
          </Link>
          <h1 className="mt-2 text-2xl font-bold tracking-tight">{project.name}</h1>
          <div className="mt-2 text-sm text-muted-foreground">
            <span className="font-mono text-xs">{project.local_path}</span>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 rounded-2xl bg-muted/30 shadow-sm border border-border/50 px-4 py-4 flex flex-col">
        <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-4">
          {conversationItems.length === 0 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                开始一个新对话，或使用快捷指令：
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  className="px-2.5 py-1.5 rounded-md bg-background text-xs text-muted-foreground hover:text-foreground border"
                  onClick={() => setMessage('/init')}
                >
                  /init
                </button>
                <button
                  className="px-2.5 py-1.5 rounded-md bg-background text-xs text-muted-foreground hover:text-foreground border"
                  onClick={() => setMessage('/close')}
                >
                  /close
                </button>
                <button
                  className="px-2.5 py-1.5 rounded-md bg-background text-xs text-muted-foreground hover:text-foreground border"
                  onClick={() => setMessage('/clear')}
                >
                  /clear
                </button>
                <button
                  className="px-2.5 py-1.5 rounded-md bg-background text-xs text-muted-foreground hover:text-foreground border"
                  onClick={() => setMessage('帮我快速了解这个项目结构')}
                >
                  项目结构
                </button>
              </div>
            </div>
          )}
          {conversationItems.map((item) => (
            <div key={item.id} className={`flex ${item.type === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-3 py-2.5 ${
                  item.type === 'user' ? 'bg-primary text-primary-foreground shadow-sm' : 'bg-background border border-border/60'
                }`}
              >
                <Markdown
                  content={item.text}
                  className={item.type === 'user' ? '[&_p]:text-primary-foreground' : '[&_p]:text-foreground'}
                />
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>

        <div className="mt-3 text-xs text-muted-foreground flex items-center gap-2">
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${(sending || awaitingAssistant) ? 'bg-blue-500 animate-pulse' : effectiveStatus === 'running' ? 'bg-emerald-500' : 'bg-gray-400'}`} />
          {(sending || awaitingAssistant) ? 'Agent 正在处理中...' : effectiveStatus === 'running' ? 'Agent 在线' : 'Agent 离线'}
        </div>

        {error && <p className="mt-3 text-sm text-red-500">{error}</p>}

        <div className="mt-3 pt-2 relative">
          {isCommandMenuOpen && (
            <div className="absolute left-0 right-0 bottom-full mb-2 rounded-xl border border-border/70 bg-background shadow-lg overflow-hidden z-20">
              {filteredCommands.map((item, idx) => (
                <button
                  key={item.command}
                  type="button"
                  className={`w-full px-3 py-2 text-left flex items-center justify-between ${
                    idx === activeCommandIndex ? 'bg-accent text-accent-foreground' : 'hover:bg-accent/60'
                  }`}
                  onClick={() => setMessage(`${item.command} `)}
                >
                  <span className="font-mono text-sm">{item.command}</span>
                  <span className="text-xs text-muted-foreground">{item.description}</span>
                </button>
              ))}
            </div>
          )}
          <div className="rounded-2xl border border-border/70 bg-background shadow-sm px-3 py-2">
            <div className="flex items-end gap-2">
              <Textarea
                ref={composerRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="给项目发消息...（Enter 发送，Shift+Enter 换行）"
                disabled={sending}
                rows={1}
                className="min-h-0 max-h-[220px] resize-none border-0 bg-transparent px-0 py-2 shadow-none focus-visible:ring-0"
              />
              <Button
                onClick={handleSend}
                disabled={sending || !message.trim()}
                size="icon"
                className="h-9 w-9 rounded-full"
              >
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </Button>
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground/80 text-right">
              <span>/init 初始化 CLAUDE.md · /clear 清空对话 · /close 关闭会话</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
