import { FolderOpen, FileCode, Loader2 } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { useFileTree } from '../../hooks/useProject'
import type { FileNode } from '../../api/client'

const LANG_COLORS: Record<string, string> = {
  python: 'bg-blue-500',
  typescript: 'bg-cyan-400',
  javascript: 'bg-yellow-400',
  go: 'bg-teal-400',
  rust: 'bg-orange-500',
  markdown: 'bg-gray-400',
}

function FileRow({ node, depth }: { node: FileNode; depth: number }) {
  const openFile = useAppStore((s) => s.openFile)
  const activeFile = useAppStore((s) => s.activeFile)
  const isActive = activeFile?.path === node.path

  if (node.type === 'directory') {
    return (
      <div>
        <div
          className="flex items-center gap-1 py-0.5 px-2 text-gray-400 text-xs"
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
        >
          <FolderOpen size={13} />
          <span>{node.name}</span>
        </div>
        {node.children?.map((child) => (
          <FileRow key={child.path} node={child} depth={depth + 1} />
        ))}
      </div>
    )
  }

  const dot = node.language ? LANG_COLORS[node.language] ?? 'bg-gray-500' : 'bg-gray-500'

  return (
    <button
      onClick={() => openFile(node.path)}
      className={`w-full flex items-center gap-2 py-0.5 text-xs text-left transition-colors
        ${ isActive ? 'bg-indigo-900/60 text-white' : 'text-gray-300 hover:bg-white/5' }`}
      style={{ paddingLeft: `${depth * 12 + 8}px` }}
    >
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dot}`} />
      <FileCode size={12} className="flex-shrink-0 text-gray-500" />
      <span className="truncate">{node.name}</span>
    </button>
  )
}

export function FileExplorer() {
  const activeProject = useAppStore((s) => s.activeProject)
  const { data, isLoading } = useFileTree(
    activeProject?.status === 'ready' ? activeProject.id : null
  )

  if (!activeProject) {
    return (
      <div className="flex items-center justify-center h-full text-gray-600 text-sm">
        No project selected
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full gap-2 text-gray-500 text-sm">
        <Loader2 size={16} className="animate-spin" /> Loading tree...
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto py-2">
      {data?.tree.map((node) => (
        <FileRow key={node.path} node={node} depth={0} />
      ))}
    </div>
  )
}