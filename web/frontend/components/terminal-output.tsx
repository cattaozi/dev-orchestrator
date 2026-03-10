'use client'

import { useEffect, useRef } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

interface TerminalOutputProps {
  content: string
  className?: string
}

export function TerminalOutput({ content, className = '' }: TerminalOutputProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const terminalRef = useRef<Terminal | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    // 创建终端实例
    const terminal = new Terminal({
      theme: {
        background: '#000000',
        foreground: '#cccccc',
        cursor: '#cccccc',
        selectionBackground: '#444444',
        black: '#000000',
        red: '#cd3131',
        green: '#0dbc79',
        yellow: '#e5e510',
        blue: '#2472c8',
        magenta: '#bc3fbc',
        cyan: '#11a8cd',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: '#f14c4c',
        brightGreen: '#23d18b',
        brightYellow: '#f5f543',
        brightBlue: '#3b8eea',
        brightMagenta: '#d670d6',
        brightCyan: '#29b8db',
        brightWhite: '#e5e5e5',
      },
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      fontSize: 13,
      lineHeight: 1.2,
      cursorBlink: false,
      disableStdin: true,
      rows: 10,
    })

    const fitAddon = new FitAddon()
    terminal.loadAddon(fitAddon)

    terminal.open(containerRef.current)
    fitAddon.fit()

    // 写入内容（xterm.js 会自动解析 ANSI 转义序列）
    terminal.write(content)

    terminalRef.current = terminal

    return () => {
      terminal.dispose()
    }
  }, [content])

  return (
    <div
      ref={containerRef}
      className={`xterm-container ${className}`}
      style={{ backgroundColor: '#000' }}
    />
  )
}
