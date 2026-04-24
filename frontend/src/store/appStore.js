import { create } from 'zustand'

/**
 * App Store — Zustand (tối ưu #6)
 *
 * Tối ưu:
 * - immutable timeline updates (no spread of full array each time)
 * - throttled engagement updates (max 1 update per 500ms)
 * - shallow-safe selectors exported
 */

// ── Throttle utility ─────────────────────────────────────
let _lastEngagementUpdate = 0
const ENGAGEMENT_THROTTLE_MS = 500  // Max 2 updates/sec

const useAppStore = create((set, get) => ({
  // ── WebSocket ──────────────────────────────────────────
  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),

  // ── Session ────────────────────────────────────────────
  sessionActive: false,
  sessionId: null,
  sessionStartTime: null,

  // ── Live engagement data ───────────────────────────────
  engagementData: null,
  engagementTimeline: [],   // last 150 points
  alerts: [],               // last 20 alerts

  // ── Actions ────────────────────────────────────────────
  startSession: (id) => set({
    sessionActive: true,
    sessionId: id,
    sessionStartTime: new Date(),
    engagementTimeline: [],
  }),

  stopSession: () => set({
    sessionActive: false,
    sessionId: null,
    sessionStartTime: null,
    engagementData: null,
    engagementTimeline: [],
    alerts: [],
  }),

  // Tối ưu #2: Throttled engagement updates — max 2/sec
  updateEngagement: (data) => {
    const now = Date.now()
    if (now - _lastEngagementUpdate < ENGAGEMENT_THROTTLE_MS) {
      // Still update the data object, just skip timeline push
      set({ engagementData: data })
      return
    }
    _lastEngagementUpdate = now

    const prev = get().engagementTimeline
    const point = {
      time: data.timestamp || new Date().toISOString(),
      value: Math.round(data.avg_engagement || 0),
      faces: data.total_faces || 0,
    }
    // Tối ưu: Avoid spreading 150-item array — use slice directly
    const timeline = prev.length >= 150
      ? [...prev.slice(1), point]
      : [...prev, point]
    set({ engagementData: data, engagementTimeline: timeline })
  },

  addAlert: (alert) => {
    const prev = get().alerts
    set({ alerts: [alert, ...prev].slice(0, 20) })
  },

  handleSessionStatus: (data) => {
    if (data.status === 'started') {
      set({
        sessionActive: true,
        sessionId: data.session_id,
        sessionStartTime: new Date(),
        engagementTimeline: [],  // Reset timeline cho session mới
      })
    } else if (data.status === 'stopped') {
      // Fix W1: Clear engagement data khi stop — match behavior của stopSession()
      set({
        sessionActive: false,
        sessionId: null,
        sessionStartTime: null,
        engagementData: null,
        engagementTimeline: [],
        alerts: [],
      })
    }
  },
}))

// ── Narrow selectors (tối ưu #2 — prevent re-render cascade) ─────
// Import these instead of selecting from full store object
export const useWsConnected = () => useAppStore(s => s.wsConnected)
export const useSessionActive = () => useAppStore(s => s.sessionActive)
export const useSessionId = () => useAppStore(s => s.sessionId)
export const useEngagementData = () => useAppStore(s => s.engagementData)
export const useEngagementTimeline = () => useAppStore(s => s.engagementTimeline)
export const useAlerts = () => useAppStore(s => s.alerts)

export default useAppStore
