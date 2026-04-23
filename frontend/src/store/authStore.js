import { create } from 'zustand'
import api from '../hooks/useApi'

const useAuthStore = create((set, get) => ({
  // State
  user: null,          // { username, role, user_id, teacher_id }
  token: null,
  isAuthenticated: false,
  isLoading: true,     // True until initial check completes
  loginError: null,

  // Initialize from localStorage
  init: async () => {
    const token = localStorage.getItem('auth_token')
    const userJson = localStorage.getItem('auth_user')
    if (token && userJson) {
      try {
        const user = JSON.parse(userJson)
        set({ token, user, isAuthenticated: true, isLoading: false })
        // Validate token is still valid
        const r = await api.get('/api/auth/me')
        if (!r.ok) {
          // Token expired
          get().logout()
        }
      } catch {
        get().logout()
      }
    } else {
      set({ isLoading: false })
    }
  },

  // Login
  login: async (username, password) => {
    set({ loginError: null, isLoading: true })
    try {
      // Use relative path — Vite proxy handles this in dev mode
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        set({ loginError: data.detail || 'Đăng nhập thất bại', isLoading: false })
        return false
      }
      const user = {
        username: data.username,
        role: data.role,
        user_id: data.user_id,
        teacher_id: data.teacher_id,
      }
      localStorage.setItem('auth_token', data.access_token)
      localStorage.setItem('auth_user', JSON.stringify(user))
      set({ token: data.access_token, user, isAuthenticated: true, isLoading: false, loginError: null })
      return true
    } catch (err) {
      set({ loginError: 'Không thể kết nối đến server', isLoading: false })
      return false
    }
  },

  // Logout
  logout: () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    set({ token: null, user: null, isAuthenticated: false, isLoading: false, loginError: null })
  },

  // Change password
  changePassword: async (currentPassword, newPassword) => {
    const r = await api.post('/api/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return r
  },
}))

export default useAuthStore
