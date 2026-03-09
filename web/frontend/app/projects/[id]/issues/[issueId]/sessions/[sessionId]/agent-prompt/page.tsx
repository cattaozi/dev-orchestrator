'use client'

import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import Link from "next/link"
import { ArrowLeft, Copy, Check } from "lucide-react"
import { useState, useEffect } from "react"

export default function WorkerPromptPage() {
  const params = useParams()
  const projectId = Number(params.id)
  const issueId = Number(params.issueId)
  const sessionId = Number(params.sessionId)

  const [copied, setCopied] = useState(false)
  const [prompt, setPrompt] = useState("")
  const [workerName, setWorkerName] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // First get session to find worker_id
    fetch(`/api/sessions`)
      .then(res => res.json())
      .then(data => {
        const session = data.find((s: any) => s.id === sessionId)
        if (session && session.worker_id) {
          // Get worker's prompt
          return fetch(`/api/projects/${projectId}/workers`)
            .then(res => res.json())
            .then(workers => {
              const worker = workers.find((w: any) => w.worker_id === session.worker_id)
              if (worker) {
                setPrompt(worker.prompt_template || '')
                setWorkerName(worker.worker_name || '')
              }
            })
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [projectId, sessionId])

  const handleCopy = async () => {
    await navigator.clipboard.writeText(prompt)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/projects/${projectId}/issues/${issueId}/sessions/${sessionId}`}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Session
          </Button>
        </Link>
      </div>

      {/* Prompt Content */}
      <Card>
        <CardHeader className="py-3 flex flex-row items-center justify-between">
          <CardTitle className="text-base">Agent Prompt{workerName && ` - ${workerName}`}</CardTitle>
          <Button variant="outline" size="sm" onClick={handleCopy}>
            {copied ? (
              <>
                <Check className="h-3 w-3 mr-1" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-3 w-3 mr-1" />
                Copy
              </>
            )}
          </Button>
        </CardHeader>
        <CardContent className="py-2">
          <pre className="whitespace-pre-wrap text-sm font-mono bg-muted p-4 rounded-md overflow-auto max-h-[calc(100vh-250px)]">
            {prompt || 'No prompt available.'}
          </pre>
        </CardContent>
      </Card>
    </div>
  )
}