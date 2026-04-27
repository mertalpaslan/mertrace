import { useEffect, useRef, useState } from 'react'
import { Loader2, FileX } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { api } from '../../api/client'

export function FilePreview() {
  const activeProject = useAppStore((s) => s.activeProject)
  const activeFile = useAppStore((s) => s.activeFile)
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!activeProject || !activeFile) {
      setContent(null)
      return
    }
    setLoading(true)
    setError(null)
    api.projects
      .file(activeProject.id, activeFile.path)
      .then((text) => setContent(text))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [activeProject?.id, activeFile?.path])

  // Auto-scroll to first highlighted line — must be before any early returns
  const hlStart = activeFile?.highlightLines?.[0] ?? 0
  const hlEnd = activeFile?.highlightLines?.[1] ?? 0
  useEffect(() => {
    if (!hlStart || !scrollRef.current) return
    const target = scrollRef.current.querySelector(`#line-${hlStart}`)
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [hlStart, content])

  if (!activeFile) {
    return (
      <div className="flex items-center justify-center h-full text-gray-600 text-sm">
        Click a file or citation to preview
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full gap-2 text-gray-500 text-sm">
        <Loader2 size={16} className="animate-spin" /> Loading file...
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-red-400 text-sm">
        <FileX size={24} />
        <span>{error}</span>
      </div>
    )
  }

  const lines = content?.split('\n') ?? []

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="px-3 py-1.5 border-b border-white/10 text-xs text-gray-400 truncate flex-shrink-0">
        {activeFile.path}
      </div>
      <div ref={scrollRef} className="flex-1 overflow-auto">
        <table className="w-full text-xs font-mono">
          <tbody>
            {lines.map((line, i) => {
              const lineNum = i + 1
              const isHighlighted = hlStart > 0 && lineNum >= hlStart && lineNum <= hlEnd
              return (
                <tr
                  key={i}
                  id={`line-${lineNum}`}
                  className={isHighlighted ? 'bg-indigo-900/40' : ''}
                >
                  <td className="select-none text-right pr-4 pl-3 text-gray-600 w-10">
                    {lineNum}
                  </td>
                  <td className="pr-4 text-gray-300 whitespace-pre">{line}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}