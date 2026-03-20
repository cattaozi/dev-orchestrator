const API_BASE = '/api'

export interface Project {
  id: number
  name: string
  local_path: string
  status: string
  created_at: string
}

export interface Session {
  id: number
  issue_id: number
  branch: string
  worktree_path: string
  status: string
  agent_type: string
  runtime: string
  prompt: string
  created_at: string
  started_at: string | null
  completed_at: string | null
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  // 直接调用同端口的 Next.js API，Next.js 会代理到后端
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API Error: ${res.status}`)
  }
  return res.json()
}

export async function getProjects(): Promise<Project[]> {
  return fetchAPI<Project[]>('/projects')
}

export async function getProject(id: number): Promise<Project> {
  return fetchAPI<Project>(`/projects/${id}`)
}

export async function createProject(data: Partial<Project>): Promise<Project> {
  return fetchAPI<Project>('/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function deleteProject(id: number): Promise<void> {
  await fetchAPI(`/projects/${id}`, { method: 'DELETE' })
}

export async function getSessions(): Promise<Session[]> {
  return fetchAPI<Session[]>('/sessions')
}

export async function createSession(issueId: number): Promise<Session> {
  return fetchAPI<Session>('/sessions', {
    method: 'POST',
    body: JSON.stringify({ issue_id: issueId }),
  })
}

export async function killSession(id: number): Promise<void> {
  await fetchAPI(`/sessions/${id}`, { method: 'DELETE' })
}

export interface SessionEvent {
  id: number
  type: string
  role: string
  content: string
  tool_name: string
  tool_input: string
  created_at: string
}

export interface SessionEventsResponse {
  events: SessionEvent[]
  status: string
}

export async function getSessionEvents(sessionId: number): Promise<SessionEventsResponse> {
  return fetchAPI<SessionEventsResponse>(`/sessions/${sessionId}/events`)
}

export interface HistoryEntry {
  role: string
  content: string
  tool?: string
  tool_input?: any
}

export interface SessionHistoryResponse {
  history: HistoryEntry[]
}

export async function getSessionHistory(sessionId: number): Promise<SessionHistoryResponse> {
  return fetchAPI<SessionHistoryResponse>(`/sessions/${sessionId}/history`)
}

export async function sendSessionMessage(sessionId: number, content: string, role: string = "user"): Promise<void> {
  await fetchAPI(`/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content, role }),
  })
}
