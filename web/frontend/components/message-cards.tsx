'use client'

import { useState } from 'react'
import { ParsedMessage } from '@/lib/message-parser'
import { Badge } from '@/components/ui/badge'
import { ChevronDown, ChevronRight, Terminal } from 'lucide-react'

// Thinking Block - AI thinking process (always expanded)
export function ThinkingCard({ message }: { message: ParsedMessage }) {
  return (
    <div className="border border-zinc-800 rounded my-1 overflow-hidden">
      <div className="flex items-center gap-2 px-2 py-1 bg-zinc-900/50 text-zinc-400">
        <span className="text-sm">🧠</span>
        <span className="text-sm font-mono">Thinking</span>
      </div>
      <div className="px-2 pb-2 border-t border-zinc-800">
        <pre className="text-sm text-zinc-300 whitespace-pre-wrap font-mono mt-2">
          {message.thinking}
        </pre>
      </div>
    </div>
  )
}

// Text Block - message to user
export function TextCard({ message }: { message: ParsedMessage }) {
  if (!message.text) return null

  return (
    <div className="my-2">
      <div className="text-sm text-zinc-100 whitespace-pre-wrap">
        {message.text}
      </div>
    </div>
  )
}

// Tool Use Block - calling a tool (simplified to one line)
export function ToolUseCard({ message }: { message: ParsedMessage }) {
  return (
    <div className="text-sm text-zinc-400 my-0.5">
      <span className="text-zinc-500">🔧</span>{' '}
      <span className="text-zinc-300">{message.toolName}</span>
      {message.toolId && <span className="text-zinc-600"> #{message.toolId.slice(0, 6)}</span>}
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
    <div className={`border rounded my-1 overflow-hidden ${
      message.isError ? 'border-red-900' : 'border-zinc-800'
    }`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className={`w-full flex items-center gap-2 px-2 py-1 hover:bg-zinc-900 transition-colors text-left ${
          message.isError ? 'bg-red-950/30' : ''
        }`}
      >
        <Terminal className={`h-3 w-3 ${message.isError ? 'text-red-400' : 'text-zinc-400'}`} />
        <span className={`text-sm font-mono ${message.isError ? 'text-red-300' : 'text-zinc-300'}`}>
          result
        </span>
        {message.isError && (
          <Badge variant="destructive" className="text-[10px] h-4">error</Badge>
        )}
        {/* 显示 diff 统计 */}
        {isDiff && !expanded && (
          <>
            {diffAdded > 0 && <span className="text-sm text-green-500">+{diffAdded}</span>}
            {diffDeleted > 0 && <span className="text-sm text-red-500">-{diffDeleted}</span>}
          </>
        )}
        {!isDiff && isLong && !expanded && (
          <span className="text-sm text-zinc-600 ml-auto">
            {lines.length} lines
          </span>
        )}
        {expanded ? (
          <ChevronDown className="h-3 w-3 ml-auto text-zinc-500" />
        ) : (
          <ChevronRight className="h-3 w-3 ml-auto text-zinc-500" />
        )}
      </button>
      {expanded && (
        <div className={`px-2 pb-2 border-t ${
          message.isError ? 'border-red-900 bg-red-950/20' :
          isDiff ? 'border-zinc-700 bg-zinc-900/50' : 'border-zinc-800'
        }`}>
          <pre className={`text-sm font-mono whitespace-pre-wrap mt-2 ${
            message.isError ? 'text-red-200' : 'text-zinc-300'
          }`}>
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
    return <div key={line} className="bg-green-900/30 text-green-400">{line}</div>
  }
  if (line.startsWith('-') && !line.startsWith('---')) {
    return <div key={line} className="bg-red-900/30 text-red-400">{line}</div>
  }
  if (line.startsWith('@@')) {
    return <div key={line} className="bg-yellow-900/30 text-yellow-400 font-semibold">{line}</div>
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
    <div className="border border-yellow-900 bg-yellow-950/30 rounded my-2">
      <div className="flex items-center gap-2 px-2 py-1 border-b border-yellow-900/50">
        <span className="text-sm">⚠️</span>
        <span className="text-sm text-yellow-400">System Reminder</span>
      </div>
      <div className="px-2 py-1">
        <div className="text-sm text-yellow-200 whitespace-pre-wrap">
          {message.reminderText}
        </div>
      </div>
    </div>
  )
}

// Todo Item Block
export function TodoItemCard({ message }: { message: ParsedMessage }) {
  const statusIcon = message.todoStatus === 'completed' ? '✓' :
                     message.todoStatus === 'in_progress' ? '→' : '○'

  return (
    <div className="border border-zinc-800 rounded my-1">
      <div className="flex items-center gap-2 px-2 py-1">
        <span className="text-sm text-zinc-500">{statusIcon}</span>
        <span className="text-sm text-zinc-400">Todo</span>
        {message.todoStatus && (
          <span className={`text-sm ${
            message.todoStatus === 'completed' ? 'text-green-500' :
            message.todoStatus === 'in_progress' ? 'text-blue-500' : 'text-zinc-500'
          }`}>
            [{message.todoStatus}]
          </span>
        )}
      </div>
      <div className="px-2 pb-1 border-t border-zinc-800">
        <div className="text-sm text-zinc-300">
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
  const isDiff = message.preview?.includes('@@') || message.preview?.includes('+++')

  return (
    <div className="border border-zinc-800 rounded my-1 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-2 py-1 hover:bg-zinc-900 transition-colors text-left"
      >
        <span className="text-sm text-zinc-400">📁</span>
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
        <div className="px-2 pb-2 border-t border-zinc-800">
          <pre className="text-sm text-zinc-300 font-mono whitespace-pre-wrap mt-2">
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
    <div className="border border-zinc-800 rounded my-1 p-2">
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
