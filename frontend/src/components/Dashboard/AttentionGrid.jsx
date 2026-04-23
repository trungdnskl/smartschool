import useAppStore from '../../store/appStore'

const items = [
  { key: 'looking_at_teacher', icon: '👀', label: 'Nhìn bảng/GV' },
  { key: 'looking_away', icon: '👈', label: 'Nhìn chỗ khác' },
  { key: 'looking_down', icon: '📱', label: 'Cúi đầu' },
  { key: 'head_down', icon: '💤', label: 'Gục đầu' },
]

export default function AttentionGrid() {
  const { engagementData } = useAppStore()
  const att = engagementData?.attention_distribution || {}

  return (
    <div className="card card-attention">
      <div className="card-header"><h3>Phân bố hướng nhìn</h3></div>
      <div className="attention-grid">
        {items.map(({ key, icon, label }) => (
          <div key={key} className="att-item">
            <div className="att-icon">{icon}</div>
            <span className="att-label">{label}</span>
            <span className="att-value">{att[key] || 0}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
