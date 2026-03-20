'use client'

import Link from "next/link"
import { Rocket, User, Settings } from "lucide-react"
import { useState } from "react"

export function Nav() {
  const [showProfileMenu, setShowProfileMenu] = useState(false)

  return (
    <nav className="border-b">
      <div className="container mx-auto flex items-center justify-between h-14 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold text-lg">
          <Rocket className="h-5 w-5 text-primary" />
          <span className="hidden sm:inline">DevPilot</span>
        </Link>
        
        <div className="flex items-center gap-1 relative">
          <button
            className="h-8 w-8 rounded-full border flex items-center justify-center hover:bg-accent"
            onClick={() => setShowProfileMenu(!showProfileMenu)}
            aria-label="Profile menu"
          >
            <User className="h-4 w-4" />
          </button>

          {showProfileMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowProfileMenu(false)} />
              <div className="absolute right-0 top-10 z-20 min-w-[140px] rounded-md border bg-background shadow-lg py-1">
                <Link
                  href="/settings"
                  className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent"
                  onClick={() => setShowProfileMenu(false)}
                >
                  <Settings className="h-4 w-4" />
                  Settings
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}
