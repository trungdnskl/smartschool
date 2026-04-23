// API requests use relative paths — Vite proxy routes /api/* to backend in dev
// In prod: same origin (behind reverse proxy)
const BASE = ''

async function request(method, path, body) {
  const headers = {}
  if (body) headers['Content-Type'] = 'application/json'

  // Attach auth token nếu có (fix A2)
  const token = localStorage.getItem('auth_token')
  if (token) headers['Authorization'] = `Bearer ${token}`

  const opts = { method, headers }
  if (body) opts.body = JSON.stringify(body)

  const res = await fetch(`${BASE}${path}`, opts)
  const data = await res.json().catch(() => ({}))
  return { ok: res.ok, status: res.status, data }
}

const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  del: (path) => request('DELETE', path),
}

export default api
