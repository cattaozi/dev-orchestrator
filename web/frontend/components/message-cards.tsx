'use client'

import { useState } from 'react'
import { ParsedMessage } from '@/lib/message-parser'
import { ChevronDown, ChevronRight, Terminal } from 'lucide-react'

// Thinking Block - AI thinking process (always expanded)
export function ThinkingCard({ message }: { message: ParsedMessage }) {
  return (
    <div className="my-1 pl-2 border-l border-zinc-700">
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">thinking</div>
      <pre className="mt-1 text-[13px] leading-6 text-zinc-400 whitespace-pre-wrap font-mono">
        {message.thinking}
      </pre>
    </div>
  )
}

// Text Block - message to user
export function TextCard({ message }: { message: ParsedMessage }) {
  if (!message.text) return null

  return (
    <div className="my-2">
      <div className="text-[13px] leading-6 text-zinc-100 whitespace-pre-wrap">
        {message.text}
      </div>
    </div>
  )
}

// Tool Use Block - calling a tool (simplified to one line)
export function ToolUseCard({ message }: { message: ParsedMessage }) {
  return (
    <div className="text-[13px] leading-6 text-zinc-300 my-1 font-mono">
      <span className="text-zinc-500">&gt; tool</span>{' '}
      <span className="text-zinc-200">{message.toolName}</span>
      {message.toolId && <span className="text-zinc-500"> #{message.toolId.slice(0, 6)}</span>}
    </div>
  )
}

// Tool Result Block - tool execution result
export function ToolResultCard({ message }: { message: ParsedMessage }) {
  const [expanded, setExpanded] = useState(false) // 默认收起
  const content = message.resultContent || ''
  const lines = content.split('\n')
  const isLong = lines.length > 10 || content.length > 500
  const isDiff = content.includes('@@') || content.includes('+++') || content.includes('---')

  // 计算 diff 统计
  let diffAdded = 0, diffDeleted = 0
  if (isDiff) {
    lines.forEach(line => {
      if (line.startsWith('+') && !line.startsWith('+++')) diffAdded++
      if (line.startsWith('-') && !line.startsWith('---')) diffDeleted++
    })
  }

  return (
    <div className="my-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-1 py-1 text-left hover:bg-zinc-900 rounded-sm"
      >
        <Terminal className={`h-3.5 w-3.5 ${message.isError ? 'text-red-400' : 'text-zinc-500'}`} />
        <span className={`text-[13px] font-medium ${message.isError ? 'text-red-300' : 'text-zinc-300'}`}>result</span>
        {message.isError && <span className="text-[11px] text-red-400 uppercase">error</span>}
        {isDiff && !expanded && (
          <>
            {diffAdded > 0 && <span className="text-xs text-emerald-400">+{diffAdded}</span>}
            {diffDeleted > 0 && <span className="text-xs text-red-400">-{diffDeleted}</span>}
          </>
        )}
        {!isDiff && isLong && !expanded && <span className="text-xs text-zinc-500 ml-auto">{lines.length} lines</span>}
        {expanded ? <ChevronDown className="h-3 w-3 ml-auto text-zinc-500" /> : <ChevronRight className="h-3 w-3 ml-auto text-zinc-500" />}
      </button>
      {expanded && (
        <div className="mt-1 ml-5 border-l border-zinc-700 pl-2">
          <pre className={`text-[13px] font-mono whitespace-pre-wrap ${message.isError ? 'text-red-300' : 'text-zinc-200'}`}>
            {isDiff ? (
              <div className="space-y-0">
                {content.split('\n').map((line, i) => (
                  <DiffLine key={i} line={line} />
                ))}
              </div>
            ) : (
              content
            )}
          </pre>
        </div>
      )}
    </div>
  )
}

// Diff line component - git standard colors (with background)
function DiffLine({ line }: { line: string }) {
  if (line.startsWith('+') && !line.startsWith('+++')) {
    return <div key={line} className="text-emerald-300">{line}</div>
  }
  if (line.startsWith('-') && !line.startsWith('---')) {
    return <div key={line} className="text-red-300">{line}</div>
  }
  if (line.startsWith('@@')) {
    return <div key={line} className="text-amber-300 font-semibold">{line}</div>
  }
  // diff header lines
  if (line.startsWith('diff ') || line.startsWith('index ') || line.startsWith('---') || line.startsWith('+++')) {
    return <div key={line} className="text-zinc-500">{line}</div>
  }
  return <div key={line} className="text-zinc-300">{line}</div>
}

// System Reminder Block
export function SystemReminderCard({ message }: { message: ParsedMessage }) {
  if (!message.reminderText) return null

  return (
    <div className="my-1 border-l border-amber-400/60 pl-2">
      <div className="text-[11px] uppercase tracking-wide text-amber-300">system</div>
      <div className="text-[13px] leading-6 text-amber-200 whitespace-pre-wrap">
        {message.reminderText}
      </div>
    </div>
  )
}

// Todo Item Block
export function TodoItemCard({ message }: { message: ParsedMessage }) {
  const statusIcon = message.todoStatus === 'completed' ? '✓' :
                     message.todoStatus === 'in_progress' ? '→' : '○'

  return (
    <div className="my-1 pl-2">
      <div className="flex items-center gap-2">
        <span className="text-sm text-zinc-500">{statusIcon}</span>
        <span className="text-sm text-zinc-300">todo</span>
        {message.todoStatus && (
          <span className={`text-sm ${
            message.todoStatus === 'completed' ? 'text-green-400' :
            message.todoStatus === 'in_progress' ? 'text-blue-400' : 'text-zinc-500'
          }`}>
            [{message.todoStatus}]
          </span>
        )}
      </div>
      <div className="pl-5">
        <div className="text-sm text-zinc-200">
          {message.todoContent}
        </div>
        {message.todoActiveForm && (
          <div className="text-sm text-zinc-500 mt-1">
            active: {message.todoActiveForm}
          </div>
        )}
      </div>
    </div>
  )
}

// Persisted Output Block - large file output
export function PersistedOutputCard({ message }: { message: ParsedMessage }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="my-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-1 py-1 hover:bg-zinc-900 rounded-sm transition-colors text-left"
      >
        <span className="text-xs uppercase tracking-wide text-zinc-500">file</span>
        <span className="text-sm font-mono text-zinc-300">output</span>
        {message.filePath && (
          <span className="text-sm text-zinc-500 ml-1">{message.filePath}</span>
        )}
        {expanded ? (
          <ChevronDown className="h-3 w-3 ml-auto text-zinc-500" />
        ) : (
          <ChevronRight className="h-3 w-3 ml-auto text-zinc-500" />
        )}
      </button>
      {expanded && (
        <div className="mt-1 ml-5 border-l border-zinc-700 pl-2">
          <pre className="text-sm text-zinc-200 font-mono whitespace-pre-wrap">
            {message.preview || '(no preview)'}
          </pre>
        </div>
      )}
    </div>
  )
}

// Unknown Block - fallback
export function UnknownCard({ message }: { message: ParsedMessage }) {
  return (
    <div className="my-1 pl-2">
      <pre className="text-sm text-zinc-400 whitespace-pre-wrap">
        {message.raw}
      </pre>
    </div>
  )
}

// Main component to render message based on type
export function MessageCard({ message }: { message: ParsedMessage }) {
  switch (message.type) {
    case 'thinking':
      return <ThinkingCard message={message} />
    case 'text':
      return <TextCard message={message} />
    case 'tool_use':
      return <ToolUseCard message={message} />
    case 'tool_result':
      return <ToolResultCard message={message} />
    case 'system_reminder':
      return <SystemReminderCard message={message} />
    case 'todo_item':
      return <TodoItemCard message={message} />
    case 'persisted_output':
      return <PersistedOutputCard message={message} />
    default:
      return <UnknownCard message={message} />
  }
}
