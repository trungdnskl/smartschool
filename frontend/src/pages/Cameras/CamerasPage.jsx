import { useEffect, useRef, useState } from 'react'
import api from '../../hooks/useApi'
import { useToast } from '../../components/UI/Toast'

const CAM_TEMPLATES = {
  hikvision: 'rtsp://admin:password@192.168.1.100:554/Streaming/Channels/102',
  dahua: 'rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=1',
  kbvision: 'rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=1',
  tapo: 'rtsp://user:password@192.168.1.100:554/stream1',
  ezviz: 'rtsp://admin:password@192.168.1.100:554/h264/ch1/main/av_stream',
  phone: 'http://192.168.1.xxx:8080/video',
}

function detectType(url) {
  if (!url) return { label: 'Không rõ', icon: '❓' }
  if (/^\d+$/.test(url)) return { label: 'Webcam USB', icon: '🖥️' }
  if (url.startsWith('rtsp://')) return { label: 'Camera IP', icon: '📡' }
  if (url.startsWith('http')) return { label: 'HTTP Stream', icon: '🌐' }
  if (/\.(mp4|avi|mkv|mov)$/i.test(url)) return { label: 'Video file', icon: '🎞️' }
  return { label: 'File/Khác', icon: '📁' }
}

function getStatusInfo(status) {
  switch (status) {
    case 'running': return { label: 'Đang chạy', cls: 'online' }
    case 'stopped': return { label: 'Đã dừng', cls: 'offline' }
    case 'error': return { label: 'Lỗi kết nối', cls: 'error' }
    case 'disconnected': return { label: 'Mất kết nối', cls: 'error' }
    default: return { label: status, cls: 'offline' }
  }
}

function maskUrl(url) { return url.replace(/:([^@:]+)@/, ':***@') }
function fmtN(n) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n
}

function CameraCard({ cam, onAction }) {
  const isRunning = cam.status === 'running'
  const statusInfo = getStatusInfo(cam.status)
  const camType = detectType(cam.url)
  const cardCls = isRunning ? 'cam-online' : (cam.status === 'error' || cam.status === 'disconnected') ? 'cam-error' : 'cam-offline'

  return (
    <div className={`camera-card ${cardCls}`}>
      <div className="cam-preview">
        {isRunning
          ? <img
              src={`/api/cameras/${cam.id}/snapshot?overlay=true&t=${Date.now()}`}
              alt="snapshot"
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onError={e => (e.target.style.display = 'none')}
            />
          : <><span className="cam-preview-icon">{camType.icon}</span><span className="cam-preview-type">{camType.label}</span></>
        }
        <span className={`cam-preview-status ${statusInfo.cls}`} style={{ position: 'absolute', top: 6, left: 6 }}>
          <span className={`status-dot ${statusInfo.cls}`} /> {statusInfo.label}
        </span>
        {isRunning && <span className="cam-preview-fps" style={{ position: 'absolute', top: 6, right: 6 }}>{cam.fps || 0} FPS</span>}
      </div>
      <div className="cam-card-body">
        <div className="cam-card-header">
          <span className="cam-card-name">{cam.name}</span>
          <span className="cam-card-id">{cam.id}</span>
        </div>
        <div className="cam-url-display">
          <code title={cam.url}>{maskUrl(cam.url)}</code>
          <button className="cam-url-copy" onClick={() => navigator.clipboard.writeText(cam.url)}>📋</button>
        </div>
        <div className="cam-card-stats">
          <div className="cam-card-stat"><span className="cam-card-stat-value">{cam.fps || 0}</span><span className="cam-card-stat-label">FPS</span></div>
          <div className="cam-card-stat"><span className="cam-card-stat-value">{fmtN(cam.frame_count || 0)}</span><span className="cam-card-stat-label">Frames</span></div>
          <div className="cam-card-stat"><span className="cam-card-stat-value">{cam.last_frame_time || '--:--'}</span><span className="cam-card-stat-label">Last</span></div>
        </div>
        {cam.error_message && <div className="cam-error-msg">⚠ {cam.error_message}</div>}
        <div className="cam-card-actions">
          {isRunning
            ? <button className="cam-btn cam-btn-stop" onClick={() => onAction(cam.id, 'stop')}>⏹ Dừng</button>
            : <button className="cam-btn cam-btn-start" onClick={() => onAction(cam.id, 'start')}>▶ Chạy</button>
          }
          <button className="cam-btn" onClick={() => onAction(cam.id, 'edit', cam)}>✏️</button>
          <button className="cam-btn cam-btn-delete" onClick={() => onAction(cam.id, 'delete', cam.name)}>🗑</button>
        </div>
      </div>
    </div>
  )
}

export default function CamerasPage() {
  const showToast = useToast()
  const [cameras, setCameras] = useState([])
  const [showAddForm, setShowAddForm] = useState(false)
  const [showLive, setShowLive] = useState(false)
  const [liveCamId, setLiveCamId] = useState('')
  const [form, setForm] = useState({ id: '', name: '', url: '', type: 'rtsp' })
  const [testResult, setTestResult] = useState('')
  const [showHelp, setShowHelp] = useState(false)
  const [editCam, setEditCam] = useState(null) // { id, name, url }
  const [editForm, setEditForm] = useState({ name: '', url: '' })
  const refreshRef = useRef(null)

  const load = async () => {
    const r = await api.get('/api/cameras')
    if (r.ok) setCameras(r.data.cameras || [])
  }

  useEffect(() => {
    load()
    refreshRef.current = setInterval(load, 5000)
    return () => clearInterval(refreshRef.current)
  }, [])

  const handleAction = async (id, action, arg) => {
    if (action === 'delete') {
      if (!confirm(`Xóa camera "${arg}" (${id})?`)) return
      await api.del(`/api/cameras/${id}`)
      showToast(`Đã xóa camera ${id}`, 'info')
    } else if (action === 'edit') {
      setEditCam(arg)
      setEditForm({ name: arg.name, url: arg.url })
      return
    } else {
      await api.post(`/api/cameras/${id}/${action}`)
      showToast(action === 'start' ? `▶ Camera ${id} đang kết nối...` : `⏹ Camera ${id} đã dừng`, 'info')
    }
    setTimeout(load, 800)
  }

  const submitEdit = async () => {
    if (!editCam) return
    const r = await api.put(`/api/cameras/${editCam.id}`, editForm)
    if (r.ok) { showToast(`✅ Đã cập nhật ${editCam.id}`, 'success'); setEditCam(null); load() }
    else showToast(r.data?.detail || 'Lỗi cập nhật', 'error')
  }

  const submitAdd = async () => {
    if (!form.id || !form.name || !form.url) { showToast('Vui lòng điền đầy đủ thông tin', 'warning'); return }
    const r = await api.post('/api/cameras', form)
    if (r.ok) { showToast(`✅ Đã thêm camera ${form.name}`, 'success'); setShowAddForm(false); setForm({ id: '', name: '', url: '', type: 'rtsp' }); load() }
    else showToast(r.data?.detail || 'Lỗi thêm camera', 'error')
  }

  const testCam = async () => {
    setTestResult('⏳ Đang kiểm tra...')
    const r = await api.post('/api/cameras/test', { url: form.url })
    setTestResult(r.ok ? '✅ Kết nối thành công' : '❌ Không thể kết nối')
  }

  const online = cameras.filter(c => c.status === 'running').length
  const errors = cameras.filter(c => ['error', 'disconnected'].includes(c.status)).length

  return (
    <div className="page-enter">
      <div className="view-header">
        <h2>📹 Quản lý Camera</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-sm" onClick={() => setShowLive(!showLive)}>📺 LiveView</button>
          <button className="btn-primary" onClick={() => setShowAddForm(!showAddForm)}>+ Thêm Camera</button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="cam-stats-bar">
        <div className="cam-stat-chip">📷 Tổng: <b>{cameras.length}</b></div>
        <div className="cam-stat-chip"><span className="status-dot online" style={{ marginRight: 4 }} />Đang chạy: <b>{online}</b></div>
        <div className="cam-stat-chip"><span className="status-dot offline" style={{ marginRight: 4 }} />Dừng: <b>{cameras.length - online - errors}</b></div>
        <div className="cam-stat-chip"><span className="status-dot" style={{ background: '#f59e0b', marginRight: 4 }} />Lỗi: <b>{errors}</b></div>
        <button className="btn-sm" style={{ marginLeft: 'auto' }} onClick={load}>🔄 Làm mới</button>
      </div>

      {/* Live View */}
      {showLive && (
        <div className="card live-view-panel" style={{ padding: 0, marginBottom: 16, overflow: 'hidden' }}>
          <div className="card-header" style={{ padding: '12px 16px' }}>
            <h3>📺 Live View</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <select value={liveCamId} onChange={e => setLiveCamId(e.target.value)} className="session-select" style={{ width: 200, fontSize: 13 }}>
                <option value="">Chọn camera...</option>
                {cameras.filter(c => c.status === 'running').map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <button className="modal-close" onClick={() => setShowLive(false)}>✕</button>
            </div>
          </div>
          <div style={{ background: '#0a0e1a', minHeight: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {liveCamId
              ? <img src={`/api/cameras/${liveCamId}/stream?overlay=true`} alt="live" style={{ maxWidth: '100%', maxHeight: '60vh', objectFit: 'contain' }} />
              : <span style={{ color: '#556', fontSize: 13 }}>Chọn camera để xem live</span>
            }
          </div>
        </div>
      )}

      {/* Add Camera Form */}
      {showAddForm && (
        <div className="card cam-add-form" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <h3>➕ Thêm Camera mới</h3>
            <button className="modal-close" onClick={() => setShowAddForm(false)}>✕</button>
          </div>
          <div className="cam-form-grid">
            <div className="form-group">
              <label>ID Camera</label>
              <input placeholder="VD: cam_front" value={form.id} onChange={e => setForm({ ...form, id: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Tên Camera</label>
              <input placeholder="VD: Camera trước bảng" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="form-group cam-form-url">
              <label>URL / Nguồn video</label>
              <input placeholder="rtsp://admin:pass@192.168.1.100:554/stream1" value={form.url} onChange={e => setForm({ ...form, url: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Loại nguồn</label>
              <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}>
                <option value="rtsp">📡 Camera IP (RTSP)</option>
                <option value="webcam">🖥️ Webcam USB</option>
                <option value="file">🎞️ File Video</option>
                <option value="http">🌐 HTTP Stream</option>
              </select>
            </div>
          </div>
          <div className="cam-url-templates">
            <span className="cam-template-label">Mẫu nhanh:</span>
            {Object.keys(CAM_TEMPLATES).map(k => (
              <button key={k} className="cam-template-btn" onClick={() => setForm({ ...form, url: CAM_TEMPLATES[k] })}>
                {k === 'phone' ? '📱 Điện thoại' : k.charAt(0).toUpperCase() + k.slice(1)}
              </button>
            ))}
          </div>
          <div className="cam-form-actions">
            <button className="btn-sm" onClick={testCam}>🔍 Kiểm tra kết nối</button>
            {testResult && <span className="cam-test-result">{testResult}</span>}
            <button className="btn-primary" style={{ marginLeft: 'auto' }} onClick={submitAdd}>✅ Thêm Camera</button>
          </div>
        </div>
      )}

      {/* Camera Grid */}
      <div className="cameras-grid">
        {cameras.length === 0
          ? <div className="table-empty" style={{ gridColumn: '1/-1', padding: 40 }}>
              <p style={{ fontSize: '2rem', marginBottom: 10 }}>📷</p>
              <p>Chưa có camera nào được cấu hình</p>
              <p style={{ fontSize: '0.78rem', marginTop: 8, color: 'var(--text-muted)' }}>Nhấn "+ Thêm Camera" để thêm mới</p>
            </div>
          : cameras.map(cam => <CameraCard key={cam.id} cam={cam} onAction={handleAction} />)
        }
      </div>

      {/* Edit Camera Modal */}
      {editCam && (
        <div className="modal-overlay" onClick={() => setEditCam(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>✏️ Chỉnh sửa Camera: {editCam.id}</h3>
              <button className="modal-close" onClick={() => setEditCam(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Tên Camera</label>
                <input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} />
              </div>
              <div className="form-group">
                <label>URL / Nguồn video</label>
                <input value={editForm.url} onChange={e => setEditForm({ ...editForm, url: e.target.value })} />
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
                <button className="btn-sm" onClick={() => setEditCam(null)}>Hủy</button>
                <button className="btn-primary" onClick={submitEdit}>💾 Lưu thay đổi</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Help */}
      <div className="card cam-help-card">
        <div className="card-header">
          <h3>💡 Hướng dẫn kết nối Camera IP</h3>
          <button className="btn-sm" onClick={() => setShowHelp(!showHelp)}>{showHelp ? 'Thu gọn' : 'Mở rộng'}</button>
        </div>
        {showHelp && (
          <div>
            <div className="cam-help-grid">
              <div className="cam-help-item">
                <h4>📡 Camera IP (RTSP)</h4>
                <div className="cam-help-table">
                  {[['Hikvision', 'rtsp://admin:pass@IP:554/Streaming/Channels/102'], ['Dahua', 'rtsp://admin:pass@IP:554/cam/realmonitor?channel=1&subtype=1'], ['Tapo', 'rtsp://user:pass@IP:554/stream1']].map(([label, url]) => (
                    <div key={label} className="cam-help-row"><span>{label}</span><code>{url}</code></div>
                  ))}
                </div>
              </div>
              <div className="cam-help-item">
                <h4>🖥️ Webcam & Khác</h4>
                <div className="cam-help-table">
                  {[['Webcam USB', '0'], ['File video', 'E:/videos/demo.mp4'], ['📱 IP Webcam', 'http://192.168.1.xxx:8080/video']].map(([label, url]) => (
                    <div key={label} className="cam-help-row"><span>{label}</span><code>{url}</code></div>
                  ))}
                </div>
              </div>
            </div>
            <div className="cam-help-tips">
              <p>⚡ <b>Mẹo:</b> Dùng sub-stream (subtype=1) để giảm tải CPU.</p>
              <p>🔍 <b>Test URL:</b> Mở VLC → Media → Open Network Stream → Dán URL RTSP.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
