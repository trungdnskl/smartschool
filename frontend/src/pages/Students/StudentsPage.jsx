import { useEffect, useRef, useState, useCallback } from 'react'
import api from '../../hooks/useApi'
import Modal from '../../components/UI/Modal'
import { useToast } from '../../components/UI/Toast'

export default function StudentsPage() {
  const showToast = useToast()
  const [students, setStudents] = useState([])
  const [search, setSearch] = useState('')
  const [showEnroll, setShowEnroll] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ student_id: '', name: '', class_name: '' })
  const [editForm, setEditForm] = useState({ student_id: '', name: '', class_name: '' })
  const videoRef = useRef(null)
  const importRef = useRef(null)
  const [capturing, setCapturing] = useState(false)
  const [isAddingPhotos, setIsAddingPhotos] = useState(false) // true = thêm ảnh cho HS đã tồn tại

  // Multi-photo enrollment
  const [capturedPhotos, setCapturedPhotos] = useState([])

  const load = async () => {
    const r = await api.get('/api/students')
    if (r.ok) setStudents(r.data.students || [])
  }

  useEffect(() => { load() }, [])

  const filtered = students.filter(s =>
    `${s.name} ${s.student_id} ${s.class_name}`.toLowerCase().includes(search.toLowerCase())
  )

  const startCamera = async () => {
    if (!navigator.mediaDevices) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }
      })
      if (videoRef.current) videoRef.current.srcObject = stream
      setCapturing(true)
    } catch (err) {
      showToast('Không thể mở camera: ' + err.message, 'error')
    }
  }

  const stopCamera = () => {
    const stream = videoRef.current?.srcObject
    stream?.getTracks().forEach(t => t.stop())
    if (videoRef.current) videoRef.current.srcObject = null
    setCapturing(false)
  }

  // Chụp 1 ảnh → thêm vào danh sách preview
  const capturePhoto = useCallback(() => {
    if (!videoRef.current?.srcObject) return
    const canvas = document.createElement('canvas')
    canvas.width = 640; canvas.height = 480
    canvas.getContext('2d').drawImage(videoRef.current, 0, 0, 640, 480)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.9)
    setCapturedPhotos(prev => [...prev, dataUrl])
    showToast(`📸 Đã chụp ảnh #${capturedPhotos.length + 1}`, 'info')
  }, [capturedPhotos.length, showToast])

  // Xóa 1 ảnh khỏi preview
  const removePhoto = (index) => {
    setCapturedPhotos(prev => prev.filter((_, i) => i !== index))
  }

  // Convert dataURL to Blob
  const dataUrlToBlob = async (dataUrl) => {
    const res = await fetch(dataUrl)
    return res.blob()
  }

  // Đăng ký MỚI: gửi từng ảnh qua API /enroll
  const enrollNew = async () => {
    if (!form.student_id || !form.name) {
      showToast('Điền đầy đủ Mã HS và Họ tên', 'warning')
      return
    }

    let photosToSend = [...capturedPhotos]
    if (photosToSend.length === 0 && videoRef.current?.srcObject) {
      const canvas = document.createElement('canvas')
      canvas.width = 640; canvas.height = 480
      canvas.getContext('2d').drawImage(videoRef.current, 0, 0, 640, 480)
      photosToSend.push(canvas.toDataURL('image/jpeg', 0.9))
    }

    if (photosToSend.length === 0) {
      showToast('Cần chụp ít nhất 1 ảnh khuôn mặt', 'warning')
      return
    }

    setLoading(true)
    let successCount = 0
    let lastSampleCount = 0

    for (const dataUrl of photosToSend) {
      try {
        const blob = await dataUrlToBlob(dataUrl)
        const fd = new FormData()
        fd.append('student_id', form.student_id)
        fd.append('name', form.name)
        fd.append('class_name', form.class_name)
        fd.append('photo', blob, 'enroll.jpg')

        const r = await fetch('/api/students/enroll', { method: 'POST', body: fd })
        const data = await r.json().catch(() => ({}))
        if (r.ok) {
          successCount++
          lastSampleCount = data.sample_count || 0
        }
      } catch (err) {
        console.error('Enroll error:', err)
      }
    }

    if (successCount > 0) {
      showToast(`✅ Đã đăng ký ${form.name} — ${successCount} ảnh (${lastSampleCount} mẫu AI)`, 'success')
      closeEnroll()
      load()
    } else {
      showToast('Không tìm thấy khuôn mặt trong ảnh — thử lại với ảnh rõ hơn', 'error')
    }
    setLoading(false)
  }

  // THÊM ẢNH cho HS đã tồn tại: gửi qua /add-photo
  const addPhotosToExisting = async () => {
    let photosToSend = [...capturedPhotos]
    if (photosToSend.length === 0 && videoRef.current?.srcObject) {
      const canvas = document.createElement('canvas')
      canvas.width = 640; canvas.height = 480
      canvas.getContext('2d').drawImage(videoRef.current, 0, 0, 640, 480)
      photosToSend.push(canvas.toDataURL('image/jpeg', 0.9))
    }

    if (photosToSend.length === 0) {
      showToast('Cần chụp ít nhất 1 ảnh khuôn mặt', 'warning')
      return
    }

    setLoading(true)
    let successCount = 0
    let lastSampleCount = 0

    for (const dataUrl of photosToSend) {
      try {
        const blob = await dataUrlToBlob(dataUrl)
        const fd = new FormData()
        fd.append('photo', blob, 'face.jpg')

        const r = await fetch(`/api/students/${form.student_id}/add-photo`, { method: 'POST', body: fd })
        const data = await r.json().catch(() => ({}))
        if (r.ok) {
          successCount++
          lastSampleCount = data.sample_count || 0
        } else {
          showToast(data.detail || 'Ảnh không hợp lệ', 'warning')
        }
      } catch (err) {
        console.error('Add photo error:', err)
      }
    }

    if (successCount > 0) {
      showToast(`✅ Đã thêm ${successCount} ảnh cho ${form.name} (tổng: ${lastSampleCount} mẫu)`, 'success')
      closeEnroll()
      load()
    } else {
      showToast('Không tìm thấy khuôn mặt — thử ảnh rõ nét hơn', 'error')
    }
    setLoading(false)
  }

  // Hàm gửi đúng API tùy mode
  const handleSubmit = () => {
    if (isAddingPhotos) {
      addPhotosToExisting()
    } else {
      enrollNew()
    }
  }

  // Cập nhật thông tin học sinh (edit name/class)
  const updateStudentInfo = async () => {
    if (!editForm.name) {
      showToast('Họ tên không được để trống', 'warning')
      return
    }
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('name', editForm.name)
      fd.append('class_name', editForm.class_name)
      const r = await fetch(`/api/students/${editForm.student_id}`, { method: 'PUT', body: fd })
      if (r.ok) {
        showToast(`✅ Đã cập nhật ${editForm.name}`, 'success')
        setShowEdit(false)
        load()
      } else {
        const data = await r.json().catch(() => ({}))
        showToast(data.detail || 'Cập nhật thất bại', 'error')
      }
    } catch (err) {
      showToast('Lỗi kết nối', 'error')
    }
    setLoading(false)
  }

  const deleteStudent = async (id, name) => {
    if (!confirm(`Xóa học sinh "${name}" (${id})?\nSẽ xóa toàn bộ ảnh và dữ liệu nhận dạng.`)) return
    await api.del(`/api/students/${id}`)
    showToast(`Đã xóa ${name}`, 'info')
    load()
  }

  // P2-6: Sync names between LBPH ↔ ArcFace ↔ DB
  const syncAll = async () => {
    setLoading(true)
    try {
      const r = await fetch('/api/students/sync', { method: 'POST' })
      const data = await r.json().catch(() => ({}))
      if (r.ok) {
        showToast(`🔄 ${data.message || 'Đồng bộ thành công'}`, 'success')
        load()
      } else {
        showToast(data.detail || 'Đồng bộ thất bại', 'error')
      }
    } catch (err) {
      showToast('Lỗi kết nối: ' + err.message, 'error')
    }
    setLoading(false)
  }

  // Export photos ZIP for Colab training
  const exportPhotos = async () => {
    setLoading(true)
    try {
      const r = await fetch('/api/students/export-photos')
      if (!r.ok) {
        const data = await r.json().catch(() => ({}))
        showToast(data.detail || 'Export thất bại', 'error')
        setLoading(false)
        return
      }
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `face_photos_${students.length}students.zip`
      a.click()
      URL.revokeObjectURL(url)
      showToast(`📦 Đã export ${r.headers.get('X-Photo-Count') || '?'} ảnh`, 'success')
    } catch (err) {
      showToast('Lỗi: ' + err.message, 'error')
    }
    setLoading(false)
  }

  // Import embeddings from Colab
  const importEmbeddings = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.endsWith('.pkl')) {
      showToast('Chỉ chấp nhận file .pkl từ Google Colab', 'warning')
      return
    }
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const r = await fetch('/api/students/import-embeddings', { method: 'POST', body: fd })
      const data = await r.json().catch(() => ({}))
      if (r.ok) {
        showToast(`✅ ${data.message || 'Import thành công'} — Engine: ${data.engine_switched || 'ArcFace'}`, 'success')
        load()
      } else {
        showToast(data.detail || 'Import thất bại', 'error')
      }
    } catch (err) {
      showToast('Lỗi: ' + err.message, 'error')
    }
    setLoading(false)
    e.target.value = '' // reset input
  }

  // Mở modal "Thêm ảnh" cho HS đã tồn tại
  const openAddPhotos = (student) => {
    setForm({ student_id: student.student_id, name: student.name, class_name: student.class_name })
    setIsAddingPhotos(true)
    setCapturedPhotos([])
    setShowEnroll(true)
  }

  // Mở modal "Đăng ký mới"
  const openNewEnroll = () => {
    setForm({ student_id: '', name: '', class_name: '' })
    setIsAddingPhotos(false)
    setCapturedPhotos([])
    setShowEnroll(true)
  }

  // Mở modal "Sửa thông tin"
  const openEdit = (student) => {
    setEditForm({ student_id: student.student_id, name: student.name, class_name: student.class_name || '' })
    setShowEdit(true)
  }

  // Reset khi đóng modal
  const closeEnroll = () => {
    stopCamera()
    setCapturedPhotos([])
    setShowEnroll(false)
    setIsAddingPhotos(false)
    setForm({ student_id: '', name: '', class_name: '' })
  }

  return (
    <div className="page-enter">
      <div className="view-header">
        <h2>👤 Học sinh</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="session-input" style={{ width: 200 }}
            placeholder="🔍 Tìm kiếm..."
            value={search} onChange={e => setSearch(e.target.value)}
          />
          <button className="btn-secondary" onClick={syncAll} disabled={loading} title="Đồng bộ tên LBPH ↔ ArcFace ↔ DB">
            {loading ? '⏳' : '🔄'} Sync
          </button>
          <button className="btn-secondary" onClick={exportPhotos} disabled={loading} title="Export ảnh → Google Colab">
            📦 Export ZIP
          </button>
          <button className="btn-secondary" onClick={() => importRef.current?.click()} disabled={loading} title="Import embeddings từ Colab">
            📥 Import .pkl
          </button>
          <button className="btn-primary" onClick={openNewEnroll}>➕ Đăng ký</button>
        </div>
      </div>

      <div style={{ marginBottom: 12, color: 'var(--text-muted)', fontSize: 13 }}>
        Tổng: <b style={{ color: 'var(--text-primary)' }}>{students.length}</b> học sinh — Đang hiển thị: <b>{filtered.length}</b>
      </div>

      <div className="attendance-table-container">
        <table className="attendance-table">
          <thead>
            <tr><th>STT</th><th>Ảnh</th><th>Mã HS</th><th>Họ tên</th><th>Lớp</th><th>Engine</th><th>Trạng thái</th><th>Thao tác</th></tr>
          </thead>
          <tbody>
            {filtered.length === 0
              ? <tr><td colSpan={8} className="table-empty">Không tìm thấy học sinh</td></tr>
              : filtered.map((s, i) => (
                <tr key={s.student_id || i}>
                  <td>{i + 1}</td>
                  <td>
                    {s.has_photo
                      ? <img
                          src={`/api/students/${s.student_id}/thumbnail`}
                          alt={s.name}
                          style={{ width: 36, height: 36, borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--accent-primary)' }}
                          onError={e => { e.target.style.display = 'none' }}
                        />
                      : <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>👤</div>
                    }
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{s.student_id}</td>
                  <td><b>{s.name}</b></td>
                  <td>{s.class_name || '-'}</td>
                  <td>
                    <div className="engine-stat-pills">
                      {(s.lbph_samples > 0) && <span className="engine-pill lbph">🟡 {s.lbph_samples}</span>}
                      {(s.deep_embeddings > 0) && <span className="engine-pill arcface">🔵 {s.deep_embeddings}</span>}
                      {(!s.lbph_samples && !s.deep_embeddings) && <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>—</span>}
                    </div>
                  </td>
                  <td>
                    {(s.sample_count > 0 || s.embedding_count > 0)
                      ? <span className="status-badge present">✓ Đã đăng ký</span>
                      : <span className="status-badge absent">Chưa đăng ký</span>
                    }
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="btn-sm" onClick={() => openAddPhotos(s)} title="Thêm ảnh khuôn mặt">📷</button>
                      <button className="btn-sm" onClick={() => openEdit(s)} title="Sửa thông tin">✏️</button>
                      <button className="btn-sm" style={{ color: 'var(--accent-danger)' }} onClick={() => deleteStudent(s.student_id, s.name)} title="Xóa">🗑</button>
                    </div>
                  </td>
                </tr>
              ))
            }
          </tbody>
        </table>
      </div>

      {/* ── Enrollment / Add Photos Modal ── */}
      <Modal
        isOpen={showEnroll}
        onClose={closeEnroll}
        title={isAddingPhotos ? `📷 Thêm ảnh — ${form.name}` : '📷 Đăng ký khuôn mặt'}
      >
        {/* Form fields - ẩn khi đang thêm ảnh cho HS đã tồn tại */}
        {!isAddingPhotos && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label>Mã học sinh *</label>
                <input placeholder="VD: HS001" value={form.student_id} onChange={e => setForm({ ...form, student_id: e.target.value })} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label>Họ và tên *</label>
                <input placeholder="Nguyễn Văn A" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              </div>
            </div>
            <div className="form-group" style={{ marginTop: 0, marginBottom: 12 }}>
              <label>Lớp</label>
              <input placeholder="VD: 10A1" value={form.class_name} onChange={e => setForm({ ...form, class_name: e.target.value })} />
            </div>
          </>
        )}

        {/* Info banner khi thêm ảnh */}
        {isAddingPhotos && (
          <div style={{ background: 'var(--bg-secondary)', padding: '8px 12px', borderRadius: 6, marginBottom: 12, fontSize: 13 }}>
            <b>{form.name}</b> ({form.student_id}) — {form.class_name || 'Chưa có lớp'}
            <br/>
            <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Chụp thêm ảnh từ các góc khác nhau để tăng độ chính xác nhận dạng.</span>
          </div>
        )}

        {/* Camera + Preview layout */}
        <div style={{ display: 'grid', gridTemplateColumns: capturedPhotos.length > 0 ? '1fr 1fr' : '1fr', gap: 12, marginBottom: 12 }}>
          {/* Camera view */}
          <div style={{ background: 'var(--bg-primary)', borderRadius: 8, overflow: 'hidden', textAlign: 'center' }}>
            <video ref={videoRef} autoPlay muted playsInline style={{ width: '100%', maxHeight: 240, background: '#000', display: capturing ? 'block' : 'none' }} />
            {!capturing && (
              <div style={{ padding: '30px 0', color: 'var(--text-muted)', fontSize: 13 }}>
                <p style={{ marginBottom: 8 }}>📷 Camera chưa được bật</p>
                <button className="btn-secondary" onClick={startCamera}>Mở Camera</button>
              </div>
            )}
            {capturing && (
              <div style={{ padding: '6px 0', display: 'flex', gap: 6, justifyContent: 'center' }}>
                <button className="btn-primary" onClick={capturePhoto} style={{ fontSize: 13 }}>
                  📸 Chụp ảnh
                </button>
                <button className="btn-secondary" onClick={stopCamera} style={{ fontSize: 13 }}>⏹ Tắt</button>
              </div>
            )}
          </div>

          {/* Captured photos preview */}
          {capturedPhotos.length > 0 && (
            <div style={{ background: 'var(--bg-primary)', borderRadius: 8, padding: 8, overflow: 'auto', maxHeight: 280 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600 }}>
                📸 Đã chụp: {capturedPhotos.length} ảnh
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6 }}>
                {capturedPhotos.map((photo, idx) => (
                  <div key={idx} style={{ position: 'relative', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border-color)' }}>
                    <img src={photo} alt={`Ảnh ${idx + 1}`} style={{ width: '100%', height: 80, objectFit: 'cover', display: 'block' }} />
                    <button
                      onClick={() => removePhoto(idx)}
                      style={{
                        position: 'absolute', top: 2, right: 2,
                        background: 'rgba(239,68,68,0.85)', color: '#fff',
                        border: 'none', borderRadius: 4, width: 20, height: 20,
                        cursor: 'pointer', fontSize: 11, lineHeight: '20px',
                        padding: 0, textAlign: 'center',
                      }}
                    >✕</button>
                    <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'rgba(0,0,0,0.6)', color: '#fff', fontSize: 10, textAlign: 'center', padding: '1px 0' }}>
                      #{idx + 1}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Tips */}
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, background: 'var(--bg-secondary)', padding: '6px 10px', borderRadius: 6 }}>
          💡 <b>Mẹo:</b> Chụp 3-5 ảnh với các góc khác nhau (chính diện, nghiêng trái, nghiêng phải) để AI nhận diện chính xác hơn.
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn-secondary" onClick={closeEnroll}>Hủy</button>
          <button className="btn-primary" onClick={handleSubmit} disabled={loading}>
            {loading
              ? '⏳ Đang xử lý...'
              : isAddingPhotos
                ? `📸 Thêm ảnh${capturedPhotos.length > 0 ? ` (${capturedPhotos.length})` : ''}`
                : `✅ Đăng ký${capturedPhotos.length > 0 ? ` (${capturedPhotos.length} ảnh)` : ''}`
            }
          </button>
        </div>
      </Modal>

      {/* ── Edit Info Modal ── */}
      <Modal isOpen={showEdit} onClose={() => setShowEdit(false)} title="✏️ Sửa thông tin học sinh">
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
          Mã HS: <b style={{ color: 'var(--text-primary)' }}>{editForm.student_id}</b>
        </div>
        <div className="form-group">
          <label>Họ và tên *</label>
          <input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} />
        </div>
        <div className="form-group">
          <label>Lớp</label>
          <input value={editForm.class_name} onChange={e => setEditForm({ ...editForm, class_name: e.target.value })} />
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn-secondary" onClick={() => setShowEdit(false)}>Hủy</button>
          <button className="btn-primary" onClick={updateStudentInfo} disabled={loading}>
            {loading ? '⏳ Đang lưu...' : '✅ Lưu thay đổi'}
          </button>
        </div>
      </Modal>

      {/* Hidden file input for import */}
      <input
        ref={importRef}
        type="file"
        accept=".pkl"
        style={{ display: 'none' }}
        onChange={importEmbeddings}
      />
    </div>
  )
}
