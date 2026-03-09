'use client'

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Rocket, Menu, X, Bot, Settings } from "lucide-react"
import { useState } from "react"

export function Nav() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <nav className="border-b">
      <div className="container mx-auto flex items-center justify-between h-14 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold text-lg">
          <Rocket className="h-5 w-5 text-primary" />
          <span className="hidden sm:inline">DevPilot</span>
        </Link>
        
        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-6">
          <Link href="/" className="text-sm font-medium hover:text-primary">
            Dashboard
          </Link>
          <Link href="/projects" className="text-sm font-medium hover:text-primary">
            Projects
          </Link>
          <Link href="/sessions" className="text-sm font-medium hover:text-primary">
            Sessions
          </Link>
          <Link href="/workers" className="text-sm font-medium hover:text-primary flex items-center gap-1">
            <Bot className="h-4 w-4" />
            Workers
          </Link>
          <Link href="/settings" className="text-sm font-medium hover:text-primary flex items-center gap-1">
            <Settings className="h-4 w-4" />
            Settings
          </Link>
        </div>

        {/* Mobile menu button */}
        <button 
          className="md:hidden p-2"
          onClick={() => setIsOpen(!isOpen)}
        >
          {isOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>

        {/* Mobile nav */}
        {isOpen && (
          <div className="absolute top-14 left-0 right-0 bg-background border-b p-4 md:hidden flex flex-col gap-4 z-50">
            <Link href="/" className="text-sm font-medium" onClick={() => setIsOpen(false)}>
              Dashboard
            </Link>
            <Link href="/projects" className="text-sm font-medium" onClick={() => setIsOpen(false)}>
              Projects
            </Link>
            <Link href="/sessions" className="text-sm font-medium" onClick={() => setIsOpen(false)}>
              Sessions
            </Link>
            <Link href="/workers" className="text-sm font-medium" onClick={() => setIsOpen(false)}>
              Workers
            </Link>
            <Link href="/settings" className="text-sm font-medium" onClick={() => setIsOpen(false)}>
              Settings
            </Link>
          </div>
        )}
      </div>
    </nav>
  )
}
