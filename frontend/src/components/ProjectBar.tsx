import { useState, useEffect, useRef } from 'react'
import { Plus, ChevronDown, Loader2, CheckCircle, AlertCircle, Wifi, WifiOff } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { useProjects, useCreateProject } from '../hooks/useProject'
import { useWebSocket } from '../hooks/useWebSocket'
import type { Project } from '../api/client'
import { useQueryClient } from '@tanstack/react-query'

const STATUS_ICON: Record<string, React.ReactNode> = {
  ready:     <CheckCircle size={12} className="text-emerald-400" />,
  error:     <AlertCircle size={12} className="text-red-400" />,
  pending:   <Loader2 size={12} className="animate-spin text-gray-400" />,
  cloning:   <Loader2 size={12} className="animate-spin text-blue-400" />,
  walking:   <Loader2 size={12} className="animate-spin text-blue-400" />,
  chunking:  <Loader2 size={12} className="animate-spin text-indigo-400" />,
  embedding: <Loader2 size={12} className="animate-spin text-indigo-400" />,
  umap:      <Loader2 size={12} className="animate-spin text-purple-400" />,
}

const STAGE_LABEL: Record<string, string> = {
  cloning:   'Cloning repository...',
  walking:   'Walking files...',
  chunking:  'Chunking code...',
  embedding: 'Embedding chunks...',
  umap:      'Building UMAP...',
  ready:     'Ready',
}

export function ProjectBar() {
  const [open, setOpen] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [progress, setProgress] = useState<{ stage: string; pct: number } | null>(null)

  const activeProject = useAppStore((s) => s.activeProject)
  const setActiveProject = useAppStore((s) => s.setActiveProject)
  const { data: projects = [] } = useProjects()
  const createProject = useCreateProject()
  const queryClient = useQueryClient()

  const isIndexing = activeProject != null &&
    !['ready', 'error', 'pending'].includes(activeProject.status)

  const { status: wsStatus } = useWebSocket({
    projectId: activeProject?.id ?? null,
    enabled: !!activeProject,
    onMessage: (msg) => {
      const type = msg.type as string
      if (type === 'index.progress') {
        setProgress({ stage: msg.stage as string, pct: msg.pct as number })
      } else if (type === 'index.done') {
        setProgress(null)
        // Refresh project list to get updated status
        queryClient.invalidateQueries({ queryKey: ['projects'] })
      } else if (type === 'index.error') {
        setProgress(null)
        queryClient.invalidateQueries({ queryKey: ['projects'] })
      }
    },
  })

  // Clear progress when project changes
  useEffect(() => { setProgress(null) }, [activeProject?.id])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    createProject.mutate(
      { name: name.trim() || url.split('/').pop() || 'project', url: url.trim() },
      {
        onSuccess: (project) => {
          setShowForm(false)
          setUrl('')
          setName('')
          setActiveProject(project)
          setOpen(false)
        },
      }
    )
  }

  return (
    <div className="relative flex items-center gap-3">
      {/* Project selector */}
      <button
        onClick={() => { setOpen((o) => !o); setShowForm(false) }}
        className="flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-sm transition-colors"
      >
        {activeProject ? (
          <>
            {STATUS_ICON[activeProject.status]}
            <span className="max-w-[180px] truncate">{activeProject.name}</span>
          </>
        ) : (
          <span className="text-gray-500">Select project</span>
        )}
        <ChevronDown size={14} className="text-gray-500" />
      </button>

      {/* Live progress bar */}
      {(isIndexing || progress) && (
        <div className="flex items-center gap-2 min-w-[200px]">
          <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all duration-500"
              style={{ width: `${progress?.pct ?? 5}%` }}
            />
          </div>
          <span className="text-xs text-gray-500 whitespace-nowrap">
            {STAGE_LABEL[progress?.stage ?? activeProject?.status ?? ''] ?? 'Indexing...'}
          </span>
        </div>
      )}

      {/* WS status dot */}
      {activeProject && (
        <span title={`WebSocket: ${wsStatus}`}>
          {wsStatus === 'connected'
            ? <Wifi size={12} className="text-emerald-500/60" />
            : <WifiOff size={12} className="text-gray-600" />}
        </span>
      )}

      {/* Dropdown */}
      {open && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-gray-900 border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden">
          {projects.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-500">No projects yet</div>
          ) : (
            <ul className="max-h-64 overflow-y-auto">
              {projects.map((p: Project) => (
                <li key={p.id}>
                  <button
                    onClick={() => { setActiveProject(p); setOpen(false) }}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-white/5 text-left transition-colors"
                  >
                    {STATUS_ICON[p.status]}
                    <span className="flex-1 truncate">{p.name}</span>
                    <span className="text-xs text-gray-600">{p.chunk_count} chunks</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-white/10 p-2">
            <button
              onClick={() => { setShowForm((s) => !s); setOpen(false) }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-indigo-400 hover:bg-indigo-900/30 rounded-lg transition-colors"
            >
              <Plus size={14} /> Index new repo
            </button>
          </div>
        </div>
      )}

      {/* New project form */}
      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="absolute top-full left-0 mt-1 w-80 bg-gray-900 border border-white/10 rounded-xl shadow-2xl z-50 p-4 flex flex-col gap-3"
        >
          <p className="text-sm font-medium text-gray-300">Index a repository</p>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500"
          />
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name (optional)"
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={!url.trim() || createProject.isPending}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 rounded-lg py-2 text-sm font-medium transition-colors"
          >
            {createProject.isPending ? 'Submitting...' : 'Start Indexing'}
          </button>
        </form>
      )}
    </div>
  )
}
