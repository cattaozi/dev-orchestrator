'use client'

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Loader2, Plus, Pencil, Trash2, Check, X, Bot } from "lucide-react"

interface Worker {
  id: number
  name: string
  emoji: string
  agent_type: string
  prompt_template: string
  prompt_file_path: string
  is_builtin: boolean
}

export default function WorkersPage() {
  const [workers, setWorkers] = useState<Worker[]>([])
  const [loading, setLoading] = useState(true)
  const [showDialog, setShowDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deletingWorker, setDeletingWorker] = useState<Worker | null>(null)
  const [editingWorker, setEditingWorker] = useState<Worker | null>(null)
  const [saving, setSaving] = useState(false)

  // Form fields
  const [name, setName] = useState("")
  const [agentType, setAgentType] = useState("claude-code")
  const [emoji, setEmoji] = useState("")
  const [promptTemplate, setPromptTemplate] = useState("")
  const [promptFilePath, setPromptFilePath] = useState("")

  useEffect(() => {
    fetchWorkers()
  }, [])

  const fetchWorkers = async () => {
    try {
      const res = await fetch('/api/workers')
      if (res.ok) {
        const data = await res.json()
        setWorkers(data)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const openCreateDialog = () => {
    setEditingWorker(null)
    setName("")
    setEmoji("")
    setAgentType("claude-code")
    setPromptTemplate("")
    setPromptFilePath("")
    setShowDialog(true)
  }

  const openEditDialog = (worker: Worker) => {
    setEditingWorker(worker)
    setName(worker.name)
    setEmoji(worker.emoji)
    setAgentType(worker.agent_type)
    setPromptTemplate(worker.prompt_template)
    setPromptFilePath(worker.prompt_file_path || "")
    setShowDialog(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {
        name,
        emoji,
        agent_type: agentType,
        prompt_template: promptTemplate,
        prompt_file_path: promptFilePath
      }

      let res
      if (editingWorker) {
        res = await fetch(`/api/workers/${editingWorker.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
      } else {
        res = await fetch('/api/workers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
      }

      if (res.ok) {
        fetchWorkers()
        setShowDialog(false)
      } else {
        alert('Failed to save worker')
      }
    } catch {
      alert('Failed to save worker')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = (worker: Worker) => {
    setDeletingWorker(worker)
    setShowDeleteDialog(true)
  }

  const confirmDelete = async () => {
    if (!deletingWorker) return
    try {
      const res = await fetch(`/api/workers/${deletingWorker.id}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        fetchWorkers()
      } else {
        alert('Failed to delete worker')
      }
    } catch {
      alert('Failed to delete worker')
    } finally {
      setShowDeleteDialog(false)
      setDeletingWorker(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  return (
    <div className="container mx-auto py-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Bot className="h-6 w-6" />
          Workers
        </h1>
        <Button onClick={openCreateDialog}>
          <Plus className="h-4 w-4 mr-2" />
          Add Worker
        </Button>
      </div>

      {workers.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            No workers yet. Add one to get started.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {workers.map(worker => (
            <Card key={worker.id}>
              <CardHeader className="py-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{worker.emoji}</span>
                    <CardTitle className="text-base">{worker.name}</CardTitle>
                    {worker.is_builtin && <Badge variant="secondary">Builtin</Badge>}
                    <Badge variant="outline">{worker.agent_type}</Badge>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEditDialog(worker)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDelete(worker)}
                      disabled={showDeleteDialog || worker.is_builtin}
                      title={worker.is_builtin ? "Cannot delete builtin worker" : ""}
                    >
                      <Trash2 className={`h-4 w-4 ${worker.is_builtin ? 'text-muted-foreground' : ''}`} />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="py-2">
                {worker.prompt_file_path && (
                  <p className="text-xs text-muted-foreground mb-2 font-mono">
                    📄 {worker.prompt_file_path}
                  </p>
                )}
                <pre className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {worker.prompt_template || '(No prompt template)'}
                </pre>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingWorker ? 'Edit Worker' : 'Add Worker'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex gap-4">
              <div className="w-20">
                <label className="text-sm font-medium">Emoji</label>
                <Input
                  value={emoji}
                  onChange={(e) => setEmoji(e.target.value)}
                  placeholder="👨‍💻"
                  className="mt-1 text-center"
                />
              </div>
              <div className="flex-1">
                <label className="text-sm font-medium">Name</label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Worker name"
                  className="mt-1"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Agent Type</label>
              <Input
                value={agentType}
                onChange={(e) => setAgentType(e.target.value)}
                placeholder="claude-code"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Prompt Template</label>
              <textarea
                value={promptTemplate}
                onChange={(e) => setPromptTemplate(e.target.value)}
                placeholder="System prompt for the agent..."
                className="w-full min-h-[120px] p-3 text-sm border rounded-md mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Prompt File Path</label>
              <Input
                value={promptFilePath}
                onChange={(e) => setPromptFilePath(e.target.value)}
                placeholder="/path/to/prompt.txt"
                className="mt-1 font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Optional: Load system prompt from file instead of template above
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving || !name}>
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
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Worker</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete worker "{deletingWorker?.name}"? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)} disabled={!deletingWorker}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={!deletingWorker}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
