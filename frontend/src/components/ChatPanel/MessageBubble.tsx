import { useState } from 'react'
import { ChevronDown, ChevronRight, Wrench, AlertCircle } from 'lucide-react'
import { useAppStore } from '../../store/appStore'

interface Citation {
  index: number
  file_path: string
  start_line: number
  end_line: number
  symbol_name?: string
  chunk_type?: string
}

interface ToolCall {
  tool_name: string
  tool_input: Record<string, unknown>
  tool_output: unknown
  duration_ms: number
  error?: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: Citation[]
  toolCalls: ToolCall[]
  isStreaming: boolean
  totalTokens?: number
  costUsd?: number
}

export function MessageBubble({ message }: { message: Message }) {
  const openFile = useAppStore((s) => s.openFile)

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-indigo-600/30 border border-indigo-500/30 rounded-2xl rounded-tr-sm px-4 py-2 text-sm text-gray-200">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Tool call cards */}
      {message.toolCalls.map((tc, i) => (
        <ToolCallCard key={i} toolCall={tc} />
      ))}

      {/* Answer bubble */}
      <div className="max-w-[95%] bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm px-4 py-3">
        <p className="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed">
          {message.content}
          {message.isStreaming && (
            <span className="inline-block w-1.5 h-4 bg-indigo-400 ml-0.5 animate-pulse" />
          )}
        </p>

        {/* Citations */}
        {message.sources.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {message.sources.map((src) => (
              <button
                key={src.index}
                onClick={() => openFile(src.file_path, [src.start_line, src.end_line])}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-indigo-900/50 hover:bg-indigo-800/60 border border-indigo-700/50 rounded text-xs text-indigo-300 transition-colors"
                title={src.symbol_name ? `${src.chunk_type}: ${src.symbol_name}` : src.file_path}
              >
                [{src.index}] {src.file_path.split('/').pop()}:{src.start_line}
              </button>
            ))}
          </div>
        )}

        {/* Token usage */}
        {!message.isStreaming && message.totalTokens !== undefined && message.totalTokens > 0 && (
          <div className="mt-2 text-xs text-gray-600">
            {message.totalTokens} tokens
          </div>
        )}
      </div>
    </div>
  )
}

function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false)
  const hasError = !!toolCall.error

  return (
    <div className={`border rounded-lg text-xs overflow-hidden ${
      hasError
        ? 'border-red-800/50 bg-red-950/20'
        : 'border-amber-800/30 bg-amber-950/10'
    }`}>
      {/* Header */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 transition-colors"
      >
        {hasError
          ? <AlertCircle size={12} className="text-red-400 flex-shrink-0" />
          : <Wrench size={12} className="text-amber-400 flex-shrink-0" />}
        <span className="font-mono text-amber-300 flex-1">{toolCall.tool_name}</span>
        <span className="text-gray-600">{toolCall.duration_ms}ms</span>
        {expanded
          ? <ChevronDown size={12} className="text-gray-500" />
          : <ChevronRight size={12} className="text-gray-500" />}
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-3 flex flex-col gap-2 border-t border-white/5">
          {/* Input */}
          <div>
            <div className="text-gray-600 mt-2 mb-1">Input</div>
            <pre className="text-gray-400 bg-black/20 rounded p-2 overflow-x-auto text-xs">
              {JSON.stringify(toolCall.tool_input, null, 2)}
            </pre>
          </div>
          {/* Output / Error */}
          <div>
            <div className="text-gray-600 mb-1">{hasError ? 'Error' : 'Output'}</div>
            <pre className={`rounded p-2 overflow-x-auto text-xs max-h-48 overflow-y-auto ${
              hasError ? 'text-red-400 bg-red-950/30' : 'text-gray-400 bg-black/20'
            }`}>
              {hasError
                ? toolCall.error
                : JSON.stringify(toolCall.tool_output, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
