import { NextResponse } from 'next/server'

const API_BASE = 'http://127.0.0.1:8000/api'

export async function GET(
  request: Request,
  { params }: { params: { id: string; issueId: string } }
) {
  const projectId = params.id
  const issueId = params.issueId

  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/issues/${issueId}`)
    if (!res.ok) {
      return NextResponse.json({ error: 'Issue not found' }, { status: 404 })
    }
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: { id: string; issueId: string } }
) {
  const projectId = params.id
  const issueId = params.issueId

  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/issues/${issueId}`, {
      method: 'DELETE'
    })
    if (!res.ok) {
      return NextResponse.json({ error: 'Failed to delete issue' }, { status: res.status })
    }
    return NextResponse.json({ success: true })
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}

export async function PUT(
  request: Request,
  { params }: { params: { id: string; issueId: string } }
) {
  const projectId = params.id
  const issueId = params.issueId

  try {
    const body = await request.json()
    const res = await fetch(`${API_BASE}/projects/${projectId}/issues/${issueId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    if (!res.ok) {
      return NextResponse.json({ error: 'Failed to update issue' }, { status: res.status })
    }
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}