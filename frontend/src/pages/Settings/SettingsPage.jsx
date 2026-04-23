import { useEffect, useState } from 'react'
import api from '../../hooks/useApi'
import useAuthStore from '../../store/authStore'
import Modal from '../../components/UI/Modal'
import { useToast } from '../../components/UI/Toast'

/* ── Section component ──────────────────────── */
function SettingsSection({ icon, title, description, children }) {
  return (
    <div className="settings-section">
      <div className="settings-section-header">
        <div className="settings-section-icon">{icon}</div>
        <div>
          <h3 className="settings-section-title">{title}</h3>
          {description && <p className="settings-section-desc">{description}</p>}
        </div>
      </div>
      <div className="settings-section-body">{children}</div>
    </div>
  )
}

function SettingsRow({ label, description, children }) {
  return (
    <div className="settings-row">
      <div className="settings-row-info">
        <span className="settings-row-label">{label}</span>
        {description && <span className="settings-row-desc">{description}</span>}
      </div>
      <div className="settings-row-control">{children}</div>
    </div>
  )
}

function Toggle({ checked, onChange, disabled }) {
  return (
    <label className={`settings-toggle ${disabled ? 'disabled' : ''}`}>
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} disabled={disabled} />
      <span className="settings-toggle-slider" />
    </label>
  )
}

/* ── Main Page ──────────────────────────────── */
export default function SettingsPage() {
  const showToast = useToast()
  const { user, changePassword, logout } = useAuthStore()
  const [config, setConfig] = useState(null)
  const [stats, setStats] = useState(null)
  const [users, setUsers] = useState([])
  const [showPw, setShowPw] = useState(false)
  const [showAddUser, setShowAddUser] = useState(false)
  const [pwForm, setPwForm] = useState({ current: '', newPw: '', confirm: '' })
  const [userForm, setUserForm] = useState({ username: '', password: '', role: 'teacher' })
  const [activeTab, setActiveTab] = useState('general')

  useEffect(() => {
    api.get('/api/system/config').then(r => { if (r.ok) setConfig(r.data) })
    api.get('/api/system/stats').then(r => { if (r.ok) setStats(r.data) })
    if (user?.role === 'admin') {
      api.get('/api/auth/users').then(r => { if (r.ok) setUsers(r.data.users || []) })
    }
  }, [user])

  const handleChangePw = async () => {
    if (!pwForm.current || !pwForm.newPw) { showToast('Vui lòng điền đầy đủ', 'warning'); return }
    if (pwForm.newPw.length < 6) { showToast('Mật khẩu mới phải ≥ 6 ký tự', 'warning'); return }
    if (pwForm.newPw !== pwForm.confirm) { showToast('Mật khẩu xác nhận không khớp', 'warning'); return }
    const r = await changePassword(pwForm.current, pwForm.newPw)
    if (r.ok) {
      showToast('✅ Đổi mật khẩu thành công', 'success')
      setShowPw(false); setPwForm({ current: '', newPw: '', confirm: '' })
    } else {
      showToast(r.data?.detail || 'Lỗi đổi mật khẩu', 'error')
    }
  }

  const handleAddUser = async () => {
    if (!userForm.username || !userForm.password) { showToast('Vui lòng điền đầy đủ', 'warning'); return }
    const r = await api.post('/api/auth/users', userForm)
    if (r.ok) {
      showToast(`✅ Đã tạo tài khoản ${userForm.username}`, 'success')
      setShowAddUser(false); setUserForm({ username: '', password: '', role: 'teacher' })
      api.get('/api/auth/users').then(r => { if (r.ok) setUsers(r.data.users || []) })
    } else {
      showToast(r.data?.detail || 'Lỗi tạo tài khoản', 'error')
    }
  }

  const handleDeactivateUser = async (uid, username) => {
    if (!confirm(`Vô hiệu hóa tài khoản "${username}"?`)) return
    const r = await api.del(`/api/auth/users/${uid}`)
    if (r.ok) {
      showToast('Đã vô hiệu hóa', 'info')
      api.get('/api/auth/users').then(r => { if (r.ok) setUsers(r.data.users || []) })
    } else showToast(r.data?.detail || 'Lỗi', 'error')
  }

  const tabs = [
    { id: 'general', label: '⚙️ Chung', show: true },
    { id: 'account', label: '👤 Tài khoản', show: true },
    { id: 'users', label: '👥 Quản lý User', show: user?.role === 'admin' },
    { id: 'system', label: '🖥️ Hệ thống', show: true },
  ]

  return (
    <div className="page-enter">
      <div className="view-header">
        <h2>⚙️ Cài đặt</h2>
      </div>

      {/* Tab navigation */}
      <div className="settings-tabs">
        {tabs.filter(t => t.show).map(t => (
          <button
            key={t.id}
            className={`settings-tab ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* === General Tab === */}
      {activeTab === 'general' && (
        <div className="settings-content">
          <SettingsSection icon="🏫" title="Thông tin lớp học" description="Cấu hình cơ bản từ config.yaml">
            <SettingsRow label="Tên phòng">
              <span className="settings-value">{config?.classroom?.name || '—'}</span>
            </SettingsRow>
            <SettingsRow label="Sĩ số tối đa">
              <span className="settings-value">{config?.classroom?.capacity || '—'}</span>
            </SettingsRow>
            <SettingsRow label="Môn học mặc định">
              <span className="settings-value">{config?.classroom?.subject || '—'}</span>
            </SettingsRow>
          </SettingsSection>

          <SettingsSection icon="🤖" title="AI Engine" description="Cấu hình nhận diện và phân tích">
            <SettingsRow label="Face Detection Model" description="Mô hình phát hiện khuôn mặt">
              <span className="settings-value settings-value-code">{config?.detection?.face_model || '—'}</span>
            </SettingsRow>
            <SettingsRow label="Emotion Model" description="Mô hình nhận diện cảm xúc">
              <span className="settings-value settings-value-code">{config?.detection?.emotion_model || '—'}</span>
            </SettingsRow>
            <SettingsRow label="Frame Skip" description="Xử lý mỗi N frame (tăng = nhẹ hơn)">
              <span className="settings-value">{config?.detection?.frame_skip || '—'}</span>
            </SettingsRow>
            <SettingsRow label="Confidence tối thiểu">
              <span className="settings-value">{config?.detection?.face_confidence || '—'}</span>
            </SettingsRow>
            <SettingsRow label="Head Pose" description="Ước lượng hướng đầu">
              <Toggle checked={config?.detection?.head_pose_enabled ?? true} onChange={() => {}} disabled />
            </SettingsRow>
          </SettingsSection>

          <SettingsSection icon="📊" title="Engagement Scoring" description="Trọng số tính điểm tham gia">
            <SettingsRow label="Cảm xúc (Emotion)">
              <span className="settings-value">{((config?.engagement?.weights?.emotion || 0) * 100).toFixed(0)}%</span>
            </SettingsRow>
            <SettingsRow label="Chú ý (Attention)">
              <span className="settings-value">{((config?.engagement?.weights?.attention || 0) * 100).toFixed(0)}%</span>
            </SettingsRow>
            <SettingsRow label="Hành vi (Behavior)">
              <span className="settings-value">{((config?.engagement?.weights?.behavior || 0) * 100).toFixed(0)}%</span>
            </SettingsRow>
            <SettingsRow label="Ngưỡng cảnh báo" description="Lớp < ngưỡng → báo động">
              <span className="settings-value">{config?.engagement?.alert_threshold || '—'}%</span>
            </SettingsRow>
          </SettingsSection>

          <SettingsSection icon="🔒" title="Quyền riêng tư" description="Bảo mật dữ liệu học sinh">
            <SettingsRow label="Lưu ảnh khuôn mặt">
              <Toggle checked={config?.privacy?.store_face_images ?? false} onChange={() => {}} disabled />
            </SettingsRow>
            <SettingsRow label="Thời hạn lưu dữ liệu">
              <span className="settings-value">{config?.privacy?.data_retention_days || '—'} ngày</span>
            </SettingsRow>
            <SettingsRow label="Ẩn danh báo cáo">
              <Toggle checked={config?.privacy?.anonymize_reports ?? true} onChange={() => {}} disabled />
            </SettingsRow>
            <SettingsRow label="Yêu cầu đồng ý">
              <Toggle checked={config?.privacy?.require_consent ?? true} onChange={() => {}} disabled />
            </SettingsRow>
          </SettingsSection>
        </div>
      )}

      {/* === Account Tab === */}
      {activeTab === 'account' && (
        <div className="settings-content">
          <SettingsSection icon="👤" title="Thông tin tài khoản" description="Tài khoản đang đăng nhập">
            <SettingsRow label="Tên đăng nhập">
              <span className="settings-value">{user?.username || 'anonymous'}</span>
            </SettingsRow>
            <SettingsRow label="Vai trò">
              <span className={`settings-badge ${user?.role === 'admin' ? 'settings-badge-admin' : 'settings-badge-teacher'}`}>
                {user?.role === 'admin' ? '🛡️ Quản trị viên' : '👩‍🏫 Giáo viên'}
              </span>
            </SettingsRow>
            <SettingsRow label="Mật khẩu">
              <button className="btn-sm" onClick={() => setShowPw(true)}>🔑 Đổi mật khẩu</button>
            </SettingsRow>
            <SettingsRow label="Đăng xuất" description="Kết thúc phiên đăng nhập">
              <button className="btn-sm" style={{ color: 'var(--accent-danger)' }} onClick={logout}>🚪 Đăng xuất</button>
            </SettingsRow>
          </SettingsSection>

          <SettingsSection icon="🔐" title="Bảo mật" description="Thông tin bảo mật hệ thống">
            <SettingsRow label="Xác thực">
              <span className="settings-value settings-value-code">JWT Bearer Token</span>
            </SettingsRow>
            <SettingsRow label="Token hết hạn">
              <span className="settings-value">8 giờ</span>
            </SettingsRow>
            <SettingsRow label="Mã hóa mật khẩu">
              <span className="settings-value settings-value-code">SHA-256 Crypt</span>
            </SettingsRow>
          </SettingsSection>
        </div>
      )}

      {/* === Users Tab (Admin only) === */}
      {activeTab === 'users' && user?.role === 'admin' && (
        <div className="settings-content">
          <SettingsSection
            icon="👥"
            title="Quản lý tài khoản"
            description="Tạo và quản lý tài khoản giáo viên"
          >
            <div style={{ marginBottom: 12 }}>
              <button className="btn-primary" onClick={() => setShowAddUser(true)}>➕ Tạo tài khoản mới</button>
            </div>

            <div className="settings-users-table">
              <table className="attendance-table">
                <thead>
                  <tr>
                    <th>ID</th><th>Username</th><th>Vai trò</th><th>Trạng thái</th><th>Ngày tạo</th><th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {users.length === 0
                    ? <tr><td colSpan={6} className="table-empty">Chưa có tài khoản</td></tr>
                    : users.map(u => (
                      <tr key={u.id}>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{u.id}</td>
                        <td><b>{u.username}</b></td>
                        <td>
                          <span className={`settings-badge ${u.role === 'admin' ? 'settings-badge-admin' : 'settings-badge-teacher'}`}>
                            {u.role === 'admin' ? '🛡️ Admin' : '👩‍🏫 Teacher'}
                          </span>
                        </td>
                        <td>
                          <span className={`status-badge ${u.is_active ? 'present' : 'absent'}`}>
                            {u.is_active ? '✓ Hoạt động' : '✗ Đã khóa'}
                          </span>
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{u.created_at || '—'}</td>
                        <td>
                          {u.id !== user?.user_id && u.is_active && (
                            <button className="btn-sm" style={{ color: 'var(--accent-danger)' }}
                              onClick={() => handleDeactivateUser(u.id, u.username)}>
                              🔒 Khóa
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  }
                </tbody>
              </table>
            </div>
          </SettingsSection>

          <SettingsSection icon="📋" title="Phân quyền" description="Mô tả các vai trò trong hệ thống">
            <div className="settings-roles-grid">
              <div className="settings-role-card">
                <div className="settings-role-header">
                  <span className="settings-badge settings-badge-admin">🛡️ Admin</span>
                </div>
                <ul className="settings-role-perms">
                  <li>✅ Quản lý tất cả tài khoản</li>
                  <li>✅ Cấu hình camera & hệ thống</li>
                  <li>✅ Quản lý giáo viên, lớp học</li>
                  <li>✅ Xem toàn bộ báo cáo</li>
                  <li>✅ Bắt đầu/kết thúc buổi học</li>
                </ul>
              </div>
              <div className="settings-role-card">
                <div className="settings-role-header">
                  <span className="settings-badge settings-badge-teacher">👩‍🏫 Giáo viên</span>
                </div>
                <ul className="settings-role-perms">
                  <li>✅ Bắt đầu/kết thúc buổi học</li>
                  <li>✅ Quản lý học sinh lớp mình</li>
                  <li>✅ Xem điểm danh & cảm xúc</li>
                  <li>✅ Xem phân tích & báo cáo</li>
                  <li>❌ Không quản lý tài khoản</li>
                </ul>
              </div>
            </div>
          </SettingsSection>
        </div>
      )}

      {/* === System Tab === */}
      {activeTab === 'system' && (
        <div className="settings-content">
          <SettingsSection icon="🖥️" title="Thông tin hệ thống" description="Trạng thái server và tài nguyên">
            <SettingsRow label="Backend">
              <span className="settings-value settings-value-code">FastAPI + Uvicorn</span>
            </SettingsRow>
            <SettingsRow label="Database">
              <span className="settings-value settings-value-code">SQLite</span>
            </SettingsRow>
            <SettingsRow label="Tổng buổi học">
              <span className="settings-value">{stats?.total_sessions ?? '—'}</span>
            </SettingsRow>
            <SettingsRow label="Tổng học sinh">
              <span className="settings-value">{stats?.total_students ?? '—'}</span>
            </SettingsRow>
            <SettingsRow label="Tổng giáo viên">
              <span className="settings-value">{stats?.total_teachers ?? '—'}</span>
            </SettingsRow>
            <SettingsRow label="Tổng lớp học">
              <span className="settings-value">{stats?.total_classes ?? '—'}</span>
            </SettingsRow>
            <SettingsRow label="CPU Usage">
              <div className="settings-progress-bar">
                <div className="settings-progress-fill" style={{ width: `${stats?.cpu_percent || 0}%` }} />
                <span>{(stats?.cpu_percent || 0).toFixed(1)}%</span>
              </div>
            </SettingsRow>
            <SettingsRow label="RAM Usage">
              <div className="settings-progress-bar">
                <div className="settings-progress-fill" style={{ width: `${stats?.memory_percent || 0}%` }} />
                <span>{(stats?.memory_percent || 0).toFixed(1)}%</span>
              </div>
            </SettingsRow>
          </SettingsSection>

          <SettingsSection icon="📡" title="Camera" description="Tình trạng camera hiện tại">
            <SettingsRow label="Tổng camera">
              <span className="settings-value">{stats?.cameras?.total ?? '—'}</span>
            </SettingsRow>
            <SettingsRow label="Đang hoạt động">
              <span className="settings-value" style={{ color: 'var(--accent-success)' }}>{stats?.cameras?.running ?? '—'}</span>
            </SettingsRow>
          </SettingsSection>
        </div>
      )}

      {/* Change Password Modal */}
      <Modal isOpen={showPw} onClose={() => { setShowPw(false); setPwForm({ current: '', newPw: '', confirm: '' }) }} title="🔑 Đổi mật khẩu">
        <div className="form-group">
          <label>Mật khẩu hiện tại</label>
          <input type="password" placeholder="••••••" value={pwForm.current} onChange={e => setPwForm({ ...pwForm, current: e.target.value })} />
        </div>
        <div className="form-group">
          <label>Mật khẩu mới (≥ 6 ký tự)</label>
          <input type="password" placeholder="••••••" value={pwForm.newPw} onChange={e => setPwForm({ ...pwForm, newPw: e.target.value })} />
        </div>
        <div className="form-group">
          <label>Xác nhận mật khẩu mới</label>
          <input type="password" placeholder="••••••" value={pwForm.confirm} onChange={e => setPwForm({ ...pwForm, confirm: e.target.value })} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
          <button className="btn-secondary" onClick={() => setShowPw(false)}>Hủy</button>
          <button className="btn-primary" onClick={handleChangePw}>✅ Đổi mật khẩu</button>
        </div>
      </Modal>

      {/* Add User Modal */}
      <Modal isOpen={showAddUser} onClose={() => setShowAddUser(false)} title="➕ Tạo tài khoản mới">
        <div className="form-group">
          <label>Tên đăng nhập *</label>
          <input placeholder="giaovien01" value={userForm.username} onChange={e => setUserForm({ ...userForm, username: e.target.value })} />
        </div>
        <div className="form-group">
          <label>Mật khẩu * (≥ 6 ký tự)</label>
          <input type="password" placeholder="••••••" value={userForm.password} onChange={e => setUserForm({ ...userForm, password: e.target.value })} />
        </div>
        <div className="form-group">
          <label>Vai trò</label>
          <select value={userForm.role} onChange={e => setUserForm({ ...userForm, role: e.target.value })}>
            <option value="teacher">👩‍🏫 Giáo viên</option>
            <option value="admin">🛡️ Quản trị viên</option>
          </select>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
          <button className="btn-secondary" onClick={() => setShowAddUser(false)}>Hủy</button>
          <button className="btn-primary" onClick={handleAddUser}>✅ Tạo tài khoản</button>
        </div>
      </Modal>
    </div>
  )
}
