'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useStore } from "@/lib/store"
import { useEffect } from "react"
import { Terminal, Play, Square } from "lucide-react"

export default function SessionsPage() {
  const { sessions, fetchSessions, loading } = useStore()

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'running':
        return 'default'
      case 'done':
        return 'success'
      case 'failed':
        return 'destructive'
      default:
        return 'secondary'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Sessions</h1>
          <p className="text-muted-foreground">
            Monitor running agent sessions
          </p>
        </div>
        <Button variant="outline" onClick={() => fetchSessions()}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="text-center py-10 text-muted-foreground">Loading...</div>
      ) : sessions.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-10">
            <Terminal className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No sessions yet</p>
            <p className="text-sm text-muted-foreground mt-2">
              Start a project to see sessions here
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {sessions.map((session) => (
            <Card key={session.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Terminal className="h-4 w-4" />
                    Session #{session.id}
                  </CardTitle>
                  <Badge variant={getStatusVariant(session.status)}>
                    {session.status}
                  </Badge>
                </div>
                <CardDescription>
                  Task #{session.issue_id ?? '-'} • {session.agent_type} • {session.runtime}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Branch:</span>
                    <span className="font-mono">{session.branch}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Worktree:</span>
                    <span className="font-mono text-xs">{session.worktree_path}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Created:</span>
                    <span>{new Date(session.created_at).toLocaleString()}</span>
                  </div>
                </div>
                
                {session.status === 'running' && (
                  <div className="flex gap-2 mt-4">
                    <Button variant="outline" size="sm">
                      <Play className="mr-2 h-4 w-4" />
                      View Logs
                    </Button>
                    <Button variant="destructive" size="sm">
                      <Square className="mr-2 h-4 w-4" />
                      Stop
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
