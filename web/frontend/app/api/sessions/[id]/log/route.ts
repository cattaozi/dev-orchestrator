import { NextResponse } from 'next/server'

const API_BASE = 'http://127.0.0.1:8000/api'

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const sessionId = params.id
  try {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/log`)
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
