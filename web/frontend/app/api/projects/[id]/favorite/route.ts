import { NextResponse } from "next/server"
import { API_BASE } from "@/lib/backend-config"

export async function POST(_request: Request, { params }: { params: { id: string } }) {
  const projectId = params.id

  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/favorite`, {
      method: "POST",
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (_error) {
    return NextResponse.json({ error: "Backend unavailable" }, { status: 500 })
  }
}
