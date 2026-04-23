import { create } from 'zustand'

const useAppStore = create((set, get) => ({
  // WebSocket
  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),

  // Session
  sessionActive: false,
  sessionId: null,
  sessionStartTime: null,

  // Live engagement data
  engagementData: null,
  engagementTimeline: [],   // last 150 points
  alerts: [],               // last 20 alerts

  // Actions
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

  updateEngagement: (data) => {
    const prev = get().engagementTimeline
    const point = {
      time: data.timestamp || new Date().toISOString(),
      value: Math.round(data.avg_engagement || 0),
      faces: data.total_faces || 0,
    }
    const timeline = [...prev, point].slice(-150)
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

export default useAppStore
