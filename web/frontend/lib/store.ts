import { create } from 'zustand'

interface Project {
  id: number
  name: string
  description: string
  local_path: string
  status: string
  favorited: boolean
  created_at: string
}

interface Session {
  id: number
  issue_id: number
  branch: string
  worktree_path: string
  status: string
  agent_type: string
  runtime: string
  created_at: string
}

interface AppState {
  projects: Project[]
  sessions: Session[]
  loading: boolean
  error: string | null
  fetchProjects: () => Promise<void>
  fetchSessions: () => Promise<void>
  setError: (error: string | null) => void
}

export const useStore = create<AppState>((set) => ({
  projects: [],
  sessions: [],
  loading: false,
  error: null,

  fetchProjects: async () => {
    set({ loading: true, error: null })
    try {
      const res = await fetch('/api/projects')
      if (!res.ok) throw new Error('Failed to fetch')
      const projects = await res.json()
      set({ projects, loading: false })
    } catch (e) {
      console.error('fetchProjects error:', e)
      set({ error: (e as Error).message, loading: false })
    }
  },

  fetchSessions: async () => {
    try {
      const res = await fetch('/api/sessions')
      if (!res.ok) throw new Error('Failed to fetch')
      const sessions = await res.json()
      set({ sessions })
    } catch (e) {
      console.error('fetchSessions error:', e)
    }
  },

  setError: (error) => set({ error }),
}))
