// Message types for parsing Claude Agent events

export type MessageType =
  | 'thinking'
  | 'text'
  | 'tool_use'
  | 'tool_result'
  | 'system_reminder'
  | 'todo_item'
  | 'persisted_output'
  | 'unknown'

export interface ParsedMessage {
  id: string
  type: MessageType
  raw: string
  // ThinkingBlock
  thinking?: string
  signature?: string
  // TextBlock
  text?: string
  // ToolUseBlock
  toolId?: string
  toolName?: string
  toolInput?: string
  // ToolResultBlock
  toolUseId?: string
  resultContent?: string
  isError?: boolean
  // SystemReminder
  reminderText?: string
  // TodoItem
  todoContent?: string
  todoStatus?: string
  todoActiveForm?: string
  // PersistedOutput
  preview?: string
  filePath?: string
}

// Parse raw event content into structured messages
export function parseEventContent(content: string): ParsedMessage[] {
  const messages: ParsedMessage[] = []

  // Clean up escaped newlines
  const cleanContent = content.replace(/\\n/g, '\n').replace(/\\'/g, "'")

  // Try to extract multiple blocks from content
  // Pattern to match block names and their content
  const blockPatterns: Array<{
    type: MessageType
    regex: RegExp
    extract: (match: RegExpMatchArray) => Record<string, any>
  }> = [
    // ThinkingBlock(thinking='...', signature='...')
    {
      type: 'thinking' as MessageType,
      regex: /ThinkingBlock\s*\(\s*thinking\s*=\s*'([\s\S]*?)'\s*,\s*signature\s*=\s*'([^']*)'\s*\)/gi,
      extract: (match: RegExpMatchArray) => ({
        thinking: unescapeContent(match[1]),
        signature: match[2]
      })
    },
    // TextBlock(text='...')
    {
      type: 'text' as MessageType,
      regex: /TextBlock\s*\(\s*text\s*=\s*'([\s\S]*?)'\s*\)/gi,
      extract: (match: RegExpMatchArray) => ({
        text: unescapeContent(match[1])
      })
    },
    // ToolUseBlock(id='...', name='...', input={...})
    {
      type: 'tool_use' as MessageType,
      regex: /ToolUseBlock\s*\(\s*id\s*=\s*'([^']+)'\s*,\s*name\s*=\s*'([^']+)'\s*,\s*input\s*=\s*(\{[\s\S]*?\})\s*\)/gi,
      extract: (match: RegExpMatchArray) => ({
        toolId: match[1],
        toolName: match[2],
        toolInput: match[3].replace(/'/g, '').replace(/\\n/g, '\n')
      })
    },
    // SystemReminder(text='...')
    {
      type: 'system_reminder' as MessageType,
      regex: /SystemReminder\s*\(\s*text\s*=\s*'([\s\S]*?)'\s*\)/gi,
      extract: (match: RegExpMatchArray) => ({
        reminderText: unescapeContent(match[1])
      })
    },
    // TodoItem(content='...', status='...', active_form='...')
    {
      type: 'todo_item' as MessageType,
      regex: /TodoItem\s*\(\s*content\s*=\s*'([\s\S]*?)'\s*,\s*status\s*=\s*'([^']*)'\s*,\s*active_form\s*=\s*'([^']*)'\s*\)/gi,
      extract: (match: RegExpMatchArray) => ({
        todoContent: unescapeContent(match[1]),
        todoStatus: match[2],
        todoActiveForm: match[3]
      })
    },
    // PersistedOutput(preview='...', file_path='...')
    {
      type: 'persisted_output' as MessageType,
      regex: /PersistedOutput\s*\(\s*preview\s*=\s*'([\s\S]*?)'\s*,\s*file_path\s*=\s*'([^']+)'\s*\)/gi,
      extract: (match: RegExpMatchArray) => ({
        preview: unescapeContent(match[1]),
        filePath: match[2]
      })
    }
  ]

  // Special handling for ToolResultBlock - handle both single and double quotes
  const toolResultRegex = /ToolResultBlock\(/gi
  let toolStart
  while ((toolStart = toolResultRegex.exec(cleanContent)) !== null) {
    // Find the position of , is_error= after this ToolResultBlock(
    const isErrorPos = cleanContent.indexOf(', is_error=', toolStart.index)
    if (isErrorPos === -1) continue

    // Find content=' or content=" after ToolResultBlock(
    const contentStartSingle = cleanContent.indexOf("content='", toolStart.index)
    const contentStartDouble = cleanContent.indexOf('content="', toolStart.index)

    // Use whichever comes first and is before is_error
    let contentStart = -1
    if (contentStartSingle !== -1 && (contentStartDouble === -1 || contentStartSingle < contentStartDouble)) {
      contentStart = contentStartSingle
    } else if (contentStartDouble !== -1) {
      contentStart = contentStartDouble
    }

    if (contentStart === -1 || contentStart > isErrorPos) continue

    // Extract content - find closing quote
    const quoteChar = cleanContent[contentStart + 7] // ' or "
    const contentValueStart = contentStart + 8 // content=' or content="
    let contentEnd = contentValueStart
    while (contentEnd < isErrorPos) {
      if (cleanContent[contentEnd] === quoteChar && cleanContent[contentEnd - 1] !== '\\') break
      contentEnd++
    }
    const rawContent = cleanContent.slice(contentValueStart, contentEnd)

    // Extract tool_use_id before content=
    const beforeContent = cleanContent.slice(toolStart.index, contentStart)
    const toolUseIdMatch = beforeContent.match(/tool_use_id\s*=\s*'([^']+)'/)

    // Extract is_error value
    const isErrorValue = cleanContent.slice(isErrorPos + 11, isErrorPos + 15).toLowerCase()

    messages.push({
      id: `tool_result-${toolStart.index}`,
      type: 'tool_result' as MessageType,
      raw: cleanContent.slice(toolStart.index, isErrorPos + 15),
      toolUseId: toolUseIdMatch ? toolUseIdMatch[1] : '',
      resultContent: unescapeContent(rawContent),
      isError: isErrorValue === 'true'
    })
  }

  // Try each pattern
  for (const pattern of blockPatterns) {
    let match
    const regex = new RegExp(pattern.regex.source, 'gi')

    while ((match = regex.exec(cleanContent)) !== null) {
      const extracted = pattern.extract(match)
      messages.push({
        id: `${pattern.type}-${match.index}`,
        type: pattern.type,
        raw: match[0],
        ...extracted
      } as ParsedMessage)
    }
  }

  // Preserve the original block order in raw message.
  const getOffset = (id: string): number => {
    const idx = Number(id.split('-').pop())
    return Number.isFinite(idx) ? idx : 0
  }
  messages.sort((a, b) => getOffset(a.id) - getOffset(b.id))

  // If no blocks found, treat entire content as text
  if (messages.length === 0 && cleanContent.trim()) {
    messages.push({
      id: 'text-0',
      type: 'text',
      raw: cleanContent,
      text: cleanContent.trim()
    })
  }

  return messages
}

// Unescape content that may have been escaped
function unescapeContent(content: string): string {
  return content
    .replace(/\\n/g, '\n')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, '\\')
}

// Get display name for message type
export function getMessageTypeLabel(type: MessageType): string {
  const labels: Record<MessageType, string> = {
    thinking: '思考',
    text: '消息',
    tool_use: '工具调用',
    tool_result: '工具结果',
    system_reminder: '系统提醒',
    todo_item: '任务',
    persisted_output: '文件输出',
    unknown: '未知'
  }
  return labels[type] || '未知'
}

// Get icon for message type
export function getMessageTypeIcon(type: MessageType): string {
  const icons: Record<MessageType, string> = {
    thinking: '🧠',
    text: '💬',
    tool_use: '🔧',
    tool_result: '📤',
    system_reminder: '⚠️',
    todo_item: '📋',
    persisted_output: '📁',
    unknown: '❓'
  }
  return icons[type] || '❓'
}
