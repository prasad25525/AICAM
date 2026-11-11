import { useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { FlaskConical, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { eventImageUrl, type Severity } from '../../api/events'
import { resetForNewIndustry } from '../../api/industry'
import { mediaTokenQuery, useMediaToken } from '../../api/streams'
import { AlertsContext, loadMuted, playAlertSound, saveMuted } from '../../lib/alerts'
import SeverityBadge from '../SeverityBadge'

interface PushedEvent {
  id: number
  type_label: string
  severity: Severity
  message: string
  camera_name: string
  has_image: boolean
  simulated: boolean
  occurred_at: string
}

type Message =
  | { type: 'hello' }
  | { type: 'created'; event: PushedEvent }
  | { type: 'changed'; ids: number[] }
  | { type: 'industry'; industry: string; name: string } // the active industry was switched (here or in another browser)

const INDUSTRY_NOTICE_MS = 5000

const MAX_TOASTS = 4
const RECONNECT_MS = 3000
// Critical alerts stay until dismissed; the rest fade on their own.
const AUTO_DISMISS_MS: Record<Severity, number | null> = { critical: null, warning: 10_000, info: 6_000 }

export default function AlertsProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const token = useMediaToken()
  const [connected, setConnected] = useState(false)
  const [muted, setMutedState] = useState(loadMuted)
  const [toasts, setToasts] = useState<PushedEvent[]>([])
  const mutedRef = useRef(muted)
  const timers = useRef(new Map<number, number>())
  const [industryNotice, setIndustryNotice] = useState<string | null>(null)
  const noticeTimer = useRef<number | undefined>(undefined)

  const setMuted = useCallback((m: boolean) => {
    mutedRef.current = m
    setMutedState(m)
    saveMuted(m)
  }, [])

  const dismiss = useCallback((id: number) => {
    window.clearTimeout(timers.current.get(id))
    timers.current.delete(id)
    setToasts((ts) => ts.filter((t) => t.id !== id))
  }, [])

  const show = useCallback(
    (e: PushedEvent) => {
      setToasts((ts) => [e, ...ts.filter((t) => t.id !== e.id)].slice(0, MAX_TOASTS))
      const ms = AUTO_DISMISS_MS[e.severity]
      if (ms) timers.current.set(e.id, window.setTimeout(() => dismiss(e.id), ms))
      if (!mutedRef.current) playAlertSound(e.severity)
    },
    [dismiss],
  )

  // One live connection for the whole app. EventSource can't send headers, so it uses the media token.
  const haveToken = !!token.data
  useEffect(() => {
    if (!haveToken) return
    let source: EventSource | null = null
    let retry: number | undefined
    let stopped = false

    const connect = async () => {
      // Always use a fresh token: the one from an old connection may have expired.
      const fresh = await qc.fetchQuery({ ...mediaTokenQuery, staleTime: 60_000 }).catch(() => null)
      if (stopped) return
      if (!fresh) {
        retry = window.setTimeout(connect, RECONNECT_MS)
        return
      }
      source = new EventSource(`/api/events/stream?token=${encodeURIComponent(fresh)}`)
      source.onopen = () => setConnected(true)
      source.onmessage = (m) => {
        const msg = JSON.parse(m.data) as Message
        if (msg.type === 'hello') return
        if (msg.type === 'industry') {
          // Everything on screen belonged to the old industry.
          setToasts([])
          resetForNewIndustry(qc)
          setIndustryNotice(msg.name)
          window.clearTimeout(noticeTimer.current)
          noticeTimer.current = window.setTimeout(() => setIndustryNotice(null), INDUSTRY_NOTICE_MS)
          return
        }
        qc.invalidateQueries({ queryKey: ['events'] })
        qc.invalidateQueries({ queryKey: ['dashboard'] })
        if (msg.type === 'created') show(msg.event)
      }
      source.onerror = () => {
        setConnected(false)
        // The browser retries dropped connections itself; a refused one (e.g. expired token) is closed for good.
        if (source?.readyState === EventSource.CLOSED) {
          source.close()
          retry = window.setTimeout(connect, RECONNECT_MS)
        }
      }
    }
    connect()
    return () => {
      stopped = true
      window.clearTimeout(retry)
      source?.close()
      setConnected(false)
    }
  }, [haveToken, qc, show])

  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach((t) => window.clearTimeout(t))
  }, [])

  return (
    <AlertsContext.Provider value={{ connected, muted, setMuted }}>
      {children}
      {industryNotice && (
        <div role="status" className="fixed left-1/2 top-20 z-[60] -translate-x-1/2 rounded-xl border border-gold-500/60 bg-forest-900 px-4 py-2.5 text-sm text-white shadow-[0_8px_30px_rgba(0,0,0,0.5)]">
          Industry changed to <strong className="text-lime-glow">{industryNotice}</strong>
        </div>
      )}
      <div aria-live="polite" className="pointer-events-none fixed right-4 top-20 z-[60] flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-3">
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.severity === 'critical' ? 'alert' : 'status'}
            aria-label={`New alert: ${t.type_label}`}
            className={`pointer-events-auto overflow-hidden rounded-xl border bg-forest-900 shadow-[0_8px_30px_rgba(0,0,0,0.5)] ${
              t.severity === 'critical' ? 'border-red-400/80' : t.severity === 'warning' ? 'border-amber-400/70' : 'border-gold-500/60'
            }`}
          >
            <div className="flex gap-3 p-3">
              <div className="h-14 w-20 shrink-0 overflow-hidden rounded-md border border-forest-600 bg-forest-950">
                {t.has_image && token.data && <img src={eventImageUrl(t.id, token.data)} alt="" className="h-full w-full object-cover" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <SeverityBadge severity={t.severity} />
                  {t.simulated && <FlaskConical size={12} className="text-sky-200" aria-label="Test event" />}
                  <span className="ml-auto text-xs tabular-nums text-emerald-100/50">{format(new Date(t.occurred_at), 'HH:mm:ss')}</span>
                </div>
                <div className="mt-1 truncate text-sm font-semibold text-white">{t.type_label}</div>
                <div className="truncate text-xs text-emerald-100/60">{t.camera_name}</div>
              </div>
              <button onClick={() => dismiss(t.id)} className="self-start rounded p-0.5 text-emerald-100/50 hover:text-white" aria-label="Dismiss alert">
                <X size={16} />
              </button>
            </div>
            <button
              onClick={() => {
                dismiss(t.id)
                navigate('/events')
              }}
              className="w-full border-t border-forest-700 px-3 py-1.5 text-left text-xs font-medium text-gold-300 hover:bg-forest-800 hover:text-lime-glow"
            >
              View in Events & Alerts →
            </button>
          </div>
        ))}
      </div>
    </AlertsContext.Provider>
  )
}
