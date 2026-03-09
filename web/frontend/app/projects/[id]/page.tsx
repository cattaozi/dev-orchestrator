'use client'

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import Link from "next/link"
import { ArrowLeft, GitBranch, Folder, Plus, Loader2, ChevronRight, Pencil, Trash2, X, Check, FileText, Bot, MoreHorizontal } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Markdown } from "@/components/ui/markdown"

interface Project {
  id: number
  name: string
  description: string
  repo: string
  local_path: string
  status: string
}

interface PRD {
  id: number
  project_id: number
  title: string
  description: string
  status: string
}

interface Issue {
  id: number
  project_id: number
  repo_id: number
  title: string
  content?: string
  status: string
}

interface ProjectWorker {
  id: number
  project_id: number
  worker_id: number
  worker_name: string
  emoji: string
  agent_type: string
  custom_prompt_template: string
  created_at: string
}

interface Worker {
  id: number
  name: string
  agent_type: string
  prompt_template: string
}

export default function ProjectDetailPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = Number(params.id)

  const [project, setProject] = useState<Project | null>(null)
  const [prds, setPrds] = useState<PRD[]>([])
  const [issues, setIssues] = useState<Issue[]>([])
  const [projectWorkers, setProjectWorkers] = useState<ProjectWorker[]>([])
  const [systemWorkers, setSystemWorkers] = useState<Worker[]>([])
  const [loading, setLoading] = useState(true)
  const [readmeContent, setReadmeContent] = useState<string>("")
  const [readmeLoading, setReadmeLoading] = useState(false)

  // Dialog states
  const [showPrdDialog, setShowPrdDialog] = useState(false)
  const [showIssueDialog, setShowIssueDialog] = useState(false)
  const [showWorkerDialog, setShowWorkerDialog] = useState(false)
  const [editingWorker, setEditingWorker] = useState<ProjectWorker | null>(null)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [showMenu, setShowMenu] = useState(false)

  // Form states
  const [prdTitle, setPrdTitle] = useState("")
  const [prdVersion, setPrdVersion] = useState("v1.0")
  const [issueTitle, setIssueTitle] = useState("")
  const [issueContent, setIssueContent] = useState("")
  const [selectedWorkerId, setSelectedWorkerId] = useState<number | null>(null)
  const [customPrompt, setCustomPrompt] = useState("")
  const [savingWorker, setSavingWorker] = useState(false)

  // Edit form states
  const [editName, setEditName] = useState("")
  const [editDescription, setEditDescription] = useState("")
  const [saving, setSaving] = useState(false)
  const [initialized, setInitialized] = useState(false)
  const [initializing, setInitializing] = useState(false)

  // Auto-initialize project workers from system workers
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
        // Refresh project workers
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
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    // Fetch project
    fetch(`/api/projects/${projectId}`)
      .then(res => res.json())
      .then(data => {
        setProject(data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
    
    // Fetch PRDs
    fetch(`/api/projects/${projectId}/prds`)
      .then(res => res.json())
      .then(data => setPrds(Array.isArray(data) ? data : []))
      .catch(() => setPrds([]))

    // Fetch Issues
    fetch(`/api/projects/${projectId}/issues`)
      .then(res => res.json())
      .then(data => setIssues(Array.isArray(data) ? data : []))
      .catch(() => setIssues([]))

    // Fetch Project Workers
    fetch(`/api/projects/${projectId}/workers`)
      .then(res => res.json())
      .then(data => setProjectWorkers(Array.isArray(data) ? data : []))
      .catch(() => setProjectWorkers([]))

    // Fetch System Workers
    fetch('/api/workers')
      .then(res => res.json())
      .then(data => setSystemWorkers(Array.isArray(data) ? data : []))
      .catch(() => setSystemWorkers([]))
  }, [projectId])

  const handleAddPRD = async () => {
    await fetch(`/api/projects/${projectId}/prds`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, title: prdTitle, version: prdVersion })
    })
    // Refresh PRDs
    const res = await fetch(`/api/projects/${projectId}/prds`)
    const data = await res.json()
    setPrds(Array.isArray(data) ? data : [])
    setShowPrdDialog(false)
    setPrdTitle("")
    setPrdVersion("v1.0")
  }

  const handleAddIssue = async () => {
    await fetch(`/api/projects/${projectId}/issues`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, title: issueTitle, content: issueContent })
    })
    // Refresh Issues
    const res = await fetch(`/api/projects/${projectId}/issues`)
    const data = await res.json()
    setIssues(Array.isArray(data) ? data : [])
    setShowIssueDialog(false)
    setIssueContent("")
  }

  const openAddWorkerDialog = () => {
    setEditingWorker(null)
    setSelectedWorkerId(systemWorkers.length > 0 ? systemWorkers[0].id : null)
    setCustomPrompt("")
    setShowWorkerDialog(true)
  }

  const openEditWorkerDialog = (pw: ProjectWorker) => {
    setEditingWorker(pw)
    setSelectedWorkerId(pw.worker_id)
    setCustomPrompt(pw.custom_prompt_template)
    setShowWorkerDialog(true)
  }

  const handleSaveWorker = async () => {
    if (!selectedWorkerId) return
    setSavingWorker(true)
    try {
      const payload = {
        project_id: projectId,
        worker_id: selectedWorkerId,
        custom_prompt_template: customPrompt
      }

      let res
      if (editingWorker) {
        res = await fetch(`/api/projects/${projectId}/workers/${editingWorker.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ custom_prompt_template: customPrompt })
        })
      } else {
        res = await fetch(`/api/projects/${projectId}/workers`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
      }

      if (res.ok) {
        const res = await fetch(`/api/projects/${projectId}/workers`)
        const data = await res.json()
        setProjectWorkers(Array.isArray(data) ? data : [])
        setShowWorkerDialog(false)
      } else {
        alert('Failed to save worker')
      }
    } catch {
      alert('Failed to save worker')
    } finally {
      setSavingWorker(false)
    }
  }

  const handleDeleteWorker = async (pw: ProjectWorker) => {
    if (!confirm(`Remove worker "${pw.worker_name}" from this project?`)) return

    try {
      const res = await fetch(`/api/projects/${projectId}/workers/${pw.id}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        const res = await fetch(`/api/projects/${projectId}/workers`)
        const data = await res.json()
        setProjectWorkers(Array.isArray(data) ? data : [])
      } else {
        alert('Failed to remove worker')
      }
    } catch {
      alert('Failed to remove worker')
    }
  }

  // Fetch README when project is loaded
  useEffect(() => {
    if (!project) return
    setReadmeLoading(true)
    fetch(`/api/projects/${projectId}/readme`)
      .then(res => res.json())
      .then(data => {
        if (data.content) {
          setReadmeContent(data.content)
        }
      })
      .catch(() => {})
      .finally(() => setReadmeLoading(false))
  }, [project, projectId])

  const openEditDialog = () => {
    if (project) {
      setEditName(project.name)
      setEditDescription(project.description || "")
      setShowEditDialog(true)
    }
  }

  const handleSaveProject = async () => {
    setSaving(true)
    try {
      const res = await fetch(`/api/projects/${projectId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editName, description: editDescription.slice(0, 20) })
      })
      if (res.ok) {
        const data = await res.json()
        setProject(data)
        setShowEditDialog(false)
      } else {
        alert('Failed to save')
      }
    } catch {
      alert('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteProject = async () => {
    setDeleting(true)
    try {
      const res = await fetch(`/api/projects/${projectId}`, { method: 'DELETE' })
      if (res.ok) {
        router.push('/projects')
      } else {
        alert('Failed to delete')
      }
    } catch {
      alert('Failed to delete')
    } finally {
      setDeleting(false)
      setShowDeleteDialog(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (!project) {
    return (
      <div className="text-center py-10">
        <p>Project not found</p>
        <Link href="/projects">
          <Button variant="link" className="mt-2">Back to Projects</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/projects">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{project.name}</h1>
          {project.description && (
            <p className="text-sm text-muted-foreground mt-1">{project.description}</p>
          )}
        </div>
        <div className="relative">
          <Button size="sm" variant="ghost" onClick={() => setShowMenu(!showMenu)}>
            <MoreHorizontal className="h-4 w-4" />
          </Button>
          {showMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
              <div className="absolute right-0 top-full mt-1 z-20 bg-background border rounded-md shadow-lg py-1 min-w-[120px]">
                <button
                  onClick={() => { openEditDialog(); setShowMenu(false) }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-accent"
                >
                  <Pencil className="h-3 w-3" />
                  Edit
                </button>
                <button
                  onClick={() => { setShowDeleteDialog(true); setShowMenu(false) }}
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

      {/* Repo & Path - compact inline */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <div className="flex items-center gap-1">
          <GitBranch className="h-3 w-3" />
          <span className="font-mono text-xs">{project.repo}</span>
        </div>
        <div className="flex items-center gap-1">
          <Folder className="h-3 w-3" />
          <span className="font-mono text-xs">{project.local_path}</span>
        </div>
      </div>

      {/* Workers Row */}
      <div className="flex items-center gap-2 text-sm flex-wrap">
        <Bot className="h-4 w-4 text-muted-foreground" />
        {projectWorkers.length === 0 ? (
          <span className="text-sm text-muted-foreground">Initializing...</span>
        ) : (
          <>
            <button
              onClick={() => setShowWorkerDialog(true)}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-dashed border-muted-foreground hover:border-foreground hover:bg-accent transition-colors text-muted-foreground text-xs"
            >
              <Plus className="h-3 w-3" />
              <span>Add worker</span>
            </button>
            {projectWorkers.map(pw => (
              <Link
                key={pw.id}
                href={`/projects/${projectId}/workers/${pw.id}`}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-md hover:bg-accent transition-colors"
              >
                <span>{pw.emoji}</span>
                <span className="text-sm">{pw.worker_name}</span>
              </Link>
            ))}
          </>
        )}
      </div>

      {/* PRD & Issues - Side by Side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* PRD Section */}
        <Card>
          <CardHeader className="py-3 flex flex-row items-center justify-between">
            <CardTitle className="text-base">PRDs</CardTitle>
            <Button size="sm" onClick={() => setShowPrdDialog(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Add
            </Button>
          </CardHeader>
          <CardContent className="py-2">
            {prds.length === 0 ? (
              <p className="text-sm text-muted-foreground">No PRDs yet</p>
            ) : (
              prds.map(prd => (
                <Link
                  key={prd.id}
                  href={`/projects/${projectId}/prds/${prd.id}`}
                  className="flex items-center justify-between py-2 px-2 -mx-2 rounded-md hover:bg-accent transition-colors cursor-pointer"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{prd.title}</p>
                    <p className="text-sm text-muted-foreground truncate">{prd.description}</p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0 ml-2" />
                </Link>
              ))
            )}
          </CardContent>
        </Card>

        {/* Issues Section */}
        <Card>
          <CardHeader className="py-3 flex flex-row items-center justify-between">
            <CardTitle className="text-base">Issues</CardTitle>
            <Button size="sm" onClick={() => setShowIssueDialog(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Add
            </Button>
          </CardHeader>
          <CardContent className="py-2">
            {issues.length === 0 ? (
              <p className="text-sm text-muted-foreground">No issues yet</p>
            ) : (
              issues.map(issue => (
                <Link
                  key={issue.id}
                  href={`/projects/${projectId}/issues/${issue.id}`}
                  className="flex items-center justify-between py-2 px-2 -mx-2 rounded-md hover:bg-accent transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    {issue.status === 'done' ? (
                      <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
                    ) : (
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        issue.status === 'in_progress' ? 'bg-blue-500' :
                        issue.status === 'failed' ? 'bg-red-500' :
                        'bg-gray-400'
                      }`}></span>
                    )}
                    <span className="font-mono text-sm text-muted-foreground flex-shrink-0">#{issue.id}</span>
                    <span className="text-sm font-medium truncate">{issue.title || issue.content}</span>
                  </div>
                  <div className="flex-shrink-0 ml-2">
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </div>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Add PRD Dialog */}
      <Dialog open={showPrdDialog} onOpenChange={setShowPrdDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add PRD</DialogTitle>
            <DialogDescription>Create a new PRD for this project</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Title</label>
              <input
                type="text"
                value={prdTitle}
                onChange={(e) => setPrdTitle(e.target.value)}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                placeholder="PRD title"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Version</label>
              <input
                type="text"
                value={prdVersion}
                onChange={(e) => setPrdVersion(e.target.value)}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                placeholder="v1.0"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPrdDialog(false)}>Cancel</Button>
            <Button onClick={handleAddPRD}>Add PRD</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Issue Dialog */}
      <Dialog open={showIssueDialog} onOpenChange={setShowIssueDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Issue</DialogTitle>
            <DialogDescription>Create a new issue for this project</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Title</label>
              <input
                type="text"
                value={issueTitle}
                onChange={(e) => setIssueTitle(e.target.value)}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                placeholder="Issue title"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Content</label>
              <textarea
                value={issueContent}
                onChange={(e) => setIssueContent(e.target.value)}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm font-mono"
                rows={15}
                placeholder="Describe the change or bug... (supports large text)"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowIssueDialog(false)}>Cancel</Button>
            <Button onClick={handleAddIssue}>Add Issue</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Worker Dialog */}
      <Dialog open={showWorkerDialog} onOpenChange={setShowWorkerDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingWorker ? 'Edit Project Worker' : 'Add Project Worker'}</DialogTitle>
            <DialogDescription>
              Configure a worker for this project. You can customize the prompt template to adapt the worker for this project's needs.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {!editingWorker && (
              <div>
                <label className="text-sm font-medium">System Worker</label>
                <select
                  value={selectedWorkerId || ''}
                  onChange={(e) => setSelectedWorkerId(Number(e.target.value))}
                  className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                >
                  {systemWorkers.map(w => (
                    <option key={w.id} value={w.id}>{w.name} ({w.agent_type})</option>
                  ))}
                </select>
              </div>
            )}
            {editingWorker && (
              <div className="flex items-center gap-2">
                <Badge variant="outline">{editingWorker.worker_name}</Badge>
                <Badge variant="outline">{editingWorker.agent_type}</Badge>
              </div>
            )}
            <div>
              <label className="text-sm font-medium">Custom Prompt Template (Optional)</label>
              <textarea
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm font-mono"
                rows={8}
                placeholder="Override the system prompt for this project. Leave empty to use system default."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowWorkerDialog(false)} disabled={savingWorker}>
              Cancel
            </Button>
            <Button onClick={handleSaveWorker} disabled={savingWorker || !selectedWorkerId}>
              {savingWorker ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              {savingWorker ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Project Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Project</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Project Name</label>
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Description <span className="text-muted-foreground">(max 20 chars)</span></label>
              <input
                type="text"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value.slice(0, 20))}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={handleSaveProject} disabled={saving || !editName}>
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Project</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete "{project?.name}"? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteProject} disabled={deleting}>
              {deleting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* README Section */}
      {(readmeContent || readmeLoading) && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4" />
              README
            </CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            {readmeLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <Markdown content={readmeContent} />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
