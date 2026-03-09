import { NextResponse } from 'next/server'

const API_BASE = 'http://127.0.0.1:8000/api'

export async function GET(request: Request) {
  const { pathname } = new URL(request.url)
  const path = pathname.replace('/api', '')
  
  try {
    const res = await fetch(`${API_BASE}${path}`)
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}

export async function POST(request: Request) {
  const { pathname } = new URL(request.url)
  const path = pathname.replace('/api', '')
  const body = await request.json()
  
  try {
    const res = await fetch(`${API_BASE}${path}`, {
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
  const path = pathname.replace('/api', '')
  
  try {
    await fetch(`${API_BASE}${path}`, { method: 'DELETE' })
    return NextResponse.json({ success: true })
  } catch (error) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 500 })
  }
}
