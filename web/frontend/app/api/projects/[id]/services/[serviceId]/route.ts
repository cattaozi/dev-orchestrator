import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export async function PUT(
  request: Request,
  { params }: { params: { id: string; serviceId: string } }
) {
  const body = await request.json()
  try {
    const res = await fetch(`${API_BASE}/projects/${params.id}/services/${params.serviceId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: { id: string; serviceId: string } }
) {
  try {
    const res = await fetch(`${API_BASE}/projects/${params.id}/services/${params.serviceId}`, {
      method: 'DELETE',
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
