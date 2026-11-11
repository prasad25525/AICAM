import axios, { isAxiosError } from 'axios'

export const TOKEN_KEY = 'aicam_token'

export const api = axios.create({ baseURL: '/api' })

// Attach the login token to every request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Token expired or invalid: drop it and go back to login.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !err.config?.url?.startsWith('/auth/login')) {
      localStorage.removeItem(TOKEN_KEY)
      window.location.assign('/login')
    }
    return Promise.reject(err)
  },
)

/** Turn a FastAPI error (string detail or validation list) into one readable message. */
export function apiErrorMessage(err: unknown): string {
  if (!isAxiosError(err)) return err instanceof Error ? err.message : 'Something went wrong'
  if (!err.response) return 'Cannot reach the server. Is the backend running?'
  const detail = err.response.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, '')).join('; ')
  }
  return `Request failed (${err.response.status})`
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_at: number
}
