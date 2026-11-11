import { useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Eye, EyeOff, LoaderCircle, Lock, LogIn, ScanEye, User } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useIndustries } from '../api/industry'
import AzkashineLogo from '../components/AzkashineLogo'
import IndustryIcon from '../components/IndustryIcon'
import { apiErrorMessage } from '../lib/api'
import { useAuth } from '../lib/auth'

// Prefilled from .env.development only, so production builds ship empty fields.
const DEFAULT_USERNAME = import.meta.env.VITE_LOGIN_USERNAME ?? ''
const DEFAULT_PASSWORD = import.meta.env.VITE_LOGIN_PASSWORD ?? ''

const inputClass =
  'w-full rounded-lg border border-forest-600 bg-forest-950/70 py-2.5 pl-10 pr-3 text-sm text-white ' +
  'placeholder:text-emerald-200/40 outline-none transition focus:border-lime-glow focus:ring-2 focus:ring-lime-glow/30'

export default function LoginPage() {
  const { token, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState(DEFAULT_USERNAME)
  const [password, setPassword] = useState(DEFAULT_PASSWORD)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const qc = useQueryClient()
  const industries = useIndustries()
  // '' = not picked: the industry that is active now.
  const [picked, setPicked] = useState('')
  const industry = picked || industries.data?.active || ''
  const showTabs = !!industries.data && !industries.data.locked && industries.data.industries.length > 1

  if (token) return <Navigate to="/dashboard" replace />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password, showTabs ? industry : undefined)
      qc.clear() // nothing cached from another session or industry
      navigate('/dashboard', { replace: true })
    } catch (err) {
      const status = isAxiosError(err) ? err.response?.status : undefined
      setError(
        status === 401 ? 'Invalid username or password'
          : status === 409 || status === 422 ? apiErrorMessage(err)
          : 'Cannot reach the server. Is the backend running?',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      {/* Background glow */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(181,242,61,0.12),transparent_45%),radial-gradient(circle_at_80%_85%,rgba(201,162,39,0.14),transparent_45%)]" />

      <div className="relative w-full max-w-sm rounded-2xl bg-gradient-to-br from-gold-300 via-gold-500 to-lime-glow p-[1.5px] shadow-[0_0_40px_rgba(201,162,39,0.18)]">
        <div className="rounded-2xl bg-forest-900 px-7 py-8">
          <div className="mb-7 flex flex-col items-center text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-gold-500 bg-forest-800 text-lime-glow shadow-[0_0_18px_rgba(181,242,61,0.25)]">
              <ScanEye size={28} />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-white">
              Vigil<span className="text-lime-glow">Siddhi</span>
            </h1>
            <p className="mt-1 text-sm text-emerald-100/60">A Vision AI Platform</p>
          </div>

          {showTabs && (
            <div className="mb-5">
              <span id="industry-label" className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">Industry</span>
              <div role="tablist" aria-labelledby="industry-label" className="grid grid-cols-2 gap-1 rounded-lg border border-forest-600 bg-forest-950/70 p-1">
                {industries.data!.industries.map((i) => {
                  const selected = i.key === industry
                  return (
                    <button
                      key={i.key}
                      type="button"
                      role="tab"
                      aria-selected={selected}
                      onClick={() => setPicked(i.key)}
                      title={i.description}
                      className={`flex items-center justify-center gap-1.5 rounded-md px-2 py-2 text-sm font-medium transition ${
                        selected ? 'border border-gold-500 bg-forest-800 text-lime-glow' : 'border border-transparent text-emerald-100/60 hover:text-white'
                      }`}
                    >
                      <IndustryIcon name={i.icon} size={16} /> {i.name}
                    </button>
                  )
                })}
              </div>
              <p className="mt-1.5 text-center text-xs text-emerald-100/50">
                {industries.data!.industries.find((i) => i.key === industry)?.description}
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">Username</span>
              <div className="relative">
                <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-200/50" />
                <input
                  className={inputClass}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  placeholder="Enter username"
                  required
                />
              </div>
            </label>

            <label className="block">
              <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">Password</span>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-200/50" />
                <input
                  className={`${inputClass} pr-10`}
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  placeholder="Enter password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-emerald-200/60 hover:text-lime-glow"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>

            {error && (
              <p role="alert" className="rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-gold-400 bg-lime-glow py-2.5 text-sm font-semibold text-forest-950 transition hover:bg-lime-300 hover:shadow-[0_0_20px_rgba(181,242,61,0.35)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? <LoaderCircle size={16} className="animate-spin" /> : <LogIn size={16} />}
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="mt-6 flex flex-col items-center gap-2 border-t border-forest-700 pt-4">
            <span className="text-[10px] uppercase tracking-wider text-emerald-100/40">Powered by</span>
            <AzkashineLogo className="h-9" />
          </div>
        </div>
      </div>
    </main>
  )
}
