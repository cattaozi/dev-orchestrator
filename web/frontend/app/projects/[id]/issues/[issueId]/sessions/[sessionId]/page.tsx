'use client'

import { useEffect, useState, useRef, useMemo } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import Link from "next/link"
import { ArrowLeft, Loader2, Send, Circle, Square, X, ExternalLink, Trash2, MoreHorizontal, Info, User, Bot, ChevronDown, ChevronRight } from "lucide-react"
import { parseEventContent, ParsedMessage } from "@/lib/message-parser"
import { MessageCard } from "@/components/message-cards"

interface Session {
  id: number
  issue_id: number
  project_id: number
  branch: string
  worktree_path: string
  status: string
  agent_type: string
  worker_id: number
  runtime: string
  command: string
  prompt: string
  started_at: string
  completed_at: string | null
}

interface SessionEvent {
  id: number
  type: string
  role: string
  content: string
  tool_name: string
  tool_input: string
  data: unknown
  created_at: string
}

export default function SessionDetailPage() {
  const params = useParams()
  const projectId = Number(params.id)
  const issueId = Number(params.issueId)
  const sessionId = Number(params.sessionId)

  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [events, setEvents] = useState<SessionEvent[]>([])
  const [loadingEvents, setLoadingEvents] = useState(false)
  const [message, setMessage] = useState("")
  const [sending, setSending] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true) // 默认开启自动滚动
  const eventsEndRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const lastEventIdRef = useRef(0)

  // 点击菜单外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false)
      }
    }
    if (showMenu) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showMenu])

  // 用户主动滚动时取消自动滚动（但如果是滚动到底部则不取消）
  const handleScroll = () => {
    if (!containerRef.current || !autoScroll) return

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    const distanceToBottom = scrollHeight - scrollTop - clientHeight

    // 只有当用户滚动到中间位置（而不是在底部）时才取消自动滚动
    // 阈值设为 50px，意味着如果距离底部超过 50px，才认为是用户主动滚动
    if (distanceToBottom > 50) {
      setAutoScroll(false)
    }
  }

  // Track if new events were added (for scroll logic)
  const prevEventsLengthRef = useRef(0)

  // Auto-scroll to bottom only when autoScroll is enabled AND new events were added
  useEffect(() => {
    const newEventsAdded = events.length > prevEventsLengthRef.current
    prevEventsLengthRef.current = events.length

    if (autoScroll && newEventsAdded && eventsEndRef.current) {
      eventsEndRef.current.scrollIntoView({ behavior: "auto" })
    }
  }, [events, autoScroll])

  // Polling for agent-sdk/stream-json mode
  useEffect(() => {
    if (!session) return

    const fetchEvents = () => {
      const afterId = lastEventIdRef.current
      const url = afterId > 0
        ? `/api/sessions/${sessionId}/events?after_id=${afterId}`
        : `/api/sessions/${sessionId}/events`

      fetch(url)
        .then(res => res.json())
        .then(data => {
          const newEvents = data.events || []
          if (newEvents.length > 0) {
            // Append new events to existing ones
            setEvents(prev => [...prev, ...newEvents])
            // Update last event ID
            lastEventIdRef.current = newEvents[newEvents.length - 1].id
          }
          if (data.status !== session.status) {
            setSession(prev => prev ? { ...prev, status: data.status } : null)
          }
          setLoadingEvents(false)
        })
        .catch(console.error)
    }

    fetchEvents()
    const interval = setInterval(fetchEvents, 2000)
    return () => clearInterval(interval)
  }, [session, sessionId])

  useEffect(() => {
    fetch(`/api/sessions`)
      .then(res => res.json())
      .then(data => {
        const found = data.find((s: Session) => s.id === sessionId)
        setSession(found || null)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [sessionId])

  const sendMessage = async () => {
    if (!message.trim() || sending) return
    setSending(true)
    try {
      await fetch(`/api/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: message, role: 'user' })
      })
      setMessage("")
    } catch (err) {
      console.error("Failed to send message:", err)
    } finally {
      setSending(false)
    }
  }

  const handleStop = async () => {
    setStopping(true)
    try {
      await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
      setSession(prev => prev ? { ...prev, status: 'failed' } : null)
    } catch (err) {
      console.error("Failed to stop session:", err)
    } finally {
      setStopping(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm("确定要删除此 Session 吗？这将删除 Session 数据、相关事件、worktree 和分支。")) {
      return
    }
    setDeleting(true)
    try {
      await fetch(`/api/sessions/${sessionId}/data`, { method: 'DELETE' })
      // Redirect to issue page
      window.location.href = `/projects/${projectId}/issues/${issueId}`
    } catch (err) {
      console.error("Failed to delete session:", err)
      setDeleting(false)
    }
  }

  const formatDateTime = (dateStr: string) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Group events: tool_use + tool_result as one unit
  interface EventGroup {
    type: 'single' | 'tool'
    eventId: number
    toolName?: string
    toolInput?: string
    resultContent?: string
    resultError?: boolean
    text?: string
    thinking?: boolean
  }

  // Group events by combining tool_use with its tool_result
  const groupEvents = (events: SessionEvent[]): EventGroup[] => {
    const groups: EventGroup[] = []
    let i = 0

    while (i < events.length) {
      const event = events[i]
      const content = event.content || ''

      // Check if this is a thinking block
      if (content.includes('ThinkingBlock')) {
        groups.push({ type: 'single', eventId: event.id, thinking: true })
        i++
        continue
      }

      // Check if this is a tool use
      const toolUseMatch = content.match(/name='([^']+)'/)
      const toolIdMatch = content.match(/ToolUseBlock\(id='([^']+)'/)
      const toolInputMatch = content.match(/input=\{([^}]+)\}/)

      if (toolUseMatch && toolIdMatch) {
        const toolId = toolIdMatch[1]
        const toolName = toolUseMatch[1]
        const toolInput = toolInputMatch ? toolInputMatch[1].replace(/'/g, '').replace(/\\n/g, '\n') : ''

        // Look for the matching tool result in next events
        let resultContent = ''
        let resultError = false
        let j = i + 1

        while (j < events.length) {
          const nextContent = events[j].content || ''
          const nextToolIdMatch = nextContent.match(/tool_use_id='([^']+)'/)
          const nextToolResultMatch = nextContent.match(/content='((?:[^'\\]|\\.)*)'/)
          const nextErrorMatch = nextContent.match(/is_error=([^),]+)/)

          if (nextToolIdMatch && nextToolIdMatch[1] === toolId && nextContent.includes('ToolResultBlock')) {
            resultContent = nextToolResultMatch ? nextToolResultMatch[1].replace(/\\n/g, '\n').replace(/\\'/g, "'") : ''
            resultError = nextErrorMatch ? nextErrorMatch[1].includes('True') || nextErrorMatch[1].includes('true') : false
            j++ // consume the result
          } else if (nextContent.includes('ToolUseBlock') || nextContent.includes('ThinkingBlock')) {
            break // next tool or thinking starts
          } else {
            j++
          }
        }

        groups.push({
          type: 'tool',
          eventId: event.id,
          toolName,
          toolInput,
          resultContent,
          resultError
        })
        i = j
        continue
      }

      // Check for text block
      const textMatch = content.match(/TextBlock\(text='((?:[^'\\]|\\.)*)'\)/)
      if (textMatch) {
        const text = textMatch[1].replace(/\\n/g, '\n').replace(/\\'/g, "'")
        groups.push({ type: 'single', eventId: event.id, text })
        i++
        continue
      }

      // Fallback: treat as single
      const clean = content.replace(/\[ThinkingBlock\([^)]*\)\]/g, '')
        .replace(/\[TextBlock\([^)]*\)\]/g, '')
        .replace(/\[ToolUseBlock\([^)]*\)\]/g, '')
        .replace(/\[ToolResultBlock\([^)]*\)\]/g, '')
        .replace(/\\n/g, '\n')
        .trim()
      if (clean) {
        groups.push({ type: 'single', eventId: event.id, text: clean })
      }
      i++
    }

    return groups
  }

  // Clean line numbers like "1→" to just "1"
  const cleanLineNumbers = (content: string): string => {
    return content.replace(/^(\s*)(\d+)(→)/gm, '$1$2')
  }

  // Tool Group: Claude Code native style
  const ToolGroup = ({ toolName, toolInput, resultContent, resultError }: {
    toolName: string
    toolInput: string
    resultContent: string
    resultError?: boolean
  }) => {
    const [collapsed, setCollapsed] = useState(true)
    const hasResult = resultContent && resultContent.trim().length > 0
    const isLong = hasResult && (resultContent.split('\n').length > 5 || resultContent.length > 300)
    const isDiff = resultContent.includes('@@') || resultContent.includes('+++') || resultContent.includes('---')

    // Clean line numbers
    const cleanResult = cleanLineNumbers(resultContent)

    return (
      <div className="my-1 font-mono text-xs border rounded-md p-2 bg-background">
        {/* Tool header */}
        <div
          className="text-primary cursor-pointer hover:opacity-80 flex items-center gap-2"
          onClick={() => setCollapsed(!collapsed)}
        >
          <span className="text-muted-foreground">&gt;</span>
          <span className="font-medium">{toolName}</span>
          {hasResult && <span className="text-muted-foreground text-xs">{collapsed ? '(点击展开)' : '(点击收起)'}</span>}
        </div>

        {/* Tool result */}
        {hasResult && !collapsed && (
          <div className={`mt-2 p-2 rounded ${resultError ? 'bg-destructive/10' : 'bg-muted'}`}>
            {isDiff ? (
              <pre className="text-xs overflow-x-auto">
                {cleanResult.split('\n').map((line, i) => (
                  <DiffLine key={i} line={line} />
                ))}
              </pre>
            ) : (
              <pre className={`text-xs whitespace-pre-wrap ${resultError ? 'text-destructive' : 'text-muted-foreground'}`}>
                {cleanResult}
              </pre>
            )}
          </div>
        )}
        {hasResult && collapsed && isLong && (
          <div className="text-muted-foreground text-xs mt-1">
            [{cleanResult.split('\n').length} lines]
          </div>
        )}
      </div>
    )
  }

  // Diff line component
  const DiffLine = ({ line }: { line: string }) => {
    if (line.startsWith('+') && !line.startsWith('+++')) {
      return <div className="text-green-400">{line}</div>
    }
    if (line.startsWith('-') && !line.startsWith('---')) {
      return <div className="text-red-400">{line}</div>
    }
    if (line.startsWith('@@')) {
      return <div className="text-yellow-400 font-semibold">{line}</div>
    }
    return <div className="text-gray-500">{line}</div>
  }

  // Code block component with collapse and diff highlighting
  const CodeBlock = ({ content, isError }: { content: string; isError?: boolean }) => {
    const [collapsed, setCollapsed] = useState(true) // Default collapsed
    const cleanContent = cleanLineNumbers(content)
    const lines = cleanContent.split('\n')
    const isLong = lines.length > 5 || cleanContent.length > 300
    const isDiff = cleanContent.includes('@@') || cleanContent.includes('+++') || cleanContent.includes('---') || /^[+-].+/m.test(cleanContent)

    if (isLong || collapsed) {
      return (
        <div className="my-1">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={`text-xs opacity-70 hover:opacity-100 flex items-center gap-1 px-1 py-0.5 rounded ${
              isDiff ? 'bg-yellow-900/30' : isError ? 'bg-red-900/30' : 'bg-green-900/30'
            }`}
          >
            <span>{collapsed ? '▶' : '▼'}</span>
            {isDiff && <span className="text-yellow-400">diff</span>}
            <span>{lines.length} lines</span>
            {collapsed && <span className="text-gray-500">(click to expand)</span>}
          </button>
          {!collapsed && (
            <pre className={`mt-1 p-2 rounded overflow-x-auto text-xs max-h-[400px] overflow-y-auto ${
              isError ? 'bg-red-900/30 border border-red-900' : isDiff ? 'bg-yellow-900/20 border border-yellow-900/50' : 'bg-black/50 border border-green-900/30'
            }`}>
              <code>
                {isDiff ? (
                  lines.map((line, i) => <DiffLine key={i} line={line} />)
                ) : (
                  content
                )}
              </code>
            </pre>
          )}
        </div>
      )
    }

    // Short content - show inline with diff coloring
    if (isDiff) {
      return (
        <div className="my-1">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-xs text-yellow-400 opacity-70 hover:opacity-100"
          >
            ▼ diff ({lines.length} lines)
          </button>
          {!collapsed && (
            <pre className="mt-1 p-2 rounded overflow-x-auto text-xs bg-yellow-900/20 border border-yellow-900/50">
              <code>
                {lines.map((line, i) => <DiffLine key={i} line={line} />)}
              </code>
            </pre>
          )}
        </div>
      )
    }

    return <span className="whitespace-pre-wrap">{cleanContent}</span>
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (!session) {
    return (
      <div className="text-center py-10">
        <p>Session not found</p>
        <Link href={`/projects/${projectId}/issues/${issueId}`}>
          <Button variant="link" className="mt-2">Back to Issue</Button>
        </Link>
      </div>
    )
  }

  const isInteractive = session.runtime === "agent-sdk" || session.runtime === "stream-json"

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/projects/${projectId}/issues/${issueId}`}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Issue
          </Button>
        </Link>
      </div>

      {/* Title with date */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge variant={session.status === 'running' ? 'default' : 'outline'}>
            {session.status === 'running' && <Circle className="h-3 w-3 mr-1 fill-green-500 animate-pulse" />}
            {session.status}
          </Badge>
          <h1 className="text-xl font-bold font-mono">{session.branch}</h1>
          {session.runtime && (
            <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
              {session.runtime}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            {formatDateTime(session.created_at)}
          </span>
          {/* More actions dropdown */}
          <div className="relative" ref={menuRef}>
            <button
              className="p-1 hover:bg-muted rounded"
              onClick={() => setShowMenu(!showMenu)}
            >
              <MoreHorizontal className="h-5 w-5 text-muted-foreground" />
            </button>
            {showMenu && (
              <div className="absolute right-0 top-8 z-50 bg-background border rounded-md shadow-lg py-1 min-w-[120px]">
                <button
                  className="w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2"
                  onClick={() => {
                    setShowMenu(false)
                    setShowDetails(true)
                  }}
                >
                  <Info className="h-4 w-4" />
                  属性
                </button>
                <button
                  className="w-full px-3 py-2 text-left text-sm text-destructive hover:bg-muted flex items-center gap-2"
                  onClick={() => {
                    setShowMenu(false)
                    handleDelete()
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                  删除
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Details Dialog */}
      {showDetails && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={() => setShowDetails(false)}>
          <div className="bg-background rounded-lg shadow-lg p-6 max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">属性</h3>
              <button onClick={() => setShowDetails(false)} className="p-1 hover:bg-muted rounded">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Branch:</span>
                <span className="font-mono">{session.branch}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Worktree:</span>
                <span className="font-mono text-xs">{session.worktree_path}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Runtime:</span>
                <span>{session.runtime}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Agent:</span>
                <span>{session.agent_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status:</span>
                <Badge variant={session.status === 'running' ? 'default' : 'outline'}>
                  {session.status}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created:</span>
                <span>{formatDateTime(session.created_at)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Prompt:</span>
                <Link
                  href={`/projects/${projectId}/issues/${issueId}/sessions/${sessionId}/prompt`}
                  target="_blank"
                  className="text-primary hover:underline flex items-center gap-1"
                >
                  查看 <ExternalLink className="h-3 w-3" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Log Output */}
      <Card className="h-[60vh] flex flex-col">
        <CardHeader className="py-3 flex flex-row items-center justify-between">
          <CardTitle className="text-base">日志输出</CardTitle>
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="w-4 h-4 rounded cursor-pointer"
            />
            <span className="text-xs text-muted-foreground">自动滚动</span>
          </label>
        </CardHeader>
        <CardContent className="flex-1 overflow-hidden p-0 border-t">
          <div
            ref={containerRef}
            onScroll={handleScroll}
            className="h-full overflow-y-auto p-4 bg-black text-zinc-100 font-mono"
          >
            {events.length === 0 ? (
              <div className="text-center text-zinc-500 py-10">
                <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                <p>等待 Agent 响应...</p>
              </div>
            ) : (
              <div className="space-y-2">
                {events.map((event) => {
                  // Parse event content into messages
                  const messages = parseEventContent(event.content || '')
                  const isUser = event.role === 'user'

                  return (
                    <div
                      key={event.id}
                      className={`mb-2 ${isUser ? 'ml-auto max-w-[80%]' : ''}`}
                    >
                      {/* User message - special style */}
                      {isUser && (
                        <div className="border border-zinc-600 rounded px-2 py-1 bg-zinc-800/50">
                          <div className="text-sm text-zinc-100 whitespace-pre-wrap">
                            {event.content.replace(/\\n/g, '\n')}
                          </div>
                        </div>
                      )}

                      {/* Agent message - just cards */}
                      {!isUser && (
                        <div>
                          {(() => {
                            // 优先使用后端解析好的 data 字段
                            const data = event.data as Array<{
                              type: string
                              thinking?: string
                              signature?: string
                              text?: string
                              name?: string
                              id?: string
                              tool_use_id?: string
                              content?: string
                              is_error?: boolean
                              diff_stats?: { added: number; deleted: number }
                              line_count?: number
                              input?: Record<string, unknown>
                            }> | null

                            // 如果有解析好的 data，直接使用
                            if (data && data.length > 0) {
                              return data.map((block, idx) => (
                                <ParsedBlock key={`${event.id}-${idx}`} block={block} />
                              ))
                            }

                            // 后备：使用旧的解析方式
                            const rawContent = event.content.replace(/\\n/g, '\n')
                            const lines = rawContent.split('\n')
                            const isBlockFormat = rawContent.includes('[ToolUseBlock') || rawContent.includes('[ToolResultBlock')
                            const isJsonArrayContent = rawContent.match(/content=\[/)

                            if (isJsonArrayContent && lines.length > 2) {
                              return (
                                <CollapsedBlock
                                  content={rawContent}
                                  lineCount={lines.length}
                                />
                              )
                            }

                            if (messages.length > 0) {
                              return messages.map((msg, idx) => (
                                <div key={`${event.id}-${idx}`}>
                                  <MessageCard message={msg} />
                                </div>
                              ))
                            }

                            // 消息解析失败时，如果是块格式且超过2行，收缩显示
                            if (isBlockFormat && lines.length > 2) {
                              return (
                                <CollapsedBlock
                                  content={rawContent}
                                  lineCount={lines.length}
                                />
                              )
                            }

                            // 否则直接显示
                            return (
                              <pre className="whitespace-pre-wrap break-all text-sm text-zinc-300">
                                {rawContent}
                              </pre>
                          )
                        })()}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
            <div ref={eventsEndRef} />
          </div>
        </CardContent>
      </Card>

      {/* Message Input - Agent Intervention */}
      <div className="flex gap-2 items-center">
        <Input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={session.status === 'running' ? "输入消息来干预 Agent..." : "Session 已结束"}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && session.status === 'running' && sendMessage()}
          disabled={sending || session.status !== 'running'}
          className="flex-1 font-mono"
        />
        <Button onClick={sendMessage} disabled={sending || !message.trim() || session.status !== 'running'} size="sm">
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
        {session.status === 'running' && (
          <Button variant="destructive" size="sm" onClick={handleStop} disabled={stopping}>
            {stopping ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Square className="h-4 w-4 mr-1" />}
            中止
          </Button>
        )}
      </div>
    </div>
  )
}

// Collapsed block for long content - simple approach
function CollapsedBlock({ content, lineCount }: { content: string; lineCount: number }) {
  const [expanded, setExpanded] = useState(false)

  // 提取块类型和工具名
  const isToolUse = content.includes('[ToolUseBlock')
  const isToolResult = content.includes('[ToolResultBlock')

  // 尝试提取工具名
  let toolName = 'Tool'
  let toolId = ''
  const nameMatch = content.match(/name='([^']+)'/)
  const idMatch = content.match(/id='([^']+)'/)
  if (nameMatch) toolName = nameMatch[1]
  if (idMatch) toolId = idMatch[1].slice(0, 8)

  const icon = isToolUse ? '🔧' : isToolResult ? '📤' : '📄'

  return (
    <div className="border border-zinc-800 rounded my-1 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-2 py-1 hover:bg-zinc-900 transition-colors text-left"
      >
        <span className="text-sm text-zinc-400">{icon}</span>
        <span className="text-sm font-mono text-zinc-300">{toolName}</span>
        {toolId && <span className="text-sm text-zinc-600">#{toolId}</span>}
        <span className="text-sm text-green-500">+{lineCount}</span>
        {expanded ? (
          <ChevronDown className="h-3 w-3 ml-auto text-zinc-500" />
        ) : (
          <ChevronRight className="h-3 w-3 ml-auto text-zinc-500" />
        )}
      </button>
      {expanded && (
        <div className="px-2 pb-2 border-t border-zinc-800">
          <pre className="text-sm text-zinc-300 font-mono whitespace-pre-wrap">
            {content}
          </pre>
        </div>
      )}
    </div>
  )
}

// ParsedBlock - render blocks from backend parsed data
function ParsedBlock({ block }: { block: {
  type: string
  thinking?: string
  signature?: string
  text?: string
  name?: string
  id?: string
  tool_use_id?: string
  content?: string
  is_error?: boolean
  diff_stats?: { added: number; deleted: number }
  line_count?: number
  input?: Record<string, unknown>
} }) {
  switch (block.type) {
    case 'thinking':
      return (
        <div className="text-sm text-zinc-400 my-0.5">
          🧠 <span className="text-zinc-500">{block.thinking?.slice(0, 50)}...</span>
        </div>
      )
    case 'text':
      return (
        <div className="text-sm text-zinc-300 my-1 whitespace-pre-wrap">
          {block.text}
        </div>
      )
    case 'tool_use':
      return (
        <div className="text-sm text-zinc-400 my-0.5">
          🔧 <span className="text-zinc-300">{block.name}</span>
          {block.id && <span className="text-zinc-600"> #{block.id.slice(0, 6)}</span>}
          {block.line_count && <span className="text-green-500"> +{block.line_count}</span>}
        </div>
      )
    case 'tool_result':
      const isLong = (block.content?.split('\n').length || 0) > 3
      const isDiff = block.content?.includes('@@') || block.content?.includes('+++')
      return (
        <div className="text-sm text-zinc-400 my-0.5">
          📤 <span className="text-zinc-300">result</span>
          {block.is_error && <span className="text-red-500 ml-1">error</span>}
          {block.diff_stats && (
            <>
              <span className="text-green-500 ml-1">+{block.diff_stats.added}</span>
              {block.diff_stats.deleted > 0 && <span className="text-red-500 ml-1">-{block.diff_stats.deleted}</span>}
            </>
          )}
          {!block.diff_stats && isLong && <span className="text-zinc-600 ml-1">{block.content?.split('\n').length} lines</span>}
        </div>
      )
    case 'system_reminder':
      return (
        <div className="text-sm text-yellow-400 my-1">
          ⚠️ {block.text}
        </div>
      )
    default:
      return null
  }
}
