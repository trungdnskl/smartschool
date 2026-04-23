import { useEffect, useState } from 'react'
import api from '../../hooks/useApi'
import Modal from '../../components/UI/Modal'
import { useToast } from '../../components/UI/Toast'

function TeacherCard({ teacher, onDelete }) {
  const initials = teacher.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
  return (
    <div className="entity-card">
      <div className="entity-card-avatar">{initials}</div>
      <div className="entity-card-name">{teacher.name}</div>
      <div className="entity-card-sub">{teacher.email || '—'}</div>
      <div className="entity-card-meta">
        <span>📚 {teacher.subject || 'Chưa cập nhật'}</span>
        <span>📞 {teacher.phone || '—'}</span>
      </div>
      <div className="entity-card-actions">
        <button className="btn-sm" style={{ color: 'var(--accent-danger)' }} onClick={() => onDelete(teacher.id, teacher.name)}>🗑 Xóa</button>
      </div>
    </div>
  )
}

export default function TeachersPage() {
  const showToast = useToast()
  const [teachers, setTeachers] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: '', email: '', subject: '', phone: '' })

  const load = async () => {
    const r = await api.get('/api/teachers')
    if (r.ok) setTeachers(r.data.teachers || [])
  }
  useEffect(() => { load() }, [])

  const add = async () => {
    if (!form.name) { showToast('Tên không được trống', 'warning'); return }
    const r = await api.post('/api/teachers', form)
    if (r.ok) { showToast('✅ Đã thêm giáo viên', 'success'); setShowAdd(false); setForm({ name: '', email: '', subject: '', phone: '' }); load() }
    else showToast(r.data?.detail || 'Lỗi', 'error')
  }

  const del = async (id, name) => {
    if (!confirm(`Xóa giáo viên "${name}"?`)) return
    await api.del(`/api/teachers/${id}`)
    showToast('Đã xóa', 'info'); load()
  }

  return (
    <div className="page-enter">
      <div className="view-header">
        <h2>👩‍🏫 Giáo viên</h2>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>➕ Thêm giáo viên</button>
      </div>
      <p style={{ marginBottom: 16, color: 'var(--text-muted)', fontSize: 13 }}>Tổng: <b>{teachers.length}</b> giáo viên</p>
      <div className="entity-cards">
        {teachers.length === 0
          ? <div className="alert-empty">Chưa có giáo viên nào</div>
          : teachers.map(t => <TeacherCard key={t.id} teacher={t} onDelete={del} />)
        }
      </div>
      <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="➕ Thêm Giáo viên">
        {[['name', 'Họ và tên *', 'Nguyễn Thị B'], ['email', 'Email', 'giaovien@school.edu.vn'], ['subject', 'Môn dạy', 'Toán học'], ['phone', 'Điện thoại', '0901234567']].map(([k, label, ph]) => (
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
