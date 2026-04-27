import { Component, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FileExplorer } from './components/FileExplorer'
import { VectorViz } from './components/VectorViz'
import { ChatPanel } from './components/ChatPanel'
import { ProjectBar } from './components/ProjectBar'
import { useAppStore } from './store/appStore'
import { AlertTriangle } from 'lucide-react'

// ── Error Boundary ────────────────────────────────────────────────────────────
interface EBState { error: Error | null }
class ErrorBoundary extends Component<{ children: ReactNode; label?: string }, EBState> {
  state: EBState = { error: null }
  static getDerivedStateFromError(error: Error): EBState { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center h-full gap-2 text-red-400 text-xs p-4">
          <AlertTriangle size={20} />
          <span className="font-medium">{this.props.label ?? 'Component error'}</span>
          <span className="text-gray-600 text-center">{this.state.error.message}</span>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 px-3 py-1 bg-white/5 hover:bg-white/10 rounded text-gray-400 transition-colors"
          >Retry</button>
        </div>
      )
    }
    return this.props.children
  }
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

function ScatterControls() {
  const mode = useAppStore((s) => s.scatterColorMode)
  const setMode = useAppStore((s) => s.setScatterColorMode)
  const activeProject = useAppStore((s) => s.activeProject)
  const middlePane = useAppStore((s) => s.middlePane)

  if (!activeProject?.umap_ready || middlePane !== 'map') return null

  return (
    <div className="flex items-center gap-1 text-xs">
      <span className="text-gray-600 mr-1">Color:</span>
      {(['chunk_type', 'language', 'cluster'] as const).map((m) => (
        <button
          key={m}
          onClick={() => setMode(m)}
          className={`px-2 py-0.5 rounded transition-colors ${
            mode === m
              ? 'bg-indigo-600/60 text-indigo-200'
              : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          {m === 'chunk_type' ? 'type' : m}
        </button>
      ))}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="h-screen w-screen bg-gray-950 text-white flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex-shrink-0 h-12 border-b border-white/10 flex items-center px-4 gap-4">
          <span className="font-semibold text-sm tracking-tight">
            <span className="text-indigo-400">⬡</span> Codebase Analyzer
          </span>
          <div className="flex-1">
            <ProjectBar />
          </div>
        </header>

        {/* 3-pane layout */}
        <main className="flex-1 flex overflow-hidden">
          {/* Left pane — File Explorer */}
          <aside className="w-60 flex-shrink-0 border-r border-white/10 overflow-hidden flex flex-col">
            <div className="px-3 py-2 border-b border-white/10 text-xs font-medium text-gray-500 uppercase tracking-wider">
              Explorer
            </div>
            <div className="flex-1 overflow-hidden">
              <ErrorBoundary label="File Explorer">
                <FileExplorer />
              </ErrorBoundary>
            </div>
          </aside>

          {/* Middle pane — Vector Viz / File Preview */}
          <section className="flex-1 border-r border-white/10 overflow-hidden flex flex-col min-w-0">
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/10 flex-shrink-0">
              <ScatterControls />
            </div>
            <div className="flex-1 overflow-hidden">
              <ErrorBoundary label="Vector Viz / File Preview">
                <VectorViz />
              </ErrorBoundary>
            </div>
          </section>

          {/* Right pane — Chat */}
          <aside className="w-96 flex-shrink-0 overflow-hidden flex flex-col">
            <ErrorBoundary label="Chat Panel">
              <ChatPanel />
            </ErrorBoundary>
          </aside>
        </main>
      </div>
    </QueryClientProvider>
  )
}
