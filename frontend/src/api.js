const BASE = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api').replace(/\/+$/, '')
const BACKEND = BASE.replace(/\/api$/, '')
export const MEDIA_BASE = `${BACKEND}/media`
export const ADMIN_URL = `${BACKEND}/admin/`
export const SESSION_EXPIRED = 'eroma:session-expired'

let pendingRefresh

export function getToken() { return localStorage.getItem('sofalux_access') }
export function hasSession() { return Boolean(getToken() || getRefreshToken()) }

function getRefreshToken() { return localStorage.getItem('sofalux_refresh') }

export function clearSession() {
  localStorage.removeItem('sofalux_access')
  localStorage.removeItem('sofalux_refresh')
}

function expireSession() {
  clearSession()
  window.dispatchEvent(new Event(SESSION_EXPIRED))
}

async function refreshAccessToken(refresh) {
  const response = await fetch(`${BASE}/auth/token/refresh/`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({refresh}),
  })
  const data = await response.json().catch(() => ({}))
  if (getRefreshToken() !== refresh) return null
  if (response.status === 400 || response.status === 401 || response.status === 403) {
    expireSession()
    return null
  }
  if (!response.ok || !data.access) throw new Error('Could not renew your session. Please try again.')
  localStorage.setItem('sofalux_access', data.access)
  if (data.refresh) localStorage.setItem('sofalux_refresh', data.refresh)
  return data.access
}

function renewSession(refresh) {
  if (pendingRefresh?.token === refresh) return pendingRefresh.promise
  const renewal = {token: refresh}
  renewal.promise = refreshAccessToken(refresh).finally(() => {
    if (pendingRefresh === renewal) pendingRefresh = undefined
  })
  pendingRefresh = renewal
  return renewal.promise
}

export async function api(path, {download=false, ...options}={}) {
  const authEndpoint = path.startsWith('/auth/')
  const access = authEndpoint ? null : getToken()
  const refresh = authEndpoint ? null : getRefreshToken()
  const headers = { ...(options.body instanceof FormData ? {} : {'Content-Type':'application/json'}), ...(options.headers||{}) }
  const send = token => fetch(`${BASE}${path}`, {...options, headers: {
    ...headers, ...(token ? {Authorization: `Bearer ${token}`} : {}),
  }})
  let response = await send(access)
  if (!authEndpoint && response.status === 401 && (access || refresh) && getRefreshToken() === refresh) {
    let updated = getToken()
    if (updated === access) {
      if (refresh) updated = await renewSession(refresh)
      else { expireSession(); updated = null }
    }
    if (updated && getToken() === updated) response = await send(updated)
    else if (access && !hasSession()) response = await send(null)
  }
  if (download && response.ok) return response.blob()
  const data = response.status === 204 ? null : await response.json().catch(()=>({}))
  if (!response.ok) {
    const messages = Object.values(data || {}).flat().filter(message => typeof message === 'string')
    throw new Error(data?.detail || messages.join(' ') || 'Request failed')
  }
  return data
}

export async function login(username,password) {
  const data = await api('/auth/token/', {method:'POST', body:JSON.stringify({username,password})})
  localStorage.setItem('sofalux_access',data.access)
  localStorage.setItem('sofalux_refresh',data.refresh)
  return api('/me/')
}
