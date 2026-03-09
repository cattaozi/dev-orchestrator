'use client'

import ReactMarkdown from 'react-markdown'

interface MarkdownProps {
  content: string
  className?: string
}

export function Markdown({ content, className = '' }: MarkdownProps) {
  return (
    <div className={`text-sm ${className}`}>
      <ReactMarkdown
        components={{
          h1: ({children}) => <h1 className="text-lg font-bold mt-4 mb-2">{children}</h1>,
          h2: ({children}) => <h2 className="text-base font-semibold mt-3 mb-2">{children}</h2>,
          h3: ({children}) => <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>,
          p: ({children}) => <p className="text-sm text-muted-foreground">{children}</p>,
          ul: ({children}) => <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">{children}</ul>,
          ol: ({children}) => <ol className="list-decimal list-inside text-sm text-muted-foreground space-y-1">{children}</ol>,
          li: ({children}) => <li className="text-sm text-muted-foreground">{children}</li>,
          code: ({children}) => <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
          pre: ({children}) => <pre className="bg-muted p-3 rounded-md overflow-x-auto text-xs font-mono mt-2 mb-2">{children}</pre>,
          blockquote: ({children}) => <blockquote className="border-l-2 border-muted-foreground pl-3 italic text-sm text-muted-foreground">{children}</blockquote>,
          a: ({href, children}) => <a href={href} className="text-blue-500 hover:underline text-sm">{children}</a>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
