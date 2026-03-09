import { NextResponse } from 'next/server'

const API_BASE = 'http://127.0.0.1:8000/api'

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
