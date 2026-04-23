import { useEffect, useState, useRef } from 'react'
import api from '../../hooks/useApi'
import useAppStore from '../../store/appStore'

export default function LiveView() {
  const { sessionActive, engagementData } = useAppStore()
  const [cameras, setCameras] = useState([])
  const [activeCam, setActiveCam] = useState('')
  const [expanded, setExpanded] = useState(true)
  const imgRef = useRef(null)

  useEffect(() => {
    const load = async () => {
      const r = await api.get('/api/cameras')
      if (r.ok) {
        const cams = r.data.cameras || []
        setCameras(cams)
        // Auto-select first running camera
        const running = cams.find(c => c.status === 'running')
        if (running && !activeCam) setActiveCam(running.id)
      }
    }
    load()
    const iv = setInterval(load, 8000)
    return () => clearInterval(iv)
  }, [])

  const runningCams = cameras.filter(c => c.status === 'running')
  const students = engagementData?.students || []
  const totalFaces = engagementData?.total_faces || 0
  const avgEng = engagementData?.avg_engagement || 0

  // Count attendance-like stats
  const recognized = students.filter(s => s.student_name).length
  const unknown = students.filter(s => !s.student_name).length

  if (!expanded) {
    return (
      <div className="card live-mini" onClick={() => setExpanded(true)}>
        <div className="live-mini-bar">
          <span className="live-dot" />
          <span>📺 LiveView</span>
          <span className="live-mini-stats">
            {runningCams.length > 0
              ? `${totalFaces} khuôn mặt • Eng ${Math.round(avgEng)}%`
              : 'Chưa có camera'}
          </span>
          <button className="btn-sm" onClick={e => { e.stopPropagation(); setExpanded(true) }}>▼</button>
        </div>
      </div>
    )
  }

  return (
    <div className="card live-view-dashboard">
      <div className="card-header">
        <div className="live-header-left">
          <span className="live-dot" />
          <h3>📺 Live Camera — Nhận diện & Điểm danh</h3>
        </div>
        <div className="live-header-right">
          {runningCams.length > 1 && (
            <select
              value={activeCam}
              onChange={e => setActiveCam(e.target.value)}
              className="session-select"
              style={{ width: 180, fontSize: 12 }}
            >
              {runningCams.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          )}
          <button className="btn-sm" onClick={() => setExpanded(false)}>▲ Thu gọn</button>
        </div>
      </div>

      <div className="live-body">
        {/* Video stream */}
        <div className="live-stream-container">
          {activeCam ? (
            <img
              ref={imgRef}
              src={`/api/cameras/${activeCam}/stream?overlay=true`}
              alt="Live Camera"
              className="live-stream-img"
              onError={e => {
                e.target.style.display = 'none'
                e.target.nextSibling && (e.target.nextSibling.style.display = 'flex')
              }}
            />
          ) : null}
          {!activeCam && (
            <div className="live-placeholder">
              <span style={{ fontSize: '2.5rem' }}>📹</span>
              <p>Chưa có camera đang chạy</p>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Vào trang Camera để bật camera trước
              </p>
            </div>
          )}
          {/* Overlay HUD */}
          {activeCam && (
            <div className="live-hud">
              <div className="live-hud-item">
                <span className="live-hud-value" style={{ color: 'var(--accent-primary)' }}>{engagementData?.total_persons || totalFaces}</span>
                <span className="live-hud-label">Sĩ số</span>
              </div>
              <div className="live-hud-item">
                <span className="live-hud-value">{Math.round(avgEng)}%</span>
                <span className="live-hud-label">Tập trung</span>
              </div>
              <div className="live-hud-item">
                <span className="live-hud-value" style={{ color: 'var(--accent-success)' }}>{recognized}</span>
                <span className="live-hud-label">Nhận diện</span>
              </div>
              <div className="live-hud-item">
                <span className="live-hud-value" style={{ color: 'var(--accent-warning)' }}>{totalFaces}</span>
                <span className="live-hud-label">Khuôn mặt</span>
              </div>
            </div>
          )}
        </div>

        {/* Attendance sidebar */}
        <div className="live-sidebar">
          <h4 className="live-sidebar-title">👤 Điểm danh trực tiếp</h4>
          {students.length === 0 ? (
            <div className="live-sidebar-empty">
              <span style={{ fontSize: '1.5rem' }}>🔍</span>
              <p>Đang chờ nhận diện...</p>
            </div>
          ) : (
            <div className="live-attendance-list">
              {students.map((s, i) => {
                const eng = s.engagement_score || 0
                const engClass = eng >= 60 ? 'high' : eng >= 40 ? 'mid' : 'low'
                return (
                  <div key={s.face_id ?? i} className={`live-student-row ${engClass}`}>
                    <div className="live-student-avatar">
                      {s.student_name ? s.student_name[0].toUpperCase() : '?'}
                    </div>
                    <div className="live-student-info">
                      <span className="live-student-name">
                        {s.student_name || `Khuôn mặt #${s.face_id ?? i + 1}`}
                      </span>
                      <span className="live-student-meta">
                        {s.emotion_vi || s.emotion} • {s.attention_direction_vi || ''}
                      </span>
                    </div>
                    <div className={`live-student-eng ${engClass}`}>
                      {Math.round(eng)}%
                    </div>
                  </div>
                )
              })}
            </div>
          )}
          <div className="live-sidebar-summary">
            <div className="live-summary-row">
              <span>✅ Đã nhận diện</span><strong>{recognized}</strong>
            </div>
            <div className="live-summary-row">
              <span>❓ Chưa xác định</span><strong>{unknown}</strong>
            </div>
            <div className="live-summary-row">
              <span>📊 Engagement TB</span><strong>{Math.round(avgEng)}%</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
