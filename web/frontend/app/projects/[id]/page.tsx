'use client'

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import Link from "next/link"
import { ArrowLeft, Folder, Plus, Loader2, ChevronRight, Pencil, Trash2, X, Check, FileText, Bot, MoreHorizontal, Play, Square, RotateCcw, Server, Save, ExternalLink } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Markdown } from "@/components/ui/markdown"

interface Project {
  id: number
  name: string
  description: string
  local_path: string
  favorited?: boolean
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

interface ProjectService {
  id: number
  project_id: number
  name: string
  start_command: string
  stop_command: string
  workdir: string
  port: number | null
  healthcheck_url: string
  url: string
  status: string
  pid: number | null
  last_error: string
}

export default function ProjectDetailPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = Number(params.id)

  const [project, setProject] = useState<Project | null>(null)
  const [issues, setIssues] = useState<Issue[]>([])
  const [projectWorkers, setProjectWorkers] = useState<ProjectWorker[]>([])
  const [systemWorkers, setSystemWorkers] = useState<Worker[]>([])
  const [projectServices, setProjectServices] = useState<ProjectService[]>([])
  const [loading, setLoading] = useState(true)
  const [readmeContent, setReadmeContent] = useState<string>("")
  const [readmeLoading, setReadmeLoading] = useState(false)

  // Dialog states
  const [showIssueDialog, setShowIssueDialog] = useState(false)
  const [showWorkerDialog, setShowWorkerDialog] = useState(false)
  const [editingWorker, setEditingWorker] = useState<ProjectWorker | null>(null)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [showServiceDialog, setShowServiceDialog] = useState(false)
  const [showMenu, setShowMenu] = useState(false)

  // Form states
  const [issueTitle, setIssueTitle] = useState("")
  const [issueContent, setIssueContent] = useState("")
  const [selectedWorkerId, setSelectedWorkerId] = useState<number | null>(null)
  const [customPrompt, setCustomPrompt] = useState("")
  const [savingWorker, setSavingWorker] = useState(false)
  const [savingService, setSavingService] = useState(false)
  const [operatingServiceId, setOperatingServiceId] = useState<number | null>(null)
  const [serviceMenuId, setServiceMenuId] = useState<number | null>(null)

  // Service form
  const [serviceName, setServiceName] = useState("")
  const [serviceStartCommand, setServiceStartCommand] = useState("")
  const [serviceStopCommand, setServiceStopCommand] = useState("")
  const [servicePort, setServicePort] = useState("")
  const [serviceHealthUrl, setServiceHealthUrl] = useState("")

  // Edit form states
  const [editName, setEditName] = useState("")
  const [editDescription, setEditDescription] = useState("")
  const [editLocalPath, setEditLocalPath] = useState("")
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
  }, [projectWorkers.length, systemWorkers, projectId, initialized, initializing])
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

    fetch(`/api/projects/${projectId}/services`)
      .then(res => res.json())
      .then(data => setProjectServices(Array.isArray(data) ? data : []))
      .catch(() => setProjectServices([]))
  }, [projectId])

  const fetchProjectServices = useCallback(async () => {
    const res = await fetch(`/api/projects/${projectId}/services`)
    const data = await res.json()
    setProjectServices(Array.isArray(data) ? data : [])
  }, [projectId])

  useEffect(() => {
    const timer = setInterval(() => {
      fetchProjectServices().catch(() => {})
    }, 5000)
    return () => clearInterval(timer)
  }, [fetchProjectServices])

  const handleSaveService = async () => {
    if (!serviceName.trim() || !serviceStartCommand.trim()) return
    setSavingService(true)
    try {
      const res = await fetch(`/api/projects/${projectId}/services`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: serviceName.trim(),
          start_command: serviceStartCommand.trim(),
          stop_command: serviceStopCommand.trim(),
          workdir: project?.local_path || '',
          port: servicePort.trim() ? Number(servicePort.trim()) : null,
          healthcheck_url: serviceHealthUrl.trim(),
        })
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        alert(data?.detail || 'Failed to create service')
        return
      }
      setServiceName("")
      setServiceStartCommand("")
      setServiceStopCommand("")
      setServicePort("")
      setServiceHealthUrl("")
      await fetchProjectServices()
      setShowServiceDialog(false)
    } catch {
      alert('Failed to create service')
    } finally {
      setSavingService(false)
    }
  }

  const operateService = async (serviceId: number, action: 'start' | 'stop' | 'restart') => {
    setOperatingServiceId(serviceId)
    try {
      const res = await fetch(`/api/projects/${projectId}/services/${serviceId}/${action}`, {
        method: 'POST'
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        alert(data?.detail || `Failed to ${action} service`)
      }
      await fetchProjectServices()
    } catch {
      alert(`Failed to ${action} service`)
    } finally {
      setOperatingServiceId(null)
    }
  }

  const deleteService = async (serviceId: number, serviceNameToDelete: string) => {
    if (!confirm(`Delete service "${serviceNameToDelete}"?`)) return
    try {
      const res = await fetch(`/api/projects/${projectId}/services/${serviceId}`, {
        method: 'DELETE'
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        alert(data?.detail || 'Failed to delete service')
        return
      }
      await fetchProjectServices()
    } catch {
      alert('Failed to delete service')
    }
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
      setEditLocalPath(project.local_path || "")
      setShowEditDialog(true)
    }
  }

  const handleSaveProject = async () => {
    setSaving(true)
    try {
      const res = await fetch(`/api/projects/${projectId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editName,
          description: editDescription.slice(0, 20),
          local_path: editLocalPath,
          favorited: project?.favorited ?? false,
        })
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
              <div className="absolute right-0 top-full mt-1 z-20 bg-background border rounded-md shadow-lg py-1 min-w-[168px]">
                <button
                  onClick={() => { setShowServiceDialog(true); setShowMenu(false) }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm whitespace-nowrap hover:bg-accent"
                >
                  <Server className="h-3 w-3" />
                  Add Service
                </button>
                <button
                  onClick={() => { openEditDialog(); setShowMenu(false) }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm whitespace-nowrap hover:bg-accent"
                >
                  <Pencil className="h-3 w-3" />
                  Edit
                </button>
                <button
                  onClick={() => { setShowDeleteDialog(true); setShowMenu(false) }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm whitespace-nowrap hover:bg-accent text-red-500"
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
          <Folder className="h-3 w-3" />
          <span className="font-mono text-xs">{project.local_path}</span>
        </div>
      </div>

      <Card>
        <CardHeader className="py-2 flex flex-row items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Server className="h-4 w-4" />
            Services
          </CardTitle>
        </CardHeader>
        <CardContent className="py-2">
          {projectServices.length === 0 ? (
            <p className="text-sm text-muted-foreground">No managed services yet. Use More → Add Service.</p>
          ) : (
            <div className="divide-y">
              {projectServices.map((service) => (
                <div key={service.id} className="py-2.5">
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`h-2 w-2 rounded-full ${service.status === 'running' ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                        <span className="font-medium">{service.name}</span>
                        {service.pid ? <span className="text-xs text-muted-foreground">PID {service.pid}</span> : null}
                        {service.last_error ? <span className="text-xs text-red-500 truncate">{service.last_error}</span> : null}
                      </div>                      
                    </div>
                    <div className="flex items-center gap-1 pt-0.5 relative">
                      <Button
                        size="icon"
                        variant="ghost"
                        title="Start"
                        aria-label="Start"
                        className="h-8 w-8"
                        disabled={operatingServiceId === service.id || service.status === 'running'}
                        onClick={() => operateService(service.id, 'start')}
                      >
                        <Play className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        title="Stop"
                        aria-label="Stop"
                        className="h-8 w-8"
                        disabled={operatingServiceId === service.id || service.status !== 'running'}
                        onClick={() => operateService(service.id, 'stop')}
                      >
                        <Square className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        title="Restart"
                        aria-label="Restart"
                        className="h-8 w-8"
                        disabled={operatingServiceId === service.id}
                        onClick={() => operateService(service.id, 'restart')}
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        title="More"
                        aria-label="More"
                        className="h-8 w-8"
                        onClick={() => setServiceMenuId(serviceMenuId === service.id ? null : service.id)}
                      >
                        <MoreHorizontal className="h-3.5 w-3.5" />
                      </Button>
                      {service.url ? (
                        <Button
                          size="icon"
                          variant="ghost"
                          title="Open URL"
                          aria-label="Open URL"
                          className="h-8 w-8"
                          onClick={() => window.open(service.url, '_blank')}
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </Button>
                      ) : null}
                      {serviceMenuId === service.id ? (
                        <div className="absolute right-10 top-9 z-20 min-w-[110px] rounded-md border bg-background shadow-lg py-1">
                          <button
                            onClick={() => {
                              deleteService(service.id, service.name)
                              setServiceMenuId(null)
                            }}
                            disabled={service.status === 'running'}
                            className="flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-accent text-red-500 disabled:text-muted-foreground disabled:hover:bg-transparent"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            Delete
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

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

      <div className="grid grid-cols-1 gap-4">
        <Card>
          <CardHeader className="py-3 flex flex-row items-center justify-between">
            <CardTitle className="text-base">Tasks</CardTitle>
            <Button size="sm" onClick={() => setShowIssueDialog(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Add Task
            </Button>
          </CardHeader>
          <CardContent className="py-2">
            {issues.length === 0 ? (
              <p className="text-sm text-muted-foreground">No tasks yet</p>
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

      {/* Add Issue Dialog */}
      <Dialog open={showIssueDialog} onOpenChange={setShowIssueDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Task</DialogTitle>
            <DialogDescription>Create a new task for this project</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Title</label>
              <input
                type="text"
                value={issueTitle}
                onChange={(e) => setIssueTitle(e.target.value)}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                placeholder="Task title"
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
            <Button onClick={handleAddIssue}>Add Task</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Worker Dialog */}
      <Dialog open={showWorkerDialog} onOpenChange={setShowWorkerDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingWorker ? 'Edit Project Worker' : 'Add Project Worker'}</DialogTitle>
            <DialogDescription>
              Configure a worker for this project. You can customize the prompt template to adapt the worker for this project&apos;s needs.
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
            <div>
              <label className="text-sm font-medium">Local Path</label>
              <input
                type="text"
                value={editLocalPath}
                onChange={(e) => setEditLocalPath(e.target.value)}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm font-mono"
                placeholder="/absolute/path/to/repo"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={handleSaveProject} disabled={saving || !editName || !editLocalPath}>
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
            Are you sure you want to delete &quot;{project?.name}&quot;? This action cannot be undone.
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

      {/* Add Service Dialog */}
      <Dialog open={showServiceDialog} onOpenChange={setShowServiceDialog}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Add Managed Service</DialogTitle>
            <DialogDescription>Define a runnable service for this project.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <input
                type="text"
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="Service name"
              />
              <input
                type="text"
                value={servicePort}
                onChange={(e) => setServicePort(e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="Port (optional)"
              />
            </div>
            <input
              type="text"
              value={serviceStartCommand}
              onChange={(e) => setServiceStartCommand(e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm font-mono"
              placeholder="Start command, e.g. npm run dev"
            />
            <input
              type="text"
              value={serviceStopCommand}
              onChange={(e) => setServiceStopCommand(e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm font-mono"
              placeholder="Stop command (optional)"
            />
            <input
              type="text"
              value={serviceHealthUrl}
              onChange={(e) => setServiceHealthUrl(e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm"
              placeholder="Health URL (optional), e.g. http://localhost:3000/health"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowServiceDialog(false)} disabled={savingService}>
              Cancel
            </Button>
            <Button onClick={handleSaveService} disabled={savingService || !serviceName || !serviceStartCommand}>
              {savingService ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
              Save Service
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
