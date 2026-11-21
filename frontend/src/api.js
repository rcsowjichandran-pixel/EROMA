const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'
export const MEDIA_BASE = `${BASE.replace(/\/api\/?$/, '')}/media`
export function getToken(){ return localStorage.getItem('sofalux_access') }
export async function api(path, options={}) {
  const isFormData = options.body instanceof FormData
  const headers = { ...(!isFormData ? {'Content-Type':'application/json'} : {}), ...(options.headers||{}) }
  if (getToken()) headers.Authorization = `Bearer ${getToken()}`
  const response = await fetch(`${BASE}${path}`, {...options, headers})
  const data = response.status === 204 ? null : await response.json().catch(()=>({}))
  if (!response.ok) throw new Error(data.detail || JSON.stringify(data) || 'Request failed')
  return data
}
export async function login(username,password){
  const data = await api('/auth/token/', {method:'POST', body:JSON.stringify({username,password})})
  localStorage.setItem('sofalux_access',data.access); localStorage.setItem('sofalux_refresh',data.refresh)
  return api('/me/')
}
