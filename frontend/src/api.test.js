import {afterEach, expect, it, vi} from 'vitest'
import {api, clearSession, SESSION_EXPIRED} from './api'

const response = (status, data) => ({status, ok: status>=200 && status<300, json: async()=>data})

afterEach(()=>{clearSession();vi.unstubAllGlobals()})

it('renews an expired token once and retries simultaneous requests', async()=>{
  localStorage.setItem('sofalux_access','expired')
  localStorage.setItem('sofalux_refresh','refresh-token')
  const fetchRequest = vi.fn(async(url, options)=>{
    if (url.endsWith('/auth/token/refresh/')) {
      expect(JSON.parse(options.body)).toEqual({refresh:'refresh-token'})
      return response(200,{access:'renewed'})
    }
    return options.headers.Authorization==='Bearer renewed'
      ? response(200,{ok:true}) : response(401,{detail:'Token expired'})
  })
  vi.stubGlobal('fetch',fetchRequest)
  await expect(Promise.all([api('/me/'),api('/profile/')])).resolves.toEqual([{ok:true},{ok:true}])
  expect(fetchRequest.mock.calls.filter(([url])=>url.endsWith('/auth/token/refresh/'))).toHaveLength(1)
})

it('clears an invalid refresh token and lets a public request continue signed out', async()=>{
  localStorage.setItem('sofalux_access','expired')
  localStorage.setItem('sofalux_refresh','invalid')
  const expired = vi.fn()
  window.addEventListener(SESSION_EXPIRED,expired,{once:true})
  vi.stubGlobal('fetch',vi.fn(async(url, options)=>{
    if (url.endsWith('/auth/token/refresh/') || options.headers.Authorization) return response(401,{detail:'Expired'})
    return response(200,[])
  }))
  await expect(api('/products/')).resolves.toEqual([])
  expect(localStorage.getItem('sofalux_access')).toBeNull()
  expect(localStorage.getItem('sofalux_refresh')).toBeNull()
  expect(expired).toHaveBeenCalledOnce()
})
