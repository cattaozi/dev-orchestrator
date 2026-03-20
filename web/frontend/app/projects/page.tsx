'use client'

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useStore } from "@/lib/store"
import { createProject } from "@/lib/api"
import {
  Folder,
  FolderOpen,
  Link as LinkIcon,
  Loader2,
  MessageSquare,
  MoreVertical,
  Plus,
  Star,
  Trash2,
} from "lucide-react"

interface Project {
  id: number
  name: string
  description?: string
  local_path: string
  status: string
  favorited: boolean
  created_at: string
}

interface RuntimeService {
  pid: number
  port: number
  url: string
  command: string
  status: string
}

interface RuntimeStatus {
  running: boolean
  count: number
  services: RuntimeService[]
}

function ProjectStatusBadge({ runtime }: { runtime?: RuntimeStatus }) {
  if (runtime?.running) {
    return (
      <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100/80 border-transparent shadow-none">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5" />
        Running
      </Badge>
    )
  }
  return <Badge variant="secondary" className="shadow-none">Stopped</Badge>
}

function ProjectCard({
  project,
  runtime,
  menuOpen,
  onToggleFavorite,
  onToggleMenu,
  onDelete,
  onOpen,
  onChat,
}: {
  project: Project
  runtime?: RuntimeStatus
  menuOpen: boolean
  onToggleFavorite: () => void
  onToggleMenu: () => void
  onDelete: () => void
  onOpen: () => void
  onChat: () => void
}) {
  const running = Boolean(runtime?.running)
  const urls = runtime?.services?.map((s) => s.url) ?? []
  const visibleUrls = Array.from(new Set(urls.filter(Boolean)))
  const canChat = running

  return (
    <Card
      className="group cursor-pointer border-border/70 bg-card transition-all duration-200 hover:border-blue-300/70 hover:shadow-[0_0_0_1px_rgba(59,130,246,0.24),0_14px_32px_-14px_rgba(37,99,235,0.45)]"
      onClick={onOpen}
    >
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <CardTitle className="text-lg leading-tight truncate">{project.name}</CardTitle>
              <ProjectStatusBadge runtime={runtime} />
            </div>
            <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground truncate w-full min-w-0">
              <Folder className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="truncate font-mono">{project.local_path}</span>
            </div>
          </div>

          <div className="relative flex items-center gap-1 flex-shrink-0">
            <button
              onClick={(e) => {
                e.stopPropagation()
                onToggleFavorite()
              }}
              className="rounded-md p-1.5 hover:bg-accent"
              aria-label="Toggle favorite"
            >
              <Star className={`h-4 w-4 ${project.favorited ? "text-yellow-500 fill-yellow-500" : "text-muted-foreground"}`} />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onToggleMenu()
              }}
              className="rounded-md p-1.5 hover:bg-accent"
              aria-label="More actions"
            >
              <MoreVertical className="h-4 w-4 text-muted-foreground" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-8 z-20 min-w-[130px] rounded-md border bg-background shadow-lg py-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onDelete()
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-500 hover:bg-accent"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
              </div>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="space-y-2">
          {visibleUrls.length > 0 ? (
            <div className="space-y-1.5">
              {visibleUrls.map((url) => (
                <div key={url} className="text-sm text-blue-600 hover:underline flex items-center gap-1.5 min-w-0">
                  <LinkIcon className="h-3.5 w-3.5 flex-shrink-0" />
                  <span className="truncate font-mono">{url}</span>
                </div>
              ))}
            </div>
          ) : (
            <span className="text-sm text-muted-foreground italic">Service entrypoint unavailable</span>
          )}
        </div>
      </CardContent>

      <CardFooter className="flex justify-end items-center pt-0">
        <div className="flex items-center gap-1">
          {canChat ? (
            <Button
              size="icon"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation()
                onChat()
              }}
              aria-label="Open chat"
            >
              <MessageSquare className="h-4 w-4" />
            </Button>
          ) : (
            <Button size="icon" variant="ghost" disabled title="No running service available" aria-label="Chat unavailable">
              <MessageSquare className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  )
}

export default function ProjectsPage() {
  const router = useRouter()
  const { projects, fetchProjects, loading } = useStore()
  const [runtimeMap, setRuntimeMap] = useState<Record<string, RuntimeStatus>>({})
  const [showDialog, setShowDialog] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [openProjectMenuId, setOpenProjectMenuId] = useState<number | null>(null)

  const [name, setName] = useState("")
  const [localPath, setLocalPath] = useState("")

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  useEffect(() => {
    let active = true
    const fetchRuntime = async () => {
      try {
        const res = await fetch("/api/projects/runtime-services")
        if (!res.ok) return
        const data = await res.json()
        if (active) setRuntimeMap(data || {})
      } catch (e) {
        console.error(e)
      }
    }

    fetchRuntime()
    const timer = setInterval(fetchRuntime, 12000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  const projectList = useMemo(() => ((projects || []) as Project[]), [projects])
  const favoriteProjects = useMemo(
    () => projectList.filter((p) => p.favorited),
    [projectList]
  )
  const otherProjects = useMemo(
    () => projectList.filter((p) => !p.favorited),
    [projectList]
  )

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await createProject({ name, local_path: localPath })
      setShowDialog(false)
      setName("")
      setLocalPath("")
      fetchProjects()
    } catch (e) {
      console.error(e)
    } finally {
      setSubmitting(false)
    }
  }

  const toggleFavorite = async (projectId: number) => {
    try {
      const res = await fetch(`/api/projects/${projectId}/favorite`, { method: "POST" })
      if (res.ok) fetchProjects()
    } catch (e) {
      console.error(e)
    }
  }

  const handleDeleteProject = async (projectId: number) => {
    try {
      const res = await fetch(`/api/projects/${projectId}`, { method: "DELETE" })
      if (res.ok) fetchProjects()
      else alert("Delete project failed")
    } catch (e) {
      console.error(e)
      alert("Delete project failed")
    } finally {
      setOpenProjectMenuId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Projects</h1>
          <p className="text-sm text-muted-foreground mt-1">Overview of project health, runtime status, and next actions.</p>
        </div>
        <Button onClick={() => setShowDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </div>

      {openProjectMenuId !== null && (
        <button
          className="fixed inset-0 z-10 cursor-default"
          onClick={() => setOpenProjectMenuId(null)}
          aria-label="Close menu"
        />
      )}

      {loading ? (
        <Card>
          <CardContent className="py-12 flex items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Loading projects...</span>
          </CardContent>
        </Card>
      ) : projectList.length === 0 ? (
        <Card>
          <CardContent className="py-12 flex flex-col items-center justify-center text-center">
            <FolderOpen className="h-10 w-10 text-muted-foreground mb-3" />
            <p className="font-medium">No projects yet</p>
            <p className="text-sm text-muted-foreground mt-1">Create your first project to get started.</p>
            <Button variant="outline" className="mt-4" onClick={() => setShowDialog(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Project
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-8">
          {favoriteProjects.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Favorites</p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {favoriteProjects.map((project) => (
                  <ProjectCard
                    key={project.id}
                    project={project}
                    runtime={runtimeMap[String(project.id)]}
                    menuOpen={openProjectMenuId === project.id}
                    onToggleFavorite={() => toggleFavorite(project.id)}
                    onToggleMenu={() => setOpenProjectMenuId(openProjectMenuId === project.id ? null : project.id)}
                    onDelete={() => {
                      setOpenProjectMenuId(null)
                      const confirmed = window.confirm(`Delete project "${project.name}"? This action cannot be undone.`)
                      if (confirmed) handleDeleteProject(project.id)
                    }}
                    onOpen={() => router.push(`/projects/${project.id}`)}
                    onChat={() => router.push(`/projects/${project.id}/chat`)}
                  />
                ))}
              </div>
            </div>
          )}

          {otherProjects.length > 0 && (
            <div className="space-y-3">
              {favoriteProjects.length > 0 && (
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Projects</p>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {otherProjects.map((project) => (
                  <ProjectCard
                    key={project.id}
                    project={project}
                    runtime={runtimeMap[String(project.id)]}
                    menuOpen={openProjectMenuId === project.id}
                    onToggleFavorite={() => toggleFavorite(project.id)}
                    onToggleMenu={() => setOpenProjectMenuId(openProjectMenuId === project.id ? null : project.id)}
                    onDelete={() => {
                      setOpenProjectMenuId(null)
                      const confirmed = window.confirm(`Delete project "${project.name}"? This action cannot be undone.`)
                      if (confirmed) handleDeleteProject(project.id)
                    }}
                    onOpen={() => router.push(`/projects/${project.id}`)}
                    onChat={() => router.push(`/projects/${project.id}/chat`)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/50" onClick={() => setShowDialog(false)} />
          <div className="relative z-50 w-full max-w-lg rounded-lg bg-background p-6 shadow-lg">
            <div className="mb-4">
              <h2 className="text-lg font-semibold">Create New Project</h2>
              <p className="text-sm text-muted-foreground mt-1">Create a project with a name and local folder path.</p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">Project Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="my-project"
                  className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Local Path</label>
                <input
                  type="text"
                  value={localPath}
                  onChange={(e) => setLocalPath(e.target.value)}
                  placeholder="/absolute/path/to/project"
                  className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <Button variant="outline" onClick={() => setShowDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={submitting || !name || !localPath}>
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create Project
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
