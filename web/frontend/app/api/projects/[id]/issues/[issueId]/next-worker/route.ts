import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export async function GET(
  request: Request,
  { params }: { params: { id: string; issueId: string } }
) {
  try {
    const res = await fetch(`${API_BASE}/issues/${params.issueId}/next-worker`)
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
