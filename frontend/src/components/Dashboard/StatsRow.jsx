import useAppStore from '../../store/appStore'

export default function StatsRow() {
  const { engagementData, alerts } = useAppStore()
  const d = engagementData || {}
  const engagement = Math.round(d.avg_engagement || 0)
  const faces = d.total_faces || 0
  const present = (d.students || []).length
  const alertCount = alerts.length

  return (
    <div className="stats-row">
      <div className="stat-card stat-engagement">
        <div className="stat-card-icon">📊</div>
        <div className="stat-card-body">
          <span className="stat-card-value">{engagement}</span>
          <span className="stat-card-unit">%</span>
        </div>
        <span className="stat-card-label">Mức tham gia</span>
      </div>
      <div className="stat-card stat-faces">
        <div className="stat-card-icon">👤</div>
        <div className="stat-card-body">
          <span className="stat-card-value">{faces}</span>
        </div>
        <span className="stat-card-label">Khuôn mặt</span>
      </div>
      <div className="stat-card stat-present">
        <div className="stat-card-icon">✅</div>
        <div className="stat-card-body">
          <span className="stat-card-value">{present}</span>
        </div>
        <span className="stat-card-label">Có mặt</span>
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
