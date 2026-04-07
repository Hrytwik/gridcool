import { useEffect, useMemo, useRef, useState } from 'react'
import type { DashboardSnapshot } from './dashboardTypes'

type Status = 'connecting' | 'open' | 'closed' | 'error'

export function useDashboardSocket(baseUrl?: string) {
  const [status, setStatus] = useState<Status>('connecting')
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)

  const wsUrl = useMemo(() => {
    const inferredHttp = baseUrl ?? import.meta.env.VITE_BACKEND_HTTP ?? 'http://localhost:8000'
    const asWs = inferredHttp.replace(/^http/i, (m: string) =>
      m.toLowerCase() === 'https' ? 'wss' : 'ws',
    )
    return `${asWs}/ws/dashboard`
  }, [baseUrl])

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)

  useEffect(() => {
    let didCancel = false

    const connect = () => {
      setStatus('connecting')
      setLastError(null)

      try {
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
          if (didCancel) return
          setStatus('open')
        }

        ws.onmessage = (evt) => {
          if (didCancel) return
          try {
            const data = JSON.parse(String(evt.data)) as DashboardSnapshot
            setSnapshot(data)
          } catch {
            // keep UI resilient; ignore malformed payloads
          }
        }

        ws.onerror = () => {
          if (didCancel) return
          setStatus('error')
          setLastError('WebSocket error')
        }

        ws.onclose = () => {
          if (didCancel) return
          setStatus('closed')
          if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
          reconnectTimerRef.current = window.setTimeout(connect, 1200)
        }
      } catch (e) {
        setStatus('error')
        setLastError(e instanceof Error ? e.message : 'Failed to connect')
      }
    }

    connect()

    return () => {
      didCancel = true
      if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [wsUrl])

  return { status, snapshot, lastError, wsUrl }
}

