'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useStore } from "@/lib/store"
import { useEffect } from "react"
import Link from "next/link"

export default function Home() {
  const { projects, sessions, fetchProjects, fetchSessions } = useStore()

  useEffect(() => {
    fetchProjects()
    fetchSessions()
  }, [])

  const runningSessions = sessions.filter(s => s.status === 'running')
  const totalIssues = sessions.length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of your AI-driven development projects
          </p>
        </div>
        <Link href="/projects">
          <Button>New Project</Button>
        </Link>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <Link href="/projects">
              <CardTitle className="text-sm font-medium hover:text-primary">Projects</CardTitle>
            </Link>
          </CardHeader>
          <CardContent>
            <Link href="/projects">
              <div className="text-2xl font-bold hover:text-primary">{projects.length}</div>
            </Link>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalIssues}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Running</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{runningSessions.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Sessions */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Sessions</CardTitle>
          <CardDescription>
            Latest agent execution sessions
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sessions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No sessions yet</p>
          ) : (
            <div className="space-y-4">
              {sessions.slice(0, 5).map((session) => (
                <div
                  key={session.id}
                  className="flex items-center justify-between border-b pb-4 last:border-0"
                >
                  <div className="space-y-1">
                    <p className="text-sm font-medium">
                      Issue #{session.issue_id}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Branch: {session.branch}
                    </p>
                  </div>
                  <Badge
                    variant={
                      session.status === 'running'
                        ? 'default'
                        : session.status === 'done'
                        ? 'success'
                        : session.status === 'failed'
                        ? 'destructive'
                        : 'secondary'
                    }
                  >
                    {session.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
