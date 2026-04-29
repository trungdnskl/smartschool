import useAppStore from '../../store/appStore'

export default function StatsRow() {
  const { engagementData, alerts } = useAppStore()
  const d = engagementData || {}
  const engagement = Math.round(d.avg_engagement || 0)

  // ── Headcount & Attendance ──
  // Sĩ số = total persons detected minus teacher
  const headcount = d.headcount || 0
  // Có mặt (identified) = students recognized by face
  const identified = d.identified_count || 0
  // Chưa xác định = headcount - identified
  const unidentified = d.unidentified_count || 0
  // Teacher
  const teacherDetected = d.teacher_detected || false
  const teacherName = d.teacher_name || ''

  const alertCount = alerts.length

  return (
    <div className="stats-row">
      <div className="stat-card stat-headcount">
        <div className="stat-card-icon">👥</div>
        <div className="stat-card-body">
          <span className="stat-card-value">{headcount}</span>
        </div>
        <span className="stat-card-label">Sĩ số</span>
      </div>
      <div className="stat-card stat-identified">
        <div className="stat-card-icon">✅</div>
        <div className="stat-card-body">
          <span className="stat-card-value">{identified}</span>
          {unidentified > 0 && (
            <span className="stat-card-sub">+{unidentified} chưa xác định</span>
          )}
        </div>
        <span className="stat-card-label">Có mặt (nhận diện)</span>
      </div>
      <div className="stat-card stat-engagement">
        <div className="stat-card-icon">📊</div>
        <div className="stat-card-body">
          <span className="stat-card-value">{engagement}</span>
          <span className="stat-card-unit">%</span>
        </div>
        <span className="stat-card-label">Mức tham gia</span>
      </div>
      <div className={`stat-card stat-teacher ${teacherDetected ? 'teacher-active' : ''}`}>
        <div className="stat-card-icon">{teacherDetected ? '🧑‍🏫' : '❓'}</div>
        <div className="stat-card-body">
          <span className="stat-card-value stat-card-text">
            {teacherDetected ? teacherName || 'Có mặt' : '—'}
          </span>
        </div>
        <span className="stat-card-label">Giáo viên</span>
      </div>
      <div className="stat-card stat-alerts">
        <div className="stat-card-icon">🔔</div>
        <div className="stat-card-body">
          <span className="stat-card-value">{alertCount}</span>
        </div>
        <span className="stat-card-label">Cảnh báo</span>
      </div>
    </div>
  )
}
