import { create } from 'zustand'
import type { Project, UmapPoint } from '../api/client'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: Citation[]
  toolCalls: ToolCall[]
  isStreaming: boolean
  totalTokens?: number
  costUsd?: number
}

interface Citation {
  index: number
  file_path: string
  start_line: number
  end_line: number
  symbol_name?: string
}

interface ToolCall {
  tool_name: string
  tool_input: Record<string, unknown>
  tool_output: unknown
  duration_ms: number
}

interface AppState {
  // Active project
  activeProject: Project | null
  setActiveProject: (p: Project | null) => void

  // Middle pane mode
  middlePane: 'map' | 'preview'
  setMiddlePane: (mode: 'map' | 'preview') => void

  // Active file in preview
  activeFile: { path: string; highlightLines?: [number, number] } | null
  openFile: (path: string, lines?: [number, number]) => void

  // Chat
  chatMode: 'rag' | 'agent'
  setChatMode: (mode: 'rag' | 'agent') => void
  messages: ChatMessage[]
  addMessage: (msg: ChatMessage) => void
  appendToken: (id: string, token: string) => void
  finalizeMessage: (id: string, sources: Citation[], tokens: number, cost: number, toolCalls?: ToolCall[]) => void
  clearMessages: () => void

  // Highlighted points in scatter (from last retrieval)
  highlightedChunkIds: Set<string>
  setHighlightedChunks: (ids: string[]) => void

  // Color mode for scatter
  scatterColorMode: 'chunk_type' | 'language' | 'cluster'
  setScatterColorMode: (mode: 'chunk_type' | 'language' | 'cluster') => void
}

export const useAppStore = create<AppState>((set) => ({
  activeProject: null,
  setActiveProject: (p) => set({ activeProject: p, messages: [], highlightedChunkIds: new Set() }),

  middlePane: 'map',
  setMiddlePane: (mode) => set({ middlePane: mode }),

  activeFile: null,
  openFile: (path, lines) => set({ activeFile: { path, highlightLines: lines }, middlePane: 'preview' }),

  chatMode: 'rag',
  setChatMode: (mode) => set({ chatMode: mode }),

  messages: [],
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendToken: (id, token) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + token } : m
      ),
    })),
  finalizeMessage: (id, sources, tokens, cost, toolCalls = []) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id
          ? { ...m, isStreaming: false, sources, totalTokens: tokens, costUsd: cost, toolCalls }
          : m
      ),
    })),
  clearMessages: () => set({ messages: [] }),

  highlightedChunkIds: new Set(),
  setHighlightedChunks: (ids) => set({ highlightedChunkIds: new Set(ids) }),

  scatterColorMode: 'chunk_type',
  setScatterColorMode: (mode) => set({ scatterColorMode: mode }),
}))