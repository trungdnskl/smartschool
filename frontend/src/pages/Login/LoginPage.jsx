import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/authStore'

export default function LoginPage() {
  const { login, loginError, isLoading, isAuthenticated } = useAuthStore()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [shakeError, setShakeError] = useState(false)
  const inputRef = useRef(null)

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true })
    }
  }, [isAuthenticated, navigate])

  useEffect(() => { inputRef.current?.focus() }, [])

  useEffect(() => {
    if (loginError) {
      setShakeError(true)
      const t = setTimeout(() => setShakeError(false), 500)
      return () => clearTimeout(t)
    }
  }, [loginError])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    const success = await login(username.trim(), password)
    if (success) {
      navigate('/dashboard')
    }
  }

  return (
    <div className="login-page">
      {/* Animated background */}
      <div className="login-bg">
        <div className="login-bg-orb login-bg-orb-1" />
        <div className="login-bg-orb login-bg-orb-2" />
        <div className="login-bg-orb login-bg-orb-3" />
        <div className="login-bg-grid" />
      </div>

      <div className={`login-card ${shakeError ? 'login-shake' : ''}`}>
        {/* Logo */}
        <div className="login-logo">
          <div className="login-logo-icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="url(#loginGrad)" strokeWidth="1.5">
              <defs>
                <linearGradient id="loginGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#00d4ff" />
                  <stop offset="100%" stopColor="#7c3aed" />
                </linearGradient>
              </defs>
              <path d="M12 14l9-5-9-5-9 5 9 5z" />
              <path d="M12 14l6.16-3.42a1 1 0 0 1 .84.18V17a6 6 0 0 1-12 0v-6.24a1 1 0 0 1 .84-.18L12 14z" />
              <circle cx="12" cy="7" r="2" fill="url(#loginGrad)" stroke="none" />
            </svg>
          </div>
          <h1 className="login-title">Classroom Engagement</h1>
          <p className="login-subtitle">Hệ thống AI giám sát lớp học</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <label htmlFor="login-user">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              Tên đăng nhập
            </label>
            <input
              ref={inputRef}
              id="login-user"
              type="text"
              placeholder="admin"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              disabled={isLoading}
            />
          </div>

          <div className="login-field">
            <label htmlFor="login-pass">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              Mật khẩu
            </label>
            <div className="login-password-wrap">
              <input
                id="login-pass"
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
                disabled={isLoading}
              />
              <button
                type="button"
                className="login-password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          {loginError && (
            <div className="login-error">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" />
                <line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              {loginError}
            </div>
          )}

          <button type="submit" className="login-btn" disabled={isLoading || !username || !password}>
            {isLoading ? (
              <><span className="login-spinner" /> Đang đăng nhập...</>
            ) : (
              <>🔐 Đăng nhập</>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="login-footer">
          <p>🔒 Mặc định: <code>admin</code> / <code>admin123</code></p>
          <p className="login-footer-version">NEHS Classroom AI v2.0</p>
        </div>
      </div>
    </div>
  )
}
