import useAppStore from '../../store/appStore'

function formatTime(ts) {
  if (!ts) return ''
  const t = ts.includes('T') ? ts.split('T')[1]?.substring(0, 8) : ts.split(' ')[1] || ''
  return t
}

export default function AlertsList() {
  const { alerts } = useAppStore()

  return (
    <div className="card card-alerts">
      <div className="card-header"><h3>Cảnh báo gần đây</h3></div>
      <div className="alerts-list">
        {alerts.length === 0
          ? <div className="alert-empty">Chưa có cảnh báo</div>
          : alerts.slice(0, 10).map((a, i) => (
            <div key={i} className={`alert-item ${a.severity === 'critical' ? 'critical' : a.severity === 'info' ? 'info' : ''}`}>
              <span className="alert-time">{formatTime(a.timestamp)}</span>
              <span className="alert-message">{a.message}</span>
            </div>
          ))
        }
      </div>
    </div>
  )
}
