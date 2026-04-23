import useAppStore from '../../store/appStore'

const emotions = [
  { key: 'happy', emoji: '😊', label: 'Vui vẻ', cls: '' },
  { key: 'neutral', emoji: '😐', label: 'Bình thường', cls: 'neutral' },
  { key: 'surprise', emoji: '😲', label: 'Ngạc nhiên', cls: 'surprise' },
  { key: 'sad', emoji: '😢', label: 'Buồn', cls: 'sad' },
  { key: 'angry', emoji: '😠', label: 'Tức giận', cls: 'angry' },
  { key: 'fear', emoji: '😨', label: 'Sợ hãi', cls: 'fear' },
]

export default function EmotionDistribution() {
  const { engagementData } = useAppStore()
  const dist = engagementData?.emotion_distribution || {}
  const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1

  return (
    <div className="card card-emotions">
      <div className="card-header"><h3>Phân bố cảm xúc</h3></div>
      <div className="emotion-grid">
        {emotions.map(({ key, emoji, label, cls }) => {
          const count = dist[key] || 0
          const pct = ((count / total) * 100).toFixed(0)
          return (
            <div key={key} className="emotion-item">
              <span className="emotion-emoji">{emoji}</span>
              <span className="emotion-name">{label}</span>
              <div className="emotion-bar">
                <div className={`emotion-bar-fill ${cls}`} style={{ width: `${pct}%` }} />
              </div>
              <span className="emotion-count">{count}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
