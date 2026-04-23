import { useEffect, useState, useMemo } from 'react'
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer,
  Tooltip, XAxis, YAxis, Bar, BarChart, Cell, PieChart, Pie,
} from 'recharts'
import api from '../../hooks/useApi'
import './AnalyticsPage.css'

/* ── helpers ────────────────────────────────────── */
const fmtDur = (s) => {
  if (!s) return '—'
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}g ${m}p` : `${m} phút`
}
const fmtTime = (t) => {
  if (!t) return '—'
  try { return new Date(t.replace(' ', 'T')).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) }
  catch { return t }
}
const fmtDate = (t) => {
  if (!t) return ''
  try { return new Date(t.replace(' ', 'T')).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }) }
  catch { return t }
}

const SEVERITY_COLORS = { warning: '#f59e0b', info: '#3b82f6', danger: '#ef4444', success: '#10b981' }
const SEVERITY_ICONS  = { warning: '⚠️', info: 'ℹ️', danger: '🚨', success: '✅' }
const STATUS_MAP = {
  present: { label: 'Có mặt', color: '#10b981', icon: '✅' },
  late:    { label: 'Trễ',    color: '#f59e0b', icon: '⏰' },
  absent:  { label: 'Vắng',   color: '#ef4444', icon: '❌' },
}
const EMOTION_COLORS = {
  happy: '#10b981', neutral: '#64748b', sad: '#3b82f6', angry: '#ef4444',
  surprise: '#f59e0b', fear: '#8b5cf6', disgust: '#6b7280',
}

/* ── sub-components ─────────────────────────────── */

function StatCard({ icon, label, value, sub, accent }) {
  return (
    <div className="sr-stat-card" style={{ '--accent': accent || 'var(--accent-primary)' }}>
      <div className="sr-stat-icon">{icon}</div>
      <div className="sr-stat-body">
        <div className="sr-stat-value">{value ?? '—'}</div>
        <div className="sr-stat-label">{label}</div>
        {sub && <div className="sr-stat-sub">{sub}</div>}
      </div>
    </div>
  )
}

function AlertTimeline({ alerts }) {
  const [lightbox, setLightbox] = useState(null)

  if (!alerts?.length) return <div className="sr-empty">Không có cảnh báo nào trong buổi học này</div>

  const apiBase = import.meta.env.VITE_API_URL || ''

  return (
    <>
      <div className="sr-alert-timeline">
        {alerts.map((a, i) => {
          const evidenceUrl = a.evidence_path ? `${apiBase}/api/evidence/${a.evidence_path.replace('alert_evidence/', '')}` : null
          return (
            <div key={i} className="sr-alert-item" style={{ '--sev': SEVERITY_COLORS[a.severity] || SEVERITY_COLORS.info }}>
              <div className="sr-alert-dot" />
              <div className="sr-alert-content">
                <div className="sr-alert-time">{fmtTime(a.timestamp)}</div>
                <div className="sr-alert-msg">{a.message}</div>
                <div className="sr-alert-meta">
                  <span className="sr-badge" style={{ background: `${SEVERITY_COLORS[a.severity]}20`, color: SEVERITY_COLORS[a.severity] }}>
                    {SEVERITY_ICONS[a.severity]} {a.alert_type?.replace(/_/g, ' ')}
                  </span>
                  {evidenceUrl && (
                    <button className="sr-evidence-btn" onClick={() => setLightbox(evidenceUrl)}>
                      📷 Xem minh chứng
                    </button>
                  )}
                </div>
                {evidenceUrl && (
                  <div className="sr-evidence-thumb" onClick={() => setLightbox(evidenceUrl)}>
                    <img src={evidenceUrl} alt={`Evidence: ${a.alert_type}`} loading="lazy" />
                    <div className="sr-evidence-overlay">🔍 Phóng to</div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Lightbox */}
      {lightbox && (
        <div className="sr-lightbox" onClick={() => setLightbox(null)}>
          <div className="sr-lightbox-inner" onClick={e => e.stopPropagation()}>
            <button className="sr-lightbox-close" onClick={() => setLightbox(null)}>✕</button>
            <img src={lightbox} alt="Evidence" />
          </div>
        </div>
      )}
    </>
  )
}

function AttendanceTable({ records }) {
  if (!records?.length) return <div className="sr-empty">Không có dữ liệu điểm danh</div>

  const present = records.filter(r => r.status === 'present')
  const late    = records.filter(r => r.status === 'late')
  const absent  = records.filter(r => r.status === 'absent')
  const sorted  = [...absent, ...late, ...present] // Absent first for visibility

  return (
    <div className="sr-attendance">
      {/* Quick counts */}
      <div className="sr-att-counts">
        {Object.entries(STATUS_MAP).map(([key, { label, color, icon }]) => {
          const count = records.filter(r => r.status === key).length
          return (
            <div key={key} className="sr-att-count" style={{ '--color': color }}>
              <span className="sr-att-count-num">{count}</span>
              <span className="sr-att-count-label">{icon} {label}</span>
            </div>
          )
        })}
      </div>

      {/* Table */}
      <div className="sr-table-wrap">
        <table className="sr-table">
          <thead>
            <tr>
              <th>Mã HS</th>
              <th>Tên học sinh</th>
              <th>Trạng thái</th>
              <th>Giờ đến</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => {
              const st = STATUS_MAP[r.status] || STATUS_MAP.absent
              return (
                <tr key={i} className={`sr-row-${r.status}`}>
                  <td className="sr-td-id">{r.student_id || '—'}</td>
                  <td className="sr-td-name">{r.student_name || 'Chưa xác định'}</td>
                  <td>
                    <span className="sr-status-badge" style={{ background: `${st.color}15`, color: st.color, borderColor: `${st.color}40` }}>
                      {st.icon} {st.label}
                    </span>
                  </td>
                  <td className="sr-td-time">{r.arrival_time || '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ── main page ──────────────────────────────────── */
export default function AnalyticsPage() {
  const [sessions, setSessions] = useState([])
  const [selSid, setSelSid] = useState('')
  const [report, setReport] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [attendance, setAttendance] = useState([])
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(false)

  // Load sessions list
  useEffect(() => {
    api.get('/api/sessions?limit=50').then(r => {
      if (r.ok) {
        const list = r.data.sessions || []
        setSessions(list)
        if (list.length) setSelSid(String(list[0].id))
      }
    })
  }, [])

  // Load session data when selection changes
  useEffect(() => {
    if (!selSid) return
    setLoading(true)
    Promise.all([
      api.get(`/api/sessions/${selSid}/report`),
      api.get(`/api/sessions/${selSid}/alerts`),
      api.get(`/api/sessions/${selSid}/attendance`),
    ]).then(([rpt, alt, att]) => {
      if (rpt.ok) setReport(rpt.data)
      if (alt.ok) setAlerts(alt.data.alerts || [])
      if (att.ok) setAttendance(att.data.records || [])
      setLoading(false)
    })
  }, [selSid])

  // Derived data
  const trendData = useMemo(() => {
    const timeline = report?.engagement_timeline || []
    return timeline.map((v, i) => ({
      i,
      value: typeof v === 'number' ? Math.round(v) : Math.round(v?.avg_engagement || 0),
      label: v?.timestamp ? fmtTime(v.timestamp) : `#${i + 1}`,
    }))
  }, [report])

  const emotionData = useMemo(() =>
    Object.entries(report?.emotion_summary || {})
      .map(([name, value]) => ({ name, value: Math.round(value) }))
      .sort((a, b) => b.value - a.value),
  [report])

  const pieData = useMemo(() => {
    const counts = { present: 0, late: 0, absent: 0 }
    attendance.forEach(r => { if (counts[r.status] !== undefined) counts[r.status]++ })
    return Object.entries(counts).filter(([,v]) => v > 0).map(([key, value]) => ({
      name: STATUS_MAP[key].label,
      value,
      color: STATUS_MAP[key].color,
    }))
  }, [attendance])

  const selectedSession = sessions.find(s => String(s.id) === String(selSid))
  const absentCount = attendance.filter(r => r.status === 'absent').length
  const alertsWarning = alerts.filter(a => a.severity === 'warning').length

  const tabs = [
    { key: 'overview',   label: '📋 Tổng quan',    count: null },
    { key: 'alerts',     label: '🔔 Cảnh báo',     count: alerts.length },
    { key: 'attendance', label: '📝 Điểm danh',    count: absentCount > 0 ? `${absentCount} vắng` : null },
  ]

  const handleExport = () => {
    if (!selSid) return
    window.open(`/api/sessions/${selSid}/export?format=csv`, '_blank')
  }

  return (
    <div className="page-enter sr-page">
      {/* Header */}
      <div className="sr-header">
        <div className="sr-header-left">
          <h2>📊 Tóm tắt buổi học</h2>
          <p className="sr-header-sub">Xem lại chi tiết các buổi học đã kết thúc</p>
        </div>
        <div className="sr-header-right">
          <select className="sr-select" value={selSid} onChange={e => setSelSid(e.target.value)}>
            <option value="">-- Chọn buổi học --</option>
            {sessions.map(s => (
              <option key={s.id} value={s.id}>
                {s.session_name || `Buổi ${s.id}`} — {s.class_name || ''} ({fmtDate(s.start_time)})
              </option>
            ))}
          </select>
          {selSid && (
            <button className="sr-export-btn" onClick={handleExport} title="Xuất CSV">
              📥 Xuất CSV
            </button>
          )}
        </div>
      </div>

      {loading && <div className="sr-loading"><div className="auth-loading-spinner" /><span>Đang tải dữ liệu...</span></div>}

      {!loading && !report && <div className="sr-empty-state">
        <div className="sr-empty-icon">📊</div>
        <h3>Chọn buổi học để xem báo cáo chi tiết</h3>
        <p>Chọn một buổi học từ dropdown phía trên để xem tóm tắt, cảnh báo, và điểm danh.</p>
      </div>}

      {!loading && report && (
        <>
          {/* Session info bar */}
          <div className="sr-session-bar">
            <div className="sr-session-info">
              <span className="sr-session-name">{selectedSession?.session_name || `Buổi ${selSid}`}</span>
              <span className="sr-session-meta">
                {selectedSession?.class_name && <><span className="sr-tag">🏫 {selectedSession.class_name}</span></>}
                {selectedSession?.subject && <span className="sr-tag">📖 {selectedSession.subject}</span>}
                {selectedSession?.teacher_name && <span className="sr-tag">👨‍🏫 {selectedSession.teacher_name}</span>}
              </span>
            </div>
            <div className="sr-session-time">
              <span>{fmtTime(report.start_time)} → {fmtTime(report.end_time)}</span>
              <span className="sr-session-dur">{fmtDur(report.duration_seconds)}</span>
            </div>
          </div>

          {/* Tabs */}
          <div className="sr-tabs">
            {tabs.map(t => (
              <button
                key={t.key}
                className={`sr-tab ${activeTab === t.key ? 'sr-tab-active' : ''}`}
                onClick={() => setActiveTab(t.key)}
              >
                {t.label}
                {t.count != null && <span className="sr-tab-badge">{t.count}</span>}
              </button>
            ))}
          </div>

          {/* ═══ TAB: OVERVIEW ═══ */}
          {activeTab === 'overview' && (
            <div className="sr-content sr-fade-in">
              {/* Stats cards */}
              <div className="sr-stats-grid">
                <StatCard icon="📊" label="Engagement trung bình" value={`${Math.round(report.avg_engagement || 0)}%`}
                  accent={report.avg_engagement >= 60 ? '#10b981' : report.avg_engagement >= 40 ? '#f59e0b' : '#ef4444'} />
                <StatCard icon="🔺" label="Engagement cao nhất" value={`${Math.round(report.peak_engagement || 0)}%`} accent="#10b981" />
                <StatCard icon="🔻" label="Engagement thấp nhất" value={`${Math.round(report.lowest_engagement || 0)}%`} accent="#ef4444" />
                <StatCard icon="👥" label="Tổng học sinh" value={report.total_students || attendance.length || '—'}
                  sub={`${report.present_students || 0} có mặt`} accent="#3b82f6" />
                <StatCard icon="⏱" label="Thời lượng" value={fmtDur(report.duration_seconds)} accent="#8b5cf6" />
                <StatCard icon="🔔" label="Cảnh báo" value={alerts.length}
                  sub={alertsWarning > 0 ? `${alertsWarning} nghiêm trọng` : 'Không có vấn đề'} accent={alertsWarning > 0 ? '#f59e0b' : '#10b981'} />
              </div>

              {/* Charts row */}
              <div className="sr-charts-row">
                {/* Engagement trend */}
                {trendData.length > 1 && (
                  <div className="card sr-chart-card">
                    <div className="card-header"><h3>📈 Xu hướng engagement</h3></div>
                    <ResponsiveContainer width="100%" height={220}>
                      <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="engGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#00d4ff" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="label" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} axisLine={false} interval="preserveStartEnd" />
                        <YAxis domain={[0, 100]} tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <Tooltip formatter={(v) => [`${v}%`, 'Engagement']}
                          contentStyle={{ background: '#1e2642', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                        <Area type="monotone" dataKey="value" stroke="#00d4ff" strokeWidth={2} fill="url(#engGrad)" dot={false}
                          activeDot={{ r: 4, stroke: '#00d4ff', fill: '#0a1929' }} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Attendance pie + Emotion bar */}
                <div className="sr-side-charts">
                  {pieData.length > 0 && (
                    <div className="card sr-chart-card sr-chart-sm">
                      <div className="card-header"><h3>📋 Điểm danh</h3></div>
                      <ResponsiveContainer width="100%" height={160}>
                        <PieChart>
                          <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={65}
                            dataKey="value" paddingAngle={3} strokeWidth={0}>
                            {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                          </Pie>
                          <Tooltip contentStyle={{ background: '#1e2642', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="sr-pie-legend">
                        {pieData.map((d, i) => (
                          <span key={i} className="sr-pie-item">
                            <span className="sr-pie-dot" style={{ background: d.color }} />
                            {d.name}: {d.value}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {emotionData.length > 0 && (
                    <div className="card sr-chart-card sr-chart-sm">
                      <div className="card-header"><h3>😊 Cảm xúc</h3></div>
                      <ResponsiveContainer width="100%" height={160}>
                        <BarChart data={emotionData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                          <XAxis type="number" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }} axisLine={false} tickLine={false} />
                          <YAxis type="category" dataKey="name" tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 10 }} axisLine={false} width={60} />
                          <Tooltip contentStyle={{ background: '#1e2642', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                            formatter={(v) => [`${v}%`]} />
                          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                            {emotionData.map((d, i) => <Cell key={i} fill={EMOTION_COLORS[d.name] || '#64748b'} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              </div>

              {/* Recommendations */}
              {(report.recommendations || []).length > 0 && (
                <div className="card sr-recs-card">
                  <div className="card-header"><h3>💡 Gợi ý cải thiện</h3></div>
                  <div className="sr-recs-list">
                    {report.recommendations.map((r, i) => (
                      <div key={i} className="sr-rec-item">{r}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ═══ TAB: ALERTS ═══ */}
          {activeTab === 'alerts' && (
            <div className="sr-content sr-fade-in">
              <div className="card">
                <div className="card-header">
                  <h3>🔔 Lịch sử cảnh báo ({alerts.length})</h3>
                  {alerts.length > 0 && (
                    <div className="sr-alert-summary">
                      {Object.entries(
                        alerts.reduce((acc, a) => { acc[a.alert_type] = (acc[a.alert_type] || 0) + 1; return acc }, {})
                      ).map(([type, count]) => (
                        <span key={type} className="sr-alert-type-badge">{type.replace(/_/g, ' ')}: {count}</span>
                      ))}
                    </div>
                  )}
                </div>
                <AlertTimeline alerts={alerts} />
              </div>
            </div>
          )}

          {/* ═══ TAB: ATTENDANCE ═══ */}
          {activeTab === 'attendance' && (
            <div className="sr-content sr-fade-in">
              <div className="card">
                <div className="card-header">
                  <h3>📝 Chi tiết điểm danh</h3>
                  <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                    Tổng: {attendance.length} học sinh
                  </span>
                </div>
                <AttendanceTable records={attendance} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
