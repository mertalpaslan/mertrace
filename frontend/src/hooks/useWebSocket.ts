import { useEffect, useRef, useCallback, useState } from 'react'

type WSMessage = Record<string, unknown>
type MessageHandler = (msg: WSMessage) => void

export type WSStatus = 'disconnected' | 'connecting' | 'connected'

interface UseWebSocketOptions {
  projectId: string | null
  onMessage: MessageHandler
  enabled?: boolean
}

// Use relative WS URL so it routes through the Vite proxy in dev
// and works correctly behind any reverse proxy in production.
function getWsBase(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}`
}

const MAX_RETRIES = 6
const BASE_DELAY_MS = 500

export function useWebSocket({ projectId, onMessage, enabled = true }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const onMessageRef = useRef(onMessage)
  const unmountedRef = useRef(false)
  const [status, setStatus] = useState<WSStatus>('disconnected')

  // Keep handler ref fresh without re-connecting
  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])

  const connect = useCallback(() => {
    if (!projectId || !enabled || unmountedRef.current) return

    const url = `${getWsBase()}/ws/${projectId}`
    setStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      retriesRef.current = 0
      setStatus('connected')
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage
        onMessageRef.current(msg)
      } catch {
        console.error('[WS] Failed to parse message', event.data)
      }
    }

    ws.onclose = () => {
      setStatus('disconnected')
      if (unmountedRef.current) return
      if (retriesRef.current >= MAX_RETRIES) {
        console.error('[WS] Max retries reached, giving up')
        return
      }
      const delay = BASE_DELAY_MS * Math.pow(2, retriesRef.current)
      retriesRef.current += 1
      setTimeout(connect, delay)
    }

    ws.onerror = (err) => {
      console.error('[WS] Error', err)
      ws.close()
    }
  }, [projectId, enabled])

  useEffect(() => {
    unmountedRef.current = false
    connect()
    return () => {
      unmountedRef.current = true
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((msg: WSMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    } else {
      console.warn('[WS] Cannot send — socket not open')
    }
  }, [])

  return { send, status }
}