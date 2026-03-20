import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export async function GET(request: Request, { params }: { params: { id: string } }) {
  const projectId = params.id
  
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}`)
    if (!res.ok) {
      return NextResponse.json({ error: 'Project not found' }, { status: 404 })
    }
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}

export async function PUT(request: Request, { params }: { params: { id: string } }) {
  const projectId = params.id
  const body = await request.json()

  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}

export async function DELETE(_request: Request, { params }: { params: { id: string } }) {
  const projectId = params.id

  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}`, {
      method: 'DELETE',
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
