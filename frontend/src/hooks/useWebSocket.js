import { useEffect, useRef } from 'react'
import useAppStore from '../store/appStore'

// In dev: connect directly to backend (Vite WS proxy may conflict with HMR)
// In prod: use relative path (behind reverse proxy)
const WS_HOST = import.meta.env.DEV ? 'localhost:8001' : window.location.host
const WS_URL = `ws://${WS_HOST}/ws`

export function useWebSocket() {
  const ws = useRef(null)
  const pingInterval = useRef(null)
  const reconnectTimeout = useRef(null)
  const { setWsConnected, updateEngagement, addAlert, handleSessionStatus, startSession } = useAppStore()

  const connect = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) return

    ws.current = new WebSocket(WS_URL)

    ws.current.onopen = () => {
      setWsConnected(true)
      // Ping every 25s
      pingInterval.current = setInterval(() => {
        if (ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send(JSON.stringify({ type: 'ping' }))
        }
      }, 25000)
    }

    ws.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        switch (msg.type) {
          case 'engagement_update':
            updateEngagement(msg.data)
            break
          case 'alert':
            addAlert(msg.data)
            break
          case 'session_status':
            handleSessionStatus(msg.data)
            break
          case 'init':
          case 'heartbeat':
            // Fix W2: chỉ startSession khi có session_id hợp lệ
            if (msg.data?.session_active && msg.data?.active_session_id) {
              startSession(msg.data.active_session_id)
            }
            break
        }
      } catch (e) {
        console.error('[WS] Parse error:', e)
      }
    }

    ws.current.onclose = () => {
      setWsConnected(false)
      clearInterval(pingInterval.current)
      reconnectTimeout.current = setTimeout(connect, 3000)
    }

    ws.current.onerror = () => {
      setWsConnected(false)
    }
  }

  useEffect(() => {
    connect()
    return () => {
      clearInterval(pingInterval.current)
      clearTimeout(reconnectTimeout.current)
      ws.current?.close()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return ws
}
