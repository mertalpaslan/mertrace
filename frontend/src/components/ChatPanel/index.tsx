import { useState, useRef, useEffect } from 'react'
import { Send, Loader2 } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { useWebSocket } from '../../hooks/useWebSocket'
import { MessageBubble } from './MessageBubble'
import { v4 as uuidv4 } from 'uuid'

export function ChatPanel() {
  const activeProject = useAppStore((s) => s.activeProject)
  const chatMode = useAppStore((s) => s.chatMode)
  const setChatMode = useAppStore((s) => s.setChatMode)
  const messages = useAppStore((s) => s.messages)
  const addMessage = useAppStore((s) => s.addMessage)
  const appendToken = useAppStore((s) => s.appendToken)
  const finalizeMessage = useAppStore((s) => s.finalizeMessage)
  const setHighlightedChunks = useAppStore((s) => s.setHighlightedChunks)

  const [input, setInput] = useState('')
  const [isWaiting, setIsWaiting] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const assistantIdRef = useRef<string | null>(null)
  // Buffer pending tool calls until chat.done
  const pendingToolCallsRef = useRef<Record<string, unknown>[]>([])

  const { send, status: wsStatus } = useWebSocket({
    projectId: activeProject?.id ?? null,
    enabled: !!activeProject && activeProject.status === 'ready',
    onMessage: (msg) => {
      const type = msg.type as string

      if (type === 'chat.token') {
        if (assistantIdRef.current) appendToken(assistantIdRef.current, msg.token as string)

      } else if (type === 'agent.tool_start') {
        // Store pending tool call (will be completed by agent.tool_done)
        pendingToolCallsRef.current.push({
          tool_name: msg.tool_name,
          tool_input: msg.tool_input,
          tool_output: null,
          duration_ms: 0,
        })

      } else if (type === 'agent.tool_done') {
        // Update the last pending tool call with result
        const last = pendingToolCallsRef.current[pendingToolCallsRef.current.length - 1]
        if (last && last.tool_name === msg.tool_name) {
          last.tool_output = msg.tool_output
          last.duration_ms = msg.duration_ms
          last.error = msg.error
        }

      } else if (type === 'chat.done') {
        setIsWaiting(false)
        if (assistantIdRef.current) {
          const sources = (msg.sources as []) ?? []
          finalizeMessage(
            assistantIdRef.current,
            sources,
            (msg.total_tokens as number) ?? 0,
            (msg.cost_usd as number) ?? 0,
            pendingToolCallsRef.current as never[],
          )
          setHighlightedChunks(
            sources
              .map((s: { chunk_id?: string }) => s.chunk_id ?? '')
              .filter(Boolean)
          )
          pendingToolCallsRef.current = []
        }

      } else if (type === 'error') {
        setIsWaiting(false)
        if (assistantIdRef.current) {
          appendToken(assistantIdRef.current, `\n\n⚠️ ${msg.message as string}`)
          finalizeMessage(assistantIdRef.current, [], 0, 0, [])
        }
      }
    },
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    const query = input.trim()
    if (!query || isWaiting || !activeProject || wsStatus !== 'connected') return

    addMessage({
      id: uuidv4(),
      role: 'user',
      content: query,
      sources: [],
      toolCalls: [],
      isStreaming: false,
    })

    const assistantId = uuidv4()
    assistantIdRef.current = assistantId
    pendingToolCallsRef.current = []
    addMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      sources: [],
      toolCalls: [],
      isStreaming: true,
    })

    const history = messages.slice(-6).map((m) => ({
      role: m.role,
      content: m.content,
    }))
    send({ type: 'chat.message', query, mode: chatMode, history })
    setInput('')
    setIsWaiting(true)
  }

  const isReady = activeProject?.status === 'ready' && wsStatus === 'connected'

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/10 flex-shrink-0">
        <span className="text-sm font-medium text-gray-300">Chat</span>
        <div className="flex bg-white/5 rounded-full p-0.5 text-xs">
          {(['rag', 'agent'] as const).map((m) => (
            <button key={m} onClick={() => setChatMode(m)}
              className={`px-3 py-1 rounded-full transition-colors ${
                chatMode === m ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
              }`}>
              {m.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-600 text-sm">
            {isReady
              ? `Ask anything about the codebase (${chatMode.toUpperCase()} mode)`
              : activeProject
              ? 'Connecting...'
              : 'Index a project to start chatting'}
          </div>
        )}
        {messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-white/10 flex-shrink-0">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder={
              isReady
                ? 'Ask about the codebase...'
                : activeProject
                ? 'Connecting to server...'
                : 'Select a ready project first'
            }
            disabled={!isReady || isWaiting}
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500 disabled:opacity-40"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isWaiting || !isReady}
            className="p-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 rounded-lg transition-colors"
          >
            {isWaiting
              ? <Loader2 size={16} className="animate-spin text-white" />
              : <Send size={16} className="text-white" />}
          </button>
        </div>
      </div>
    </div>
  )
}
