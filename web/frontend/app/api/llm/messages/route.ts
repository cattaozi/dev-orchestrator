import { NextResponse } from "next/server"
import { API_BASE } from "@/lib/backend-config"

export async function POST(request: Request) {
  const body = await request.json()

  try {
    const res = await fetch(`${API_BASE}/llm/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (_error) {
    return NextResponse.json({ error: "Backend unavailable" }, { status: 500 })
  }
}
