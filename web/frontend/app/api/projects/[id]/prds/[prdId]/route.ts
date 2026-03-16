import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export async function GET(
  request: Request,
  { params }: { params: { id: string; prdId: string } }
) {
  const projectId = params.id
  const prdId = params.prdId

  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/prds/${prdId}`)
    if (!res.ok) {
      return NextResponse.json({ error: 'PRD not found' }, { status: 404 })
    }
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}