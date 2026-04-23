import useAppStore from '../../store/appStore'

const states = [
  { key: 'engaged', icon: '🎯', label: 'Tích cực', cls: 'ls-engaged' },
  { key: 'neutral', icon: '😐', label: 'Bình thường', cls: 'ls-neutral' },
  { key: 'confused', icon: '🤔', label: 'Bối rối', cls: 'ls-confused' },
  { key: 'bored', icon: '😴', label: 'Chán nản', cls: 'ls-bored' },
  { key: 'frustrated', icon: '😤', label: 'Thất vọng', cls: 'ls-frustrated' },
]

export default function LearningStates() {
  const { engagementData } = useAppStore()
  const dist = engagementData?.learning_state_distribution || {}

  return (
    <div className="card card-learning-states">
      <div className="card-header"><h3>Trạng thái học tập</h3></div>
      <div className="learning-states-grid">
        {states.map(({ key, icon, label, cls }) => (
          <div key={key} className={`ls-item ${cls}`}>
            <div className="ls-icon">{icon}</div>
            <div className="ls-info">
              <span className="ls-label">{label}</span>
              <span className="ls-value">{dist[key] || 0}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
