'use client'

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import Link from "next/link"
import { ArrowLeft, Loader2, Calendar, Play, Pencil, Trash2, Folder, X, Check, MoreVertical, Trash, RefreshCw, XCircle } from "lucide-react"

interface Issue {
  id: number
  project_id: number
  title: string
  content: string
  status: string
  worktree?: string
  branch?: string
  worktree_state?: string
  branch_state?: string
  created_at: string
}

interface Project {
  id: number
  name: string
}

interface NextWorker {
  worker_id: number
  worker_name: string
  emoji: string
  agent_type: string
  prompt_template: string
  next_status: string
}

interface ProjectWorker {
  id: number
  project_id: number
  worker_id: number
  worker_name: string
  emoji: string
  agent_type: string
  custom_prompt_template: string
}

interface Worker {
  id: number
  name: string
  emoji: string
  agent_type: string
  prompt_template: string
  is_builtin: boolean
}

export default function IssueDetailPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = Number(params.id)
  const issueId = Number(params.issueId)

  const [issue, setIssue] = useState<Issue | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState("")
  const [editStatus, setEditStatus] = useState("")
  const [editContent, setEditContent] = useState("")
  const [saving, setSaving] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [startingWork, setStartingWork] = useState(false)
  const [closing, setClosing] = useState(false)
  const [nextWorker, setNextWorker] = useState<NextWorker | null>(null)
  const [projectWorkers, setProjectWorkers] = useState<ProjectWorker[]>([])
  const [systemWorkers, setSystemWorkers] = useState<Worker[]>([])
  const [selectedWorkerId, setSelectedWorkerId] = useState<number | null>(null)
  const [sessions, setSessions] = useState<any[]>([])
  const [initialized, setInitialized] = useState(false)
  const [initializing, setInitializing] = useState(false)
  // Session deletion
  const [showSessionDeleteDialog, setShowSessionDeleteDialog] = useState(false)
  const [sessionToDelete, setSessionToDelete] = useState<any>(null)
  const [deletingSession, setDeletingSession] = useState(false)
  // Clear all sessions
  const [showClearSessionsDialog, setShowClearSessionsDialog] = useState(false)
  const [clearingSessions, setClearingSessions] = useState(false)
  // Delete worktree/branch
  const [showDeleteWorktreeDialog, setShowDeleteWorktreeDialog] = useState(false)
  const [deletingWorktree, setDeletingWorktree] = useState(false)
  const [showDeleteBranchDialog, setShowDeleteBranchDialog] = useState(false)
  const [deletingBranch, setDeletingBranch] = useState(false)

  // Auto-initialize project workers from system workers if not already done
  useEffect(() => {
    // Fetch both system workers and project workers in parallel
    Promise.all([
      fetch('/api/workers').then(res => res.json()).catch(() => []),
      fetch(`/api/projects/${projectId}/workers`).then(res => res.json()).catch(() => [])
    ]).then(([systemWorkersData, projectWorkersData]) => {
      setSystemWorkers(Array.isArray(systemWorkersData) ? systemWorkersData : [])
      setProjectWorkers(Array.isArray(projectWorkersData) ? projectWorkersData : [])
    })
  }, [projectId])

  // Auto-create project workers when system workers are loaded
  useEffect(() => {
    // Only initialize when: projectWorkers is empty, systemWorkers loaded, not already initializing, and not already initialized
    if (projectWorkers.length === 0 && systemWorkers.length > 0 && !initialized && !initializing) {
      setInitializing(true)
      // Auto-create project workers from system workers
      Promise.all(
        systemWorkers.map(worker =>
          fetch(`/api/projects/${projectId}/workers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              project_id: projectId,
              worker_id: worker.id,
              custom_prompt_template: ''
            })
          })
        )
      ).then(() => {
        // Refresh project workers after creation
        fetch(`/api/projects/${projectId}/workers`)
          .then(res => res.json())
          .then(data => {
            setProjectWorkers(Array.isArray(data) ? data : [])
            setInitialized(true)
          })
          .catch(() => {
            // If fetch fails, still mark as initialized to avoid infinite loop
            setInitialized(true)
          })
      }).catch(() => {
        // If creation fails, mark as initialized to avoid infinite retry
        setInitialized(true)
      }).finally(() => {
        setInitializing(false)
      })
    }
  }, [projectWorkers.length, systemWorkers.length, projectId, initialized, initializing])

  useEffect(() => {
    Promise.all([
      fetch(`/api/projects/${projectId}`).then(res => res.json()),
      fetch(`/api/projects/${projectId}/issues/${issueId}`).then(res => res.json())
    ])
      .then(([projectData, issueData]) => {
        setProject(projectData)
        setIssue(issueData)
        setLoading(false)
      })
      .catch(() => setLoading(false))

    // Fetch next worker info
    fetch(`/api/projects/${projectId}/issues/${issueId}/next-worker`)
      .then(res => res.json())
      .then(data => {
        if (!data.error) {
          setNextWorker(data)
          setSelectedWorkerId(data.worker_id)
        }
      })
      .catch(() => {})

    // Fetch sessions for this issue
    fetch(`/api/sessions`)
      .then(res => res.json())
      .then(data => {
        const issueSessions = Array.isArray(data) ? data.filter((s: any) => s.issue_id === issueId) : []
        setSessions(issueSessions)
      })
      .catch(() => {})
  }, [projectId, issueId])

  const startEdit = () => {
    if (issue) {
      setEditTitle(issue.title || "")
      setEditContent(issue.content || "")
      setEditStatus(issue.status)
      setEditing(true)
    }
  }

  const cancelEdit = () => {
    setEditing(false)
    setEditTitle("")
    setEditContent("")
  }

  const handleSave = async () => {
    if (!issue) return
    setSaving(true)
    try {
      const res = await fetch(`/api/projects/${projectId}/issues/${issueId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editTitle, content: editContent, status: editStatus })
      })
      if (res.ok) {
        setIssue({ ...issue, title: editTitle, content: editContent, status: editStatus })
        setEditing(false)
      } else {
        alert('Failed to save issue')
      }
    } catch {
      alert('Failed to save issue')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = () => {
    setShowDeleteDialog(true)
  }

  const confirmDelete = async () => {
    setDeleting(true)
    try {
      const res = await fetch(`/api/projects/${projectId}/issues/${issueId}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        router.push(`/projects/${projectId}`)
      } else {
        alert('Failed to delete issue')
      }
    } catch {
      alert('Failed to delete issue')
    } finally {
      setDeleting(false)
      setShowDeleteDialog(false)
    }
  }

  const confirmDeleteSession = async () => {
    if (!sessionToDelete) return
    setDeletingSession(true)
    try {
      const res = await fetch(`/api/sessions/${sessionToDelete.id}/data`, {
        method: 'DELETE'
      })
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== sessionToDelete.id))
        setShowSessionDeleteDialog(false)
        setSessionToDelete(null)
      } else {
        alert('Failed to delete session')
      }
    } catch {
      alert('Failed to delete session')
    } finally {
      setDeletingSession(false)
    }
  }

  const confirmClearSessions = async () => {
    setClearingSessions(true)
    try {
      // 直接删除每个 session（delete_session_data 会清理 worktree、branch、events 和 session 记录）
      for (const session of sessions) {
        await fetch(`/api/sessions/${session.id}/data`, { method: 'DELETE' })
      }
      setSessions([])
      setShowClearSessionsDialog(false)
    } catch {
      alert('Failed to clear sessions')
    } finally {
      setClearingSessions(false)
    }
  }

  const handleDeleteWorktree = async () => {
    if (!issue?.worktree) return
    setDeletingWorktree(true)
    try {
      const res = await fetch(`/api/projects/${projectId}/issues/${issueId}/worktree`, {
        method: 'DELETE'
      })
      if (res.ok) {
        setIssue(prev => prev ? { ...prev, worktree: undefined, worktree_state: undefined } : null)
        setShowDeleteWorktreeDialog(false)
      } else {
        const data = await res.json()
        alert(data.detail || 'Failed to delete worktree')
      }
    } catch {
      alert('Failed to delete worktree')
    } finally {
      setDeletingWorktree(false)
    }
  }

  const handleDeleteBranch = async () => {
    if (!issue?.branch) return
    setDeletingBranch(true)
    try {
      const res = await fetch(`/api/projects/${projectId}/issues/${issueId}/branch`, {
        method: 'DELETE'
      })
      if (res.ok) {
        setIssue(prev => prev ? { ...prev, branch: undefined, branch_state: undefined } : null)
        setShowDeleteBranchDialog(false)
      } else {
        const data = await res.json()
        alert(data.detail || 'Failed to delete branch')
      }
    } catch {
      alert('Failed to delete branch')
    } finally {
      setDeletingBranch(false)
    }
  }

  const handleStartWork = async () => {
    if (!selectedWorkerId) return
    setStartingWork(true)
    try {
      // Get worker info to determine next_status based on issue status
      const currentWorker = projectWorkers.find(pw => pw.worker_id === selectedWorkerId)
      let nextStatus = 'in_progress'
      if (issue?.status === 'need_review') {
        nextStatus = 'need_test'
      } else if (issue?.status === 'need_test') {
        nextStatus = 'done'
      }

      const res = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issue_id: issueId, worker_id: selectedWorkerId, runtime: 'agent-sdk' })
      })
      if (res.ok) {
        const session = await res.json()
        // Update issue status to next_status
        setIssue(prev => prev ? { ...prev, status: nextStatus } : null)
        // Refresh next worker
        const newWorkerRes = await fetch(`/api/projects/${projectId}/issues/${issueId}/next-worker`)
        const newWorkerData = await newWorkerRes.json()
        if (!newWorkerData.error) {
          setNextWorker(newWorkerData)
        }
        // Refresh sessions list
        const sessionsRes = await fetch('/api/sessions')
        const sessionsData = await sessionsRes.json()
        const issueSessions = Array.isArray(sessionsData) ? sessionsData.filter((s: any) => s.issue_id === issueId) : []
        setSessions(issueSessions)
      } else {
        const data = await res.json()
        alert(data.detail || 'Failed to start work')
      }
    } catch {
      alert('Failed to start work')
    } finally {
      setStartingWork(false)
    }
  }

  const handleCloseIssue = async (reopen: boolean = false) => {
    setClosing(true)
    try {
      let newStatus: string
      if (reopen) {
        newStatus = 'pending'
      } else {
        // Advance to next status based on current status
        switch (issue?.status) {
          case 'pending':
          case 'in_progress':
            newStatus = 'need_review'
            break
          case 'need_review':
            newStatus = 'need_test'
            break
          case 'need_test':
            newStatus = 'done'
            break
          default:
            newStatus = 'done'
        }
      }

      const res = await fetch(`/api/projects/${projectId}/issues/${issueId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      })
      if (res.ok) {
        setIssue(prev => prev ? { ...prev, status: newStatus } : null)
        // Refresh next worker
        const newWorkerRes = await fetch(`/api/projects/${projectId}/issues/${issueId}/next-worker`)
        const newWorkerData = await newWorkerRes.json()
        if (!newWorkerData.error) {
          setNextWorker(newWorkerData)
        }
      } else {
        alert(reopen ? 'Failed to reopen issue' : 'Failed to advance issue')
      }
    } catch {
      alert(reopen ? 'Failed to reopen issue' : 'Failed to advance issue')
    } finally {
      setClosing(false)
    }
  }

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'done': return 'bg-green-500 text-white hover:bg-green-600'
      case 'in_progress': return 'bg-blue-500 text-white hover:bg-blue-600'
      case 'need_review': return 'bg-yellow-500 text-white hover:bg-yellow-600'
      case 'need_test': return 'bg-purple-500 text-white hover:bg-purple-600'
      case 'failed': return 'bg-red-500 text-white hover:bg-red-600'
      default: return 'bg-gray-400 text-white hover:bg-gray-500'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'done': return 'Done'
      case 'in_progress': return 'In Progress'
      case 'need_review': return 'Need Review'
      case 'need_test': return 'Need Test'
      case 'failed': return 'Failed'
      default: return 'Pending'
    }
  }

  // Get start button config based on issue status
  const getStartConfig = () => {
    if (!issue) return null
    const status = issue.status

    if (status === 'done' || status === 'failed') return null

    let label = ''
    let workerType = ''

    switch (status) {
      case 'pending':
      case 'in_progress':
        label = '解决此issue'
        workerType = 'Developer'
        break
      case 'need_review':
        label = '审核此issue'
        workerType = 'Reviewer'
        break
      case 'need_test':
        label = '测试此issue'
        workerType = 'Tester'
        break
      default:
        return null
    }

    // Filter workers by type and sort by id descending (newest first)
    const availableWorkers = projectWorkers
      .filter(pw => pw.worker_name.includes(workerType))
      .sort((a, b) => b.id - a.id)

    if (availableWorkers.length === 0) return null

    return { label, workers: availableWorkers }
  }

  const startConfig = getStartConfig()

  // Set default selected worker when config changes
  useEffect(() => {
    if (startConfig && startConfig.workers.length > 0) {
      setSelectedWorkerId(startConfig.workers[0].worker_id)
    }
  }, [startConfig])

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (!issue || !project) {
    return (
      <div className="text-center py-10">
        <p>Issue not found</p>
        <Link href={`/projects/${projectId}`}>
          <Button variant="link" className="mt-2">Back to Project</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/projects/${projectId}`}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Project
          </Button>
        </Link>
      </div>

      {/* Issue Header */}
      <div className="flex items-center gap-4">
        <div className="flex-1">
          {editing ? (
            <div className="space-y-2">
              <Input
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="text-2xl font-bold h-auto py-2"
                placeholder="Issue title"
              />
              <select
                value={editStatus}
                onChange={(e) => setEditStatus(e.target.value)}
                className="h-8 text-sm border rounded px-2 bg-background"
              >
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="need_review">Need Review</option>
                <option value="need_test">Need Test</option>
                <option value="done">Done</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          ) : (
            <h1 className="text-2xl font-bold">{issue.title || 'Untitled Issue'}</h1>
          )}
          <div className="flex items-center gap-4 text-sm text-muted-foreground mt-2">
            <span className="font-mono">#{issue.id}</span>
            <Badge className={getStatusBadgeClass(issue.status)}>
              {getStatusText(issue.status)}
            </Badge>
            <Link href={`/projects/${projectId}`} className="flex items-center gap-1 hover:text-foreground">
              <Folder className="h-4 w-4" />
              <span>{project.name}</span>
            </Link>
            <div className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              <span>{formatDateTime(issue.created_at)}</span>
            </div>
          </div>
        </div>
        <div className="relative flex items-center gap-2">
          {startConfig && startConfig.workers.length > 0 && !editing && (
            <Button
              size="sm"
              className="bg-primary text-primary-foreground hover:bg-primary/90"
              onClick={() => {
                setSelectedWorkerId(startConfig.workers[0].worker_id)
                handleStartWork()
              }}
              disabled={startingWork}
            >
              {startingWork ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-1" />
              )}
              {startingWork ? '执行中...' : startConfig.label}
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => setShowMenu(!showMenu)}>
            <MoreVertical className="h-4 w-4" />
          </Button>
          {showMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
              <div className="absolute right-0 top-full mt-1 z-20 bg-background border rounded-md shadow-lg py-1 min-w-[120px]">
                <button
                  onClick={() => { startEdit(); setShowMenu(false) }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-accent"
                >
                  <Pencil className="h-3 w-3" />
                  Edit
                </button>
                {sessions.length > 0 && (
                  <button
                    onClick={() => { setShowMenu(false); setShowClearSessionsDialog(true) }}
                    className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-accent"
                  >
                    <RefreshCw className="h-3 w-3" />
                    清理会话 ({sessions.length})
                  </button>
                )}
                <button
                  onClick={() => { handleDelete(); setShowMenu(false) }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-accent text-red-500"
                >
                  <Trash2 className="h-3 w-3" />
                  Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2">
        {editing ? (
          <>
            <Button variant="outline" size="sm" onClick={cancelEdit} disabled={saving}>
              <X className="h-3 w-3 mr-1" />
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Check className="h-3 w-3 mr-1" />}
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </>
        ) : (
          <>
            {issue?.status === 'done' && (
              <Button variant="outline" size="sm" onClick={() => handleCloseIssue(true)} disabled={closing}>
                {closing ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Play className="h-3 w-3 mr-1" />}
                {closing ? 'Reopening...' : 'Reopen'}
              </Button>
            )}
          </>
        )}
      </div>

      {/* Issue Content */}
      {issue.worktree && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-base">开发环境</CardTitle>
          </CardHeader>
          <CardContent className="py-2 space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Worktree:</span>
              <code className="bg-muted px-2 py-1 rounded text-xs">{issue.worktree}</code>
              <Badge variant={issue.worktree_state === 'exists' ? 'default' : 'outline'}>
                {issue.worktree_state || 'none'}
              </Badge>
              <button
                className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                onClick={() => setShowDeleteWorktreeDialog(true)}
                title="删除 Worktree"
              >
                <XCircle className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Branch:</span>
              <code className="bg-muted px-2 py-1 rounded text-xs">{issue.branch || 'none'}</code>
              {issue.branch && (
                <>
                  <Badge variant={issue.branch_state === 'pushed' ? 'default' : 'outline'}>
                    {issue.branch_state || 'local'}
                  </Badge>
                  <button
                    className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                    onClick={() => setShowDeleteBranchDialog(true)}
                    title="删除 Branch"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                  </button>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base">Description</CardTitle>
        </CardHeader>
        <CardContent className="py-2">
          {editing ? (
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full min-h-[200px] p-4 text-sm font-mono bg-muted rounded-md border-0 focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Issue description..."
            />
          ) : (
            <pre className="whitespace-pre-wrap text-sm font-mono bg-muted p-4 rounded-md">
              {issue.content || 'No description provided.'}
            </pre>
          )}
        </CardContent>
      </Card>

      {/* Sessions Section */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base">Sessions</CardTitle>
        </CardHeader>
        <CardContent className="py-2">
          {sessions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No sessions yet</p>
          ) : (
            <div className="space-y-2">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  className="flex items-center justify-between p-3 bg-muted rounded-md hover:bg-muted/80 transition-colors group"
                >
                  <Link
                    href={`/projects/${projectId}/issues/${issueId}/sessions/${session.id}`}
                    className="flex items-center gap-3 flex-1"
                  >
                    <Badge variant={session.status === 'running' ? 'default' : 'outline'}>
                      {session.status}
                    </Badge>
                    <span className="text-sm font-mono">{session.branch}</span>
                  </Link>
                  <button
                    className="p-1 opacity-0 group-hover:opacity-100 hover:bg-background rounded"
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      setSessionToDelete(session)
                      setShowSessionDeleteDialog(true)
                    }}
                  >
                    <MoreVertical className="h-4 w-4 text-muted-foreground" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Session Confirmation Dialog */}
      <Dialog open={showSessionDeleteDialog} onOpenChange={(open) => {
        setShowSessionDeleteDialog(open)
        if (!open) setSessionToDelete(null)
      }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>删除 Session</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            确定要删除 Session "{sessionToDelete?.branch}" 吗？这将删除 Session 数据、相关事件、worktree 和分支。
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSessionDeleteDialog(false)} disabled={deletingSession}>
              取消
            </Button>
            <Button variant="destructive" onClick={confirmDeleteSession} disabled={deletingSession}>
              {deletingSession ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  删除中...
                </>
              ) : (
                '删除'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Clear Sessions Confirmation Dialog */}
      <Dialog open={showClearSessionsDialog} onOpenChange={setShowClearSessionsDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>清理会话</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            确定要清理该 Issue 下的所有 {sessions.length} 个 Session 吗？这将删除所有 Session 数据、事件、worktree 和分支。
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowClearSessionsDialog(false)} disabled={clearingSessions}>
              取消
            </Button>
            <Button variant="destructive" onClick={confirmClearSessions} disabled={clearingSessions}>
              {clearingSessions ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  清理中...
                </>
              ) : (
                '清理'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Issue Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Issue</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">Are you sure you want to delete this issue? This action cannot be undone.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleting}>
              {deleting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                'Delete'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Worktree Confirmation Dialog */}
      <Dialog open={showDeleteWorktreeDialog} onOpenChange={setShowDeleteWorktreeDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>删除 Worktree</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            确定要删除 Worktree <code className="bg-muted px-1 rounded">{issue?.worktree}</code> 吗？
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteWorktreeDialog(false)} disabled={deletingWorktree}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDeleteWorktree} disabled={deletingWorktree}>
              {deletingWorktree ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  删除中...
                </>
              ) : (
                '删除'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Branch Confirmation Dialog */}
      <Dialog open={showDeleteBranchDialog} onOpenChange={setShowDeleteBranchDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>删除 Branch</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            确定要删除分支 <code className="bg-muted px-1 rounded">{issue?.branch}</code> 吗？
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteBranchDialog(false)} disabled={deletingBranch}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDeleteBranch} disabled={deletingBranch}>
              {deletingBranch ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  删除中...
                </>
              ) : (
                '删除'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}