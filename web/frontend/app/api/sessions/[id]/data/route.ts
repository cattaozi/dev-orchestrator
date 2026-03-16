import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export const dynamic = 'force-dynamic'

export async function DELETE(
  request: Request,
  { params }: { params: { id: string } }
) {
  const sessionId = params.id
  try {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/data`, {
      method: 'DELETE'
    })
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
