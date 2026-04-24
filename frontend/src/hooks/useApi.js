/**
 * API Client — Centralized fetch wrapper (tối ưu #7)
 *
 * Features:
 * - Auto retry with backoff (network errors only)
 * - Error classification (network/auth/validation/server)
 * - Request deduplication for GET requests
 * - Auth token injection
 */

const BASE = ''

// ── In-flight GET request dedup cache ────────────────────
const _inflightGets = new Map()

// ── Error classification ─────────────────────────────────
export class ApiError extends Error {
  constructor(type, status, data, message) {
    super(message || `API Error: ${type}`)
    this.type = type       // 'network' | 'auth' | 'validation' | 'server'
    this.status = status
    this.data = data
  }
}

function classifyError(status, data) {
  if (status === 401 || status === 403) {
    return new ApiError('auth', status, data, 'Phiên đăng nhập hết hạn')
  }
  if (status === 422 || status === 400) {
    return new ApiError('validation', status, data, data?.detail || 'Dữ liệu không hợp lệ')
  }
  if (status >= 500) {
    return new ApiError('server', status, data, 'Lỗi máy chủ')
  }
  return new ApiError('unknown', status, data, 'Lỗi không xác định')
}

// ── Core request with retry ──────────────────────────────
async function request(method, path, body, options = {}) {
  const { retries = 2, retryDelay = 1000, dedupGet = true } = options

  // Dedup GET requests (tối ưu #7 — prevent double fetch)
  if (method === 'GET' && dedupGet) {
    const key = path
    if (_inflightGets.has(key)) {
      return _inflightGets.get(key)
    }
    const promise = _doRequest(method, path, body, retries, retryDelay)
      .finally(() => _inflightGets.delete(key))
    _inflightGets.set(key, promise)
    return promise
  }

  return _doRequest(method, path, body, retries, retryDelay)
}

async function _doRequest(method, path, body, retries, retryDelay) {
  const headers = {}
  if (body) headers['Content-Type'] = 'application/json'

  // Attach auth token nếu có
  const token = localStorage.getItem('auth_token')
  if (token) headers['Authorization'] = `Bearer ${token}`

  const opts = { method, headers }
  if (body) opts.body = JSON.stringify(body)

  let lastError = null

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(`${BASE}${path}`, opts)
      const data = await res.json().catch(() => ({}))

      if (res.ok) {
        return { ok: true, status: res.status, data }
      }

      // Auth errors — don't retry, redirect
      if (res.status === 401) {
        // Auto-logout on expired token
        localStorage.removeItem('auth_token')
        window.dispatchEvent(new CustomEvent('auth:expired'))
      }

      // Don't retry 4xx errors (client's fault)
      if (res.status >= 400 && res.status < 500) {
        return { ok: false, status: res.status, data, error: classifyError(res.status, data) }
      }

      // 5xx — retry
      lastError = classifyError(res.status, data)

    } catch (e) {
      // Network error — retry
      lastError = new ApiError('network', 0, null, 'Không thể kết nối máy chủ')
    }

    // Wait before retry (exponential backoff)
    if (attempt < retries) {
      await new Promise(r => setTimeout(r, retryDelay * Math.pow(2, attempt)))
    }
  }

  return { ok: false, status: lastError?.status || 0, data: {}, error: lastError }
}

// ── Public API ───────────────────────────────────────────
const api = {
  get: (path, opts) => request('GET', path, null, opts),
  post: (path, body, opts) => request('POST', path, body, opts),
  put: (path, body, opts) => request('PUT', path, body, opts),
  patch: (path, body, opts) => request('PATCH', path, body, opts),
  del: (path, opts) => request('DELETE', path, null, opts),
}

export default api
