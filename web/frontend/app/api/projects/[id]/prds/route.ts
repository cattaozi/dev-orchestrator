import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export async function GET(request: Request, { params }: { params: { id: string } }) {
  const projectId = params.id
  
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/prds`)
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}

export async function POST(request: Request, { params }: { params: { id: string } }) {
  const projectId = params.id
  const body = await request.json()
  
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/prds`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
