import { useEffect, useState } from 'react'
import api from '../../hooks/useApi'
import Modal from '../../components/UI/Modal'
import { useToast } from '../../components/UI/Toast'

function ClassCard({ cls, onDelete }) {
  return (
    <div className="entity-card">
      <div className="entity-card-avatar" style={{ background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))' }}>
        {cls.name?.slice(0, 2) || '??'}
      </div>
      <div className="entity-card-name">{cls.name}</div>
      <div className="entity-card-sub">{cls.grade_level || ''}</div>
      <div className="entity-card-meta">
        <span>👨‍🏫 GVCN: {cls.teacher_name || 'Chưa cập nhật'}</span>
        <span>🏫 Phòng: {cls.room || '—'}</span>
        <span>👥 Sĩ số: {cls.student_count || 0} học sinh</span>
      </div>
      <div className="entity-card-actions">
        <button className="btn-sm" style={{ color: 'var(--accent-danger)' }} onClick={() => onDelete(cls.id, cls.name)}>🗑 Xóa</button>
      </div>
    </div>
  )
}

export default function ClassesPage() {
  const showToast = useToast()
  const [classes, setClasses] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: '', grade_level: '', teacher_name: '', room: '' })

  const load = async () => {
    const r = await api.get('/api/classes')
    if (r.ok) setClasses(r.data.classes || [])
  }
  useEffect(() => { load() }, [])

  const add = async () => {
    if (!form.name) { showToast('Tên lớp không được trống', 'warning'); return }
    const r = await api.post('/api/classes', form)
    if (r.ok) { showToast('✅ Đã thêm lớp học', 'success'); setShowAdd(false); setForm({ name: '', grade_level: '', teacher_name: '', room: '' }); load() }
    else showToast(r.data?.detail || 'Lỗi', 'error')
  }

  const del = async (id, name) => {
    if (!confirm(`Xóa lớp "${name}"?`)) return
    await api.del(`/api/classes/${id}`)
    showToast('Đã xóa lớp', 'info'); load()
  }

  return (
    <div className="page-enter">
      <div className="view-header">
        <h2>🏫 Lớp học</h2>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>➕ Thêm lớp</button>
      </div>
      <p style={{ marginBottom: 16, color: 'var(--text-muted)', fontSize: 13 }}>Tổng: <b>{classes.length}</b> lớp</p>
      <div className="entity-cards">
        {classes.length === 0
          ? <div className="alert-empty">Chưa có lớp nào được tạo</div>
          : classes.map(c => <ClassCard key={c.id} cls={c} onDelete={del} />)
        }
      </div>
      <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="➕ Thêm Lớp học">
        {[['name', 'Tên lớp *', '10A1'], ['grade_level', 'Khối lớp', 'Khối 10'], ['teacher_name', 'GVCN', 'Nguyễn Thị B'], ['room', 'Phòng học', 'P201']].map(([k, label, ph]) => (
          <div key={k} className="form-group">
            <label>{label}</label>
            <input placeholder={ph} value={form[k]} onChange={e => setForm({ ...form, [k]: e.target.value })} />
          </div>
        ))}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
          <button className="btn-secondary" onClick={() => setShowAdd(false)}>Hủy</button>
          <button className="btn-primary" onClick={add}>✅ Thêm</button>
        </div>
      </Modal>
    </div>
  )
}
