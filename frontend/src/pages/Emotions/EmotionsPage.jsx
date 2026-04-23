import { useEffect, useState } from 'react'
import api from '../../hooks/useApi'
import useAppStore from '../../store/appStore'

export default function EmotionsPage() {
  const { engagementData } = useAppStore()
  const students = (engagementData?.students || []).filter(s => s.emotion)

  const emotionMap = {}
  students.forEach(s => { emotionMap[s.emotion] = (emotionMap[s.emotion] || 0) + 1 })
  const total = students.length || 1

  const EMOJIS = { happy: '😊', sad: '😢', angry: '😠', surprise: '😲', fear: '😨', disgust: '😖', neutral: '😐' }
  const VN = { happy: 'Vui vẻ', sad: 'Buồn', angry: 'Tức giận', surprise: 'Ngạc nhiên', fear: 'Lo âu', disgust: 'Khó chịu', neutral: 'Bình thường' }

  return (
    <div className="page-enter">
      <div className="view-header"><h2>😊 Phân tích cảm xúc realtime</h2></div>

      <div className="emotions-detail-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Left: distribution */}
        <div className="card">
          <div className="card-header"><h3>Phân bố cảm xúc</h3></div>
          <div className="emotion-grid">
            {Object.entries(EMOJIS).map(([key, emoji]) => {
              const count = emotionMap[key] || 0
              const pct = ((count / total) * 100).toFixed(0)
              return (
                <div key={key} className="emotion-item">
                  <span className="emotion-emoji">{emoji}</span>
                  <span className="emotion-name">{VN[key]}</span>
                  <div className="emotion-bar">
                    <div className="emotion-bar-fill" style={{ width: `${pct}%`, background: 'linear-gradient(90deg, var(--accent-primary), var(--accent-secondary))' }} />
                  </div>
                  <span className="emotion-count">{count}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right: student list */}
        <div className="card">
          <div className="card-header"><h3>Danh sách học sinh ({students.length})</h3></div>
          <div className="student-emotion-list">
            {students.length === 0
              ? <div className="alert-empty">Đang chờ dữ liệu realtime...</div>
              : students.map((s, i) => (
                <div key={i} className="student-emotion-item">
                  <span className="student-emotion-emoji">{EMOJIS[s.emotion] || '😐'}</span>
                  <div className="student-emotion-info">
                    <div className="student-emotion-name">{s.student_name || `Khuôn mặt #${s.face_id}`}</div>
                    <div className="student-emotion-state">
                      {VN[s.emotion] || s.emotion} · {s.attention_direction_vi || ''}
                    </div>
                  </div>
                  <span className="student-emotion-score">{Math.round(s.engagement_score || 0)}%</span>
                </div>
              ))
            }
          </div>
        </div>
      </div>
    </div>
  )
}
