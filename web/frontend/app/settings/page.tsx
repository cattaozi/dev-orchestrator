'use client'

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Save, Loader2 } from "lucide-react"

export default function SettingsPage() {
  const [footerPrompt, setFooterPrompt] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    fetch("/api/config")
      .then(res => res.json())
      .then(data => {
        setFooterPrompt(data.agent_footer_prompt || "")
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_footer_prompt: footerPrompt })
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Configure agent behavior and prompts</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Agent Footer Prompt</CardTitle>
          <CardDescription>
            This prompt will be appended to every agent request. Use {"{branch}"} and {"{project_path}"} as placeholders.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="footer">Footer Prompt</Label>
            <Textarea
              id="footer"
              value={footerPrompt}
              onChange={(e) => setFooterPrompt(e.target.value)}
              placeholder={"请在此分支 {branch} 上进行开发。\n开发完成后，请：\n1. 编写单元测试\n2. 提交代码到 {branch} 分支\n3. 汇报完成状态"}
              rows={8}
            />
          </div>

          <div className="text-sm text-muted-foreground space-y-1">
            <p>Available placeholders:</p>
            <ul className="list-disc list-inside">
              <li>{"{branch}"} - Branch name (e.g., task/issue-11)</li>
              <li>{"{project_path}"} - Project worktree path</li>
            </ul>
          </div>

          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            {saving ? "Saving..." : "Save"}
          </Button>

          {saved && <span className="text-green-600 text-sm ml-2">Saved!</span>}
        </CardContent>
      </Card>
    </div>
  )
}
