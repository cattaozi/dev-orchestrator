'use client'

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import Link from "next/link"
import { ArrowLeft, Loader2, Pencil, Trash2, Bot, ChevronRight, Check } from "lucide-react"

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

interface Project {
  id: number
  name: string
}

export default function ProjectWorkerPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = Number(params.id)
  const workerId = Number(params.workerId)

  const [project, setProject] = useState<Project | null>(null)
  const [projectWorker, setProjectWorker] = useState<ProjectWorker | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)

  // Form fields
  const [customPrompt, setCustomPrompt] = useState("")

  useEffect(() => {
    Promise.all([
      fetch(`/api/projects/${projectId}`).then(res => res.json()),
      fetch(`/api/projects/${projectId}/workers`).then(res => res.json())
    ])
      .then(([projectData, workersData]) => {
        setProject(projectData)
        const worker = Array.isArray(workersData) ? workersData.find((w: ProjectWorker) => w.id === workerId) : null
        setProjectWorker(worker)
        if (worker) {
          setCustomPrompt(worker.custom_prompt_template || "")
        }
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [projectId, workerId])

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await fetch(`/api/projects/${projectId}/workers/${workerId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ custom_prompt_template: customPrompt })
      })
      if (res.ok) {
        const data = await res.json()
        setProjectWorker(prev => prev ? { ...prev, custom_prompt_template: customPrompt } : null)
      } else {
        alert('Failed to save')
      }
    } catch {
      alert('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      const res = await fetch(`/api/projects/${projectId}/workers/${workerId}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        router.push(`/projects/${projectId}`)
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

  if (!projectWorker || !project) {
    return (
      <div className="text-center py-10">
        <p>Worker not found</p>
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

      {/* Worker Header */}
      <div className="flex items-center gap-4">
        <span className="text-4xl">{projectWorker.emoji}</span>
        <div>
          <h1 className="text-2xl font-bold">{projectWorker.worker_name}</h1>
          <div className="flex items-center gap-2 text-sm text-muted-foreground mt-1">
            <Badge variant="outline">{projectWorker.agent_type}</Badge>
            <span>Project: {project.name}</span>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Check className="h-4 w-4 mr-2" />
              Save
            </>
          )}
        </Button>
        <Button size="sm" variant="destructive" onClick={() => setShowDeleteDialog(true)} disabled={deleting}>
          <Trash2 className="h-4 w-4 mr-2" />
          Remove from Project
        </Button>
      </div>

      {/* Custom Prompt */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Bot className="h-4 w-4" />
            Custom Prompt Template
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-2">
            Override the system prompt for this worker in this project. Leave empty to use system default.
          </p>
          <textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            className="w-full min-h-[300px] p-4 text-sm font-mono border rounded-md"
            placeholder="Enter custom prompt template..."
          />
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Remove Worker</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Remove "{projectWorker.worker_name}" from this project? The system worker will still be available.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
