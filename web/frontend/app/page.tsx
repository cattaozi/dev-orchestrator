'use client'

import { useEffect, useState } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Folder, ListTodo, PlayCircle, Activity, AlertTriangle } from "lucide-react"

interface DashboardSummary {
  stats: {
    total_projects: number
    running_projects: number
    running_services: number
    total_tasks: number
    done_tasks: number
    blocked_tasks: number
    in_progress_tasks: number
    total_sessions: number
    active_sessions: number
  }
  recent_tasks: Array<{
    id: number
    project_id: number
    project_name: string
    title: string
    status: string
    created_at: string | null
  }>
  recent_sessions: Array<{
    id: number
    project_id: number | null
    project_name: string
    task_id: number | null
    status: string
    started_at: string | null
  }>
}

const emptySummary: DashboardSummary = {
  stats: {
    total_projects: 0,
    running_projects: 0,
    running_services: 0,
    total_tasks: 0,
    done_tasks: 0,
    blocked_tasks: 0,
    in_progress_tasks: 0,
    total_sessions: 0,
    active_sessions: 0,
  },
  recent_tasks: [],
  recent_sessions: [],
}

export default function Home() {
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<DashboardSummary>(emptySummary)

  useEffect(() => {
    let active = true

    const loadSummary = async () => {
      try {
        const res = await fetch('/api/dashboard/summary')
        if (!res.ok) return
        const data = await res.json()
        if (active) {
          setSummary(data)
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    loadSummary()
    const timer = setInterval(loadSummary, 10000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  const stats = summary.stats

  return (
    <div className="space-y-6">
      <div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">个人 AI IDE 工作台：项目、任务、Session</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Link href="/projects" className="block">
        <Card className="hover:bg-accent/40 transition-colors cursor-pointer">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Folder className="h-4 w-4" />
              Projects
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{stats.total_projects}</div>
            <p className="text-xs text-muted-foreground mt-1">{stats.running_projects} running</p>
          </CardContent>
        </Card>
        </Link>

        <Link href="/projects" className="block">
        <Card className="hover:bg-accent/40 transition-colors cursor-pointer">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <PlayCircle className="h-4 w-4" />
              Services
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{stats.running_services}</div>
            <p className="text-xs text-muted-foreground mt-1">running processes</p>
          </CardContent>
        </Card>
        </Link>

        <Link href="/projects" className="block">
        <Card className="hover:bg-accent/40 transition-colors cursor-pointer">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <ListTodo className="h-4 w-4" />
              Tasks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{stats.total_tasks}</div>
            <p className="text-xs text-muted-foreground mt-1">{stats.done_tasks} done · {stats.in_progress_tasks} doing</p>
          </CardContent>
        </Card>
        </Link>

        <Link href="/sessions" className="block">
        <Card className="hover:bg-accent/40 transition-colors cursor-pointer">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Sessions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{stats.active_sessions}</div>
            <p className="text-xs text-muted-foreground mt-1">{stats.total_sessions} total</p>
          </CardContent>
        </Card>
        </Link>
      </div>

      {stats.blocked_tasks > 0 && (
        <Card className="border-amber-300">
          <CardContent className="py-3 flex items-center gap-2 text-sm">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            <span>{stats.blocked_tasks} blocked task(s) need attention.</span>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Tasks</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : summary.recent_tasks.length === 0 ? (
              <p className="text-sm text-muted-foreground">No tasks yet</p>
            ) : (
              summary.recent_tasks.map((task) => (
                <Link
                  key={task.id}
                  href={`/projects/${task.project_id}/issues/${task.id}`}
                  className="flex items-center justify-between text-sm border-b pb-2 last:border-b-0"
                >
                  <div className="min-w-0">
                    <p className="font-medium truncate">{task.title || `Task #${task.id}`}</p>
                    <p className="text-xs text-muted-foreground truncate">{task.project_name}</p>
                  </div>
                  <Badge variant="outline">{task.status}</Badge>
                </Link>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Sessions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : summary.recent_sessions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No sessions yet</p>
            ) : (
              summary.recent_sessions.map((session) => {
                const href =
                  session.project_id && session.task_id
                    ? `/projects/${session.project_id}/issues/${session.task_id}/sessions/${session.id}`
                    : `/sessions`
                return (
                  <Link
                    key={session.id}
                    href={href}
                    className="flex items-center justify-between text-sm border-b pb-2 last:border-b-0"
                  >
                    <div className="min-w-0">
                      <p className="font-medium truncate">Session #{session.id}</p>
                      <p className="text-xs text-muted-foreground truncate">{session.project_name}</p>
                    </div>
                    <Badge variant="outline">{session.status}</Badge>
                  </Link>
                )
              })
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
