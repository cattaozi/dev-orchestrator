import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/sessions`)
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}

export async function POST(request: Request) {
  const body = await request.json()
  try {
    const res = await fetch(`${API_BASE}/sessions`, {
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

export async function DELETE(request: Request) {
  const { pathname } = new URL(request.url)
  const id = pathname.split('/').pop()
  try {
    await fetch(`${API_BASE}/sessions/${id}`, { method: 'DELETE' })
    return NextResponse.json({ success: true })
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
