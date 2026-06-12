// API client with JWT access/refresh handling.
// Note: tokens live in localStorage for simplicity; for stricter XSS posture
// move the refresh token to an httpOnly cookie.
const API_BASE = '/api'

let accessToken = localStorage.getItem('tr_access') || null
let refreshToken = localStorage.getItem('tr_refresh') || null

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export function setTokens(access, refresh) {
  accessToken = access
  refreshToken = refresh
  localStorage.setItem('tr_access', access)
  localStorage.setItem('tr_refresh', refresh)
}

export function clearTokens() {
  accessToken = null
  refreshToken = null
  localStorage.removeItem('tr_access')
  localStorage.removeItem('tr_refresh')
}

export function hasTokens() {
  return Boolean(refreshToken)
}

async function tryRefresh() {
  if (!refreshToken) return false
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return false
    const data = await res.json()
    setTokens(data.access_token, data.refresh_token)
    return true
  } catch {
    return false
  }
}

async function request(path, { method = 'GET', body, params, raw = false, auth = true } = {}) {
  const url = new URL(API_BASE + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
    })
  }
  const doFetch = () => {
    const headers = {}
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    if (auth && accessToken) headers['Authorization'] = `Bearer ${accessToken}`
    return fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  }

  let res = await doFetch()
  if (res.status === 401 && auth && (await tryRefresh())) {
    res = await doFetch()
  }
  if (res.status === 401 && auth) {
    clearTokens()
    window.dispatchEvent(new Event('tr-logout'))
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data)
    } catch { /* non-JSON error body */ }
    throw new ApiError(detail, res.status)
  }
  if (raw) return res
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get: (path, params, opts) => request(path, { params, ...opts }),
  post: (path, body, opts) => request(path, { method: 'POST', body, ...opts }),
  put: (path, body, opts) => request(path, { method: 'PUT', body, ...opts }),
  del: (path, opts) => request(path, { method: 'DELETE', ...opts }),
  download: async (path, filename) => {
    const res = await request(path, { raw: true })
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}

// ---- IST display helpers (storage is UTC, display is UTC+5:30) ----

const dtFmt = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit', month: 'short', year: 'numeric',
  hour: '2-digit', minute: '2-digit', hour12: true,
  timeZone: 'Asia/Kolkata',
})
const dFmt = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit', month: 'short', year: 'numeric',
})

export function fmtDateTime(value) {
  if (!value) return '—'
  const iso = value.endsWith('Z') || value.includes('+') ? value : value + 'Z'
  return dtFmt.format(new Date(iso)) + ' IST'
}

export function fmtDate(value) {
  if (!value) return '—'
  if (value.includes('T')) return fmtDateTime(value)
  return dFmt.format(new Date(value + 'T00:00:00'))
}

export function daysUntil(value) {
  if (!value) return null
  const iso = value.endsWith('Z') || value.includes('+') ? value : value + 'Z'
  return Math.ceil((new Date(iso) - Date.now()) / 86400000)
}

export function fmtINR(value) {
  if (value === null || value === undefined) return '—'
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(2)} Cr`
  if (value >= 1e5) return `₹${(value / 1e5).toFixed(2)} L`
  return `₹${Number(value).toLocaleString('en-IN')}`
}
