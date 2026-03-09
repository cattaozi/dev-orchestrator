'use client'

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useStore } from "@/lib/store"
import { useEffect } from "react"
import Link from "next/link"
import { FolderGit2, Plus, GitBranch, Folder, Loader2, Star, ExternalLink } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { createProject } from "@/lib/api"

export default function ProjectsPage() {
  const { projects, fetchProjects, loading } = useStore()
  const [showDialog, setShowDialog] = useState(false)
  const [repoType, setRepoType] = useState<"git" | "local">("git")
  const [submitting, setSubmitting] = useState(false)
  
  // Form fields
  const [name, setName] = useState("")
  const [gitUrl, setGitUrl] = useState("")
  const [localPath, setLocalPath] = useState("")
  const [savePath, setSavePath] = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")

  useEffect(() => {
    fetchProjects()
  }, [])

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await createProject({
        name,
        repo: gitUrl,
        local_path: savePath || localPath,
      })
      setShowDialog(false)
      fetchProjects()
      // Reset form
      setName("")
      setGitUrl("")
      setLocalPath("")
      setSavePath("")
      setUsername("")
      setPassword("")
    } catch (e) {
      console.error(e)
    }
    setSubmitting(false)
  }

  const toggleFavorite = async (projectId: number, currentFavorited: boolean) => {
    try {
      const res = await fetch(`/api/projects/${projectId}/favorite`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        // Update local state
        const updatedProjects = projects.map(p =>
          p.id === projectId ? { ...p, favorited: data.favorited } : p
        )
        // Use a simple approach - just refetch
        fetchProjects()
      }
    } catch (e) {
      console.error(e)
    }
  }

  const favoritedProjects = projects.filter(p => p.favorited)
  const normalProjects = projects.filter(p => !p.favorited)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Projects</h1>
          <p className="text-muted-foreground">Manage your development projects</p>
        </div>
        <Button onClick={() => setShowDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </div>

      {loading ? (
        <div className="text-center py-10 text-muted-foreground">Loading...</div>
      ) : projects.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-10">
            <FolderGit2 className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No projects yet</p>
            <Button variant="outline" className="mt-4" onClick={() => setShowDialog(true)}>
              Create your first project
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Favorited Projects Section */}
          {favoritedProjects.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                <h2 className="text-sm font-medium text-muted-foreground">Favorited</h2>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {favoritedProjects.map((project) => (
                  <Link key={project.id} href={`/projects/${project.id}`}>
                    <Card className="hover:shadow-md transition-shadow cursor-pointer border-yellow-200 dark:border-yellow-800">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="font-semibold">{project.name}</h3>
                          <span
                            onClick={(e) => { e.preventDefault(); toggleFavorite(project.id, project.favorited) }}
                            className="p-1 hover:bg-accent rounded cursor-pointer"
                          >
                            <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                          </span>
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <GitBranch className="h-3 w-3 flex-shrink-0" />
                            <span className="font-mono truncate">{project.repo}</span>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Folder className="h-3 w-3 flex-shrink-0" />
                            <span className="font-mono truncate">{project.local_path}</span>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Normal Projects Section */}
          <div>
            {favoritedProjects.length > 0 && (
              <h2 className="text-sm font-medium text-muted-foreground mb-3">All Projects</h2>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {normalProjects.map((project) => (
                <Link key={project.id} href={`/projects/${project.id}`}>
                  <Card className="hover:shadow-md transition-shadow cursor-pointer">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold">{project.name}</h3>
                        <span
                          onClick={(e) => { e.preventDefault(); toggleFavorite(project.id, project.favorited) }}
                          className="p-1 hover:bg-accent rounded cursor-pointer"
                        >
                          <Star className="h-4 w-4 text-muted-foreground" />
                        </span>
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <GitBranch className="h-3 w-3 flex-shrink-0" />
                          <span className="font-mono truncate">{project.repo}</span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Folder className="h-3 w-3 flex-shrink-0" />
                          <span className="font-mono truncate">{project.local_path}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Create Project Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Project</DialogTitle>
            <DialogDescription>
              Add a new project from Git repository or local path
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Repo Type Selection */}
            <div className="flex gap-2">
              <Button
                variant={repoType === "git" ? "default" : "outline"}
                size="sm"
                onClick={() => setRepoType("git")}
                className="flex-1"
              >
                <GitBranch className="mr-2 h-4 w-4" />
                Git
              </Button>
              <Button
                variant={repoType === "local" ? "default" : "outline"}
                size="sm"
                onClick={() => setRepoType("local")}
                className="flex-1"
              >
                <Folder className="mr-2 h-4 w-4" />
                Local
              </Button>
            </div>

            {/* Project Name */}
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

            {repoType === "git" ? (
              <>
                {/* Git URL */}
                <div>
                  <label className="text-sm font-medium">Git Repository URL</label>
                  <input
                    type="text"
                    value={gitUrl}
                    onChange={(e) => setGitUrl(e.target.value)}
                    placeholder="https://github.com/owner/repo.git"
                    className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                  />
                </div>

                {/* Save Path */}
                <div>
                  <label className="text-sm font-medium">Save Path</label>
                  <input
                    type="text"
                    value={savePath}
                    onChange={(e) => setSavePath(e.target.value)}
                    placeholder="/data/repo/my-project"
                    className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                  />
                </div>

                {/* Credentials */}
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-sm font-medium">Username</label>
                      <input
                        type="text"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="GitHub username"
                        className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Password/Token</label>
                      <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="GitHub token"
                        className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    For private repositories, provide a GitHub Personal Access Token
                  </p>
                </div>
              </>
            ) : (
              /* Local Path */
              <div>
                <label className="text-sm font-medium">Local Path</label>
                <input
                  type="text"
                  value={localPath}
                  onChange={(e) => setLocalPath(e.target.value)}
                  placeholder="/data/repo/my-project"
                  className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting || !name || (repoType === "git" ? !gitUrl : !localPath)}>
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Project
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
