import { useRef, useEffect, useState } from 'react'
import * as Plot from '@observablehq/plot'
import { Loader2, Map, FileCode } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { useEmbeddings } from '../../hooks/useProject'
import { FilePreview } from './FilePreview'

const TYPE_COLORS: Record<string, string> = {
  function: '#6366f1',
  method:   '#8b5cf6',
  class:    '#06b6d4',
  import:   '#f59e0b',
  config:   '#10b981',
  fallback: '#6b7280',
}

export function VectorViz() {
  const activeProject = useAppStore((s) => s.activeProject)
  const middlePane = useAppStore((s) => s.middlePane)
  const setMiddlePane = useAppStore((s) => s.setMiddlePane)
  const scatterColorMode = useAppStore((s) => s.scatterColorMode)
  const highlightedChunkIds = useAppStore((s) => s.highlightedChunkIds)
  const openFile = useAppStore((s) => s.openFile)

  const plotRef = useRef<HTMLDivElement>(null)
  const isReady = activeProject?.umap_ready ?? false

  const { data: umapData, isLoading } = useEmbeddings(
    activeProject?.id ?? null,
    isReady
  )

  useEffect(() => {
    if (!umapData || !plotRef.current || middlePane !== 'map') return
    const el = plotRef.current
    el.innerHTML = ''

    const points = umapData.points.map((p) => ({
      ...p,
      highlighted: highlightedChunkIds.has(p.chunk_id),
    }))

    const colorKey = scatterColorMode === 'chunk_type' ? 'chunk_type'
      : scatterColorMode === 'language' ? 'language' : 'cluster'

    const plot = Plot.plot({
      width: el.clientWidth || 600,
      height: el.clientHeight || 500,
      style: { background: 'transparent', color: '#9ca3af' },
      marks: [
        Plot.dot(points, {
          x: 'x', y: 'y',
          fill: colorKey,
          r: (d: typeof points[0]) => d.highlighted ? 5 : 2.5,
          opacity: (d: typeof points[0]) => d.highlighted ? 1 : 0.55,
          tip: true,
          title: (d: typeof points[0]) =>
            `${d.symbol_name ?? d.chunk_type}\n${d.file_path}`,
        }),
      ],
    })

    el.appendChild(plot)
    return () => plot.remove()
  }, [umapData, middlePane, scatterColorMode, highlightedChunkIds])

  return (
    <div className="h-full flex flex-col">
      {/* Tab bar */}
      <div className="flex border-b border-white/10 px-3 pt-2 gap-1 flex-shrink-0">
        <TabBtn active={middlePane === 'map'} onClick={() => setMiddlePane('map')}>
          <Map size={13} /> Map
        </TabBtn>
        <TabBtn active={middlePane === 'preview'} onClick={() => setMiddlePane('preview')}>
          <FileCode size={13} /> Preview
        </TabBtn>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {middlePane === 'map' ? (
          isLoading ? (
            <div className="flex items-center justify-center h-full gap-2 text-gray-500 text-sm">
              <Loader2 size={16} className="animate-spin" /> Computing UMAP...
            </div>
          ) : !umapData ? (
            <div className="flex items-center justify-center h-full text-gray-600 text-sm">
              {activeProject ? 'Index a project to see the embedding map' : 'No project selected'}
            </div>
          ) : (
            <div ref={plotRef} className="w-full h-full" />
          )
        ) : (
          <FilePreview />
        )}
      </div>
    </div>
  )
}

function TabBtn({ active, onClick, children }: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-t transition-colors
        ${active ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-gray-300'}`}
    >
      {children}
    </button>
  )
}