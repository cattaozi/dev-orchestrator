import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export const dynamic = 'force-dynamic'

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const sessionId = params.id
  const url = new URL(request.url)
  const afterId = url.searchParams.get('after_id')

  try {
    let fetchUrl = `${API_BASE}/sessions/${sessionId}/events`
    if (afterId) {
      fetchUrl += `?after_id=${afterId}`
    }

    const res = await fetch(fetchUrl, {
      cache: 'no-store',
      headers: {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
      }
    })
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable', events: [] }, { status: 500 })
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: { id: string } }
) {
  const sessionId = params.id
  try {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/events`, { method: 'DELETE' })
    const data = await res.json().catch(() => ({}))
    return NextResponse.json(data, { status: res.status })
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
