const BASE_URL = '/api'

export interface Project {
  id: string
  name: string
  url: string | null
  local_path: string | null
  status: 'pending' | 'cloning' | 'walking' | 'chunking' | 'embedding' | 'umap' | 'ready' | 'error'
  error_message: string | null
  chunk_count: number
  file_count: number
  languages: string | null
  umap_ready: boolean
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  url?: string
  local_path?: string
}

export interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  language?: string
  children?: FileNode[]
}

export interface UmapPoint {
  x: number
  y: number
  chunk_id: string
  chunk_type: string
  file_path: string
  symbol_name?: string
  language?: string
  cluster?: number
}

export interface UmapData {
  points: UmapPoint[]
  clusters: { id: number; label: string; centroid: [number, number] }[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Request failed')
  }
  return res.json()
}

export const api = {
  health: () => request<{ status: string; version: string }>('/health'),

  projects: {
    list: () => request<Project[]>('/projects/'),
    get: (id: string) => request<Project>(`/projects/${id}`),
    create: (data: ProjectCreate) =>
      request<Project>('/projects/', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: string) =>
      request<void>(`/projects/${id}`, { method: 'DELETE' }),
    tree: (id: string) => request<{ tree: FileNode[] }>(`/projects/${id}/tree`),
    embeddings: (id: string) => request<UmapData>(`/projects/${id}/embeddings`),
    file: (id: string, path: string) =>
      fetch(`${BASE_URL}/projects/${id}/file?path=${encodeURIComponent(path)}`)
        .then(r => r.text()),
  },
}