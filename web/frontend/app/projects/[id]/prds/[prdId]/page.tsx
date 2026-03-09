'use client'

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import Link from "next/link"
import { ArrowLeft, Loader2, Calendar, FileText, GitBranch } from "lucide-react"

interface PRD {
  id: number
  project_id: number
  title: string
  version: string
  status: string
  created_at: string
}

interface Project {
  id: number
  name: string
}

export default function PRDDetailPage() {
  const params = useParams()
  const projectId = Number(params.id)
  const prdId = Number(params.prdId)

  const [prd, setPrd] = useState<PRD | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch(`/api/projects/${projectId}`).then(res => res.json()),
      fetch(`/api/projects/${projectId}/prds/${prdId}`).then(res => res.json())
    ])
      .then(([projectData, prdData]) => {
        setProject(projectData)
        setPrd(prdData)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [projectId, prdId])

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'approved': return 'default'
      case 'review': return 'secondary'
      default: return 'outline'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (!prd || !project) {
    return (
      <div className="text-center py-10">
        <p>PRD not found</p>
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

      {/* PRD Header */}
      <div className="flex items-start gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <Badge variant="outline">{prd.version}</Badge>
            <Badge variant={getStatusBadgeVariant(prd.status)}>
              {prd.status}
            </Badge>
          </div>
          <h1 className="text-2xl font-bold">{prd.title}</h1>
        </div>
      </div>

      {/* Project Info */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base">Project</CardTitle>
        </CardHeader>
        <CardContent className="py-2 space-y-2">
          <div className="flex items-center gap-2 text-sm">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <span>{project.name}</span>
          </div>
        </CardContent>
      </Card>

      {/* PRD Info */}
      <Card>
        <CardHeader className="py-3 flex flex-row items-center justify-between">
          <CardTitle className="text-base">Details</CardTitle>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Calendar className="h-4 w-4" />
            {new Date(prd.created_at).toLocaleDateString()}
          </div>
        </CardHeader>
        <CardContent className="py-2 space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Version</span>
            <span className="font-mono">{prd.version}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Status</span>
            <Badge variant={getStatusBadgeVariant(prd.status)}>{prd.status}</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Issues from this PRD - Placeholder */}
      <Card>
        <CardHeader className="py-3 flex flex-row items-center justify-between">
          <CardTitle className="text-base">Related Issues</CardTitle>
        </CardHeader>
        <CardContent className="py-2">
          <p className="text-sm text-muted-foreground">No issues linked yet</p>
        </CardContent>
      </Card>
    </div>
  )
}