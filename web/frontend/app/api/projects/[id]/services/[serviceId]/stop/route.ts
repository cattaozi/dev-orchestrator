import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export async function POST(
  _request: Request,
  { params }: { params: { id: string; serviceId: string } }
) {
  try {
    const res = await fetch(`${API_BASE}/projects/${params.id}/services/${params.serviceId}/stop`, {
      method: 'POST',
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
