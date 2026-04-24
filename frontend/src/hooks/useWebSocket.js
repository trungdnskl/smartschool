import { useEffect, useRef, useCallback } from 'react'
import useAppStore from '../store/appStore'

// In dev: connect directly to backend (Vite WS proxy may conflict with HMR)
// In prod: use relative path (behind reverse proxy)
const WS_HOST = import.meta.env.DEV ? 'localhost:8001' : window.location.host
const WS_URL = `ws://${WS_HOST}/ws`

// ── Reconnect config ────────────────────────────────────
const RECONNECT_BASE_MS = 1000   // Start at 1s
const RECONNECT_MAX_MS = 30000   // Cap at 30s
const PING_INTERVAL_MS = 25000

export function useWebSocket() {
  const ws = useRef(null)
  const pingInterval = useRef(null)
  const reconnectTimeout = useRef(null)
  const reconnectAttempt = useRef(0)
  const isVisible = useRef(true)

  // Narrow selectors to avoid unnecessary re-renders (tối ưu #2)
  const setWsConnected = useAppStore(s => s.setWsConnected)
  const updateEngagement = useAppStore(s => s.updateEngagement)
  const addAlert = useAppStore(s => s.addAlert)
  const handleSessionStatus = useAppStore(s => s.handleSessionStatus)
  const startSession = useAppStore(s => s.startSession)

  const connect = useCallback(() => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) return
    // Don't reconnect if tab is hidden (tối ưu #3 — save bandwidth)
    if (!isVisible.current) return

    try {
      ws.current = new WebSocket(WS_URL)
    } catch (e) {
      console.error('[WS] Failed to create WebSocket:', e)
      scheduleReconnect()
      return
    }

    ws.current.onopen = () => {
      setWsConnected(true)
      reconnectAttempt.current = 0  // Reset backoff on success
      // Ping every 25s
      pingInterval.current = setInterval(() => {
        if (ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send(JSON.stringify({ type: 'ping' }))
        }
      }, PING_INTERVAL_MS)
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
      scheduleReconnect()
    }

    ws.current.onerror = () => {
      setWsConnected(false)
    }
  }, [setWsConnected, updateEngagement, addAlert, handleSessionStatus, startSession])

  // Exponential backoff reconnect (tối ưu #3)
  const scheduleReconnect = useCallback(() => {
    clearTimeout(reconnectTimeout.current)
    const attempt = reconnectAttempt.current++
    const delay = Math.min(RECONNECT_BASE_MS * Math.pow(2, attempt), RECONNECT_MAX_MS)
    console.log(`[WS] Reconnect in ${delay}ms (attempt ${attempt + 1})`)
    reconnectTimeout.current = setTimeout(connect, delay)
  }, [connect])

  // Visibility API — pause WS when tab hidden, resume when visible (tối ưu #3)
  useEffect(() => {
    const handleVisibility = () => {
      isVisible.current = !document.hidden
      if (!document.hidden && (!ws.current || ws.current.readyState !== WebSocket.OPEN)) {
        reconnectAttempt.current = 0  // Reset backoff when user returns
        connect()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [connect])

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
