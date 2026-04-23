import useAppStore from '../../store/appStore'

const EMOJIS = { happy: '😊', sad: '😢', angry: '😠', surprise: '😲', fear: '😨', disgust: '😖', neutral: '😐' }

export default function StudentEmotions() {
  const { engagementData } = useAppStore()
  const students = engagementData?.students || []

  return (
    <div className="card" style={{ gridColumn: '1 / -1' }}>
      <div className="card-header"><h3>👥 Danh sách học sinh realtime</h3></div>
      {students.length === 0
        ? <div className="table-empty">Đang chờ dữ liệu...</div>
        : (
          <div className="student-emotion-list">
            {students.map((s, i) => (
              <div key={i} className="student-emotion-item">
                <span className="student-emotion-emoji">{EMOJIS[s.emotion] || '😐'}</span>
                <div className="student-emotion-info">
                  <div className="student-emotion-name">{s.student_name || `Học sinh #${s.face_id}`}</div>
                  <div className="student-emotion-state">
                    {s.learning_state_vi || s.learning_state} · {s.attention_direction_vi || ''}
                  </div>
                </div>
                <span className="student-emotion-score">{Math.round(s.engagement_score || 0)}%</span>
              </div>
            ))}
          </div>
        )
      }
    </div>
  )
}
