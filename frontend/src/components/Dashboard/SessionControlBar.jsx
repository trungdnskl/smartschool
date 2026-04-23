import { useEffect, useState } from 'react'
import api from '../../hooks/useApi'
import useAppStore from '../../store/appStore'
import { useToast } from '../UI/Toast'

export default function SessionControlBar() {
  const { sessionActive, startSession, stopSession } = useAppStore()
  const showToast = useToast()
  const [classes, setClasses] = useState([])
  const [teachers, setTeachers] = useState([])
  const [selClass, setSelClass] = useState('')
  const [selSubject, setSelSubject] = useState('')
  const [selTeacher, setSelTeacher] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get('/api/classes').then(r => setClasses(r.data?.classes || []))
    api.get('/api/teachers').then(r => setTeachers(r.data?.teachers || []))
  }, [])

  const toggle = async () => {
    setLoading(true)
    try {
      if (sessionActive) {
        const r = await api.post('/api/sessions/stop')
        if (r.ok) { stopSession(); showToast('✅ Buổi học đã kết thúc!', 'success') }
        else showToast(r.data?.detail || 'Lỗi khi kết thúc', 'error')
      } else {
        // Fix F1: Tìm class object để gửi cả id lẫn name
        const selectedClass = classes.find(c => String(c.id) === selClass)
        const selectedTeacher = teachers.find(t => t.name === selTeacher)

        const r = await api.post('/api/sessions/start', {
          session_name: `Buổi học ${new Date().toLocaleDateString('vi-VN')}`,
          subject: selSubject || undefined,
          teacher_name: selTeacher || undefined,
          class_name: selectedClass?.name || undefined,
          class_id: selectedClass?.id || undefined,
          teacher_id: selectedTeacher?.id || undefined,
        })
        if (r.ok) { startSession(r.data.session_id); showToast('🎓 Buổi học đã bắt đầu!', 'success') }
        else showToast(r.data?.detail || 'Lỗi khi bắt đầu', 'error')
      }
    } catch {
      showToast('Không thể kết nối server', 'error')
    }
    setLoading(false)
  }

  return (
    <div className="session-control-bar">
      <div className="session-inputs">
        <select
          className="session-input"
          value={selClass}
          onChange={e => setSelClass(e.target.value)}
          disabled={sessionActive || loading}
        >
          <option value="">-- Chọn lớp --</option>
          {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input
          className="session-input"
          placeholder="Môn học..."
          value={selSubject}
          onChange={e => setSelSubject(e.target.value)}
          disabled={sessionActive || loading}
        />
        <select
          className="session-input"
          value={selTeacher}
          onChange={e => setSelTeacher(e.target.value)}
          disabled={sessionActive || loading}
        >
          <option value="">-- Chọn GV --</option>
          {teachers.map(t => <option key={t.id} value={t.name}>{t.name}</option>)}
        </select>
      </div>
      <button
        className={`btn-session-start${sessionActive ? ' active' : ''}`}
        onClick={toggle}
        disabled={loading}
      >
        <span>{sessionActive ? '⬛' : '▶'}</span>
        {sessionActive ? 'Kết thúc buổi học' : 'Bắt đầu buổi học'}
      </button>
    </div>
  )
}
