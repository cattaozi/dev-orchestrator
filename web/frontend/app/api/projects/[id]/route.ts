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
