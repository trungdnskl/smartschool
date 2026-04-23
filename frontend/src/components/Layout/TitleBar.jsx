import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import useAppStore from '../../store/appStore'
import useAuthStore from '../../store/authStore'

function useTimer(sessionStartTime, sessionActive) {
  const [display, setDisplay] = useState('00:00:00')
  useEffect(() => {
    if (!sessionActive || !sessionStartTime) { setDisplay('00:00:00'); return }
    const tick = () => {
      const elapsed = Math.floor((Date.now() - sessionStartTime.getTime()) / 1000)
      const h = String(Math.floor(elapsed / 3600)).padStart(2, '0')
      const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0')
      const s = String(elapsed % 60).padStart(2, '0')
      setDisplay(`${h}:${m}:${s}`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [sessionActive, sessionStartTime])
  return display
}

export default function TitleBar() {
  const { wsConnected, sessionActive, sessionStartTime } = useAppStore()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const timer = useTimer(sessionStartTime, sessionActive)
  const [showMenu, setShowMenu] = useState(false)
  const menuRef = useRef(null)

  // Close menu on click outside
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setShowMenu(false)
    }
    if (showMenu) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showMenu])

  const initials = user?.username
    ? user.username.slice(0, 2).toUpperCase()
    : 'GV'

  const roleBadge = user?.role === 'admin' ? '🛡️' : '👩‍🏫'

  const handleLogout = () => {
    setShowMenu(false)
    logout()
    navigate('/login')
  }

  return (
    <header className="title-bar">
      <div className="title-bar-left">
        <div className="title-bar-logo">🎓</div>
        <div className="title-bar-text">
          <h1>Classroom Engagement</h1>
          <span className="title-subtitle">
            {sessionActive ? 'Đang giám sát...' : 'Chưa bắt đầu buổi học'}
          </span>
        </div>
      </div>

      <div className="title-bar-center">
        {sessionActive && (
          <div className="session-timer">
            <span>⏱</span>
            <span className="timer-value">{timer}</span>
          </div>
        )}
      </div>

      <div className="title-bar-right">
        <div className="connection-status">
          <span className={`status-dot ${wsConnected ? 'online' : 'offline'}`} />
          <span>{wsConnected ? 'Trực tuyến' : 'Mất kết nối'}</span>
        </div>

        {/* User menu */}
        <div className="user-menu-container" ref={menuRef}>
          <button
            className="user-avatar"
            title={`${user?.username || 'User'} (${user?.role || ''})`}
            onClick={() => setShowMenu(!showMenu)}
          >
            {initials}
          </button>

          {showMenu && (
            <div className="user-dropdown">
              <div className="user-dropdown-header">
                <div className="user-dropdown-avatar">{initials}</div>
                <div className="user-dropdown-info">
                  <span className="user-dropdown-name">{user?.username || 'User'}</span>
                  <span className="user-dropdown-role">{roleBadge} {user?.role === 'admin' ? 'Quản trị viên' : 'Giáo viên'}</span>
                </div>
              </div>
              <div className="user-dropdown-divider" />
              <button className="user-dropdown-item" onClick={() => { setShowMenu(false); navigate('/settings') }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
                Cài đặt
              </button>
              <button className="user-dropdown-item user-dropdown-logout" onClick={handleLogout}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                Đăng xuất
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
