import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export async function PUT(
  request: Request,
  { params }: { params: { id: string; pwId: string } }
) {
  const body = await request.json()
  try {
    const res = await fetch(`${API_BASE}/projects/${params.id}/workers/${params.pwId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: { id: string; pwId: string } }
) {
  try {
    const res = await fetch(`${API_BASE}/projects/${params.id}/workers/${params.pwId}`, {
      method: 'DELETE',
    })
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
