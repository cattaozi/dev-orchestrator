import { NextResponse } from 'next/server'
import { API_BASE } from '@/lib/backend-config'

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/projects/dashboard-summary`, { cache: 'no-store' })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
