import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Bell, LogOut, Menu, UserCircle2, Volume2, VolumeX } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useOpenEventCount } from '../../api/events'
import { api } from '../../lib/api'
import { useAlerts } from '../../lib/alerts'
import { useAuth } from '../../lib/auth'
import IndustrySwitcher from './IndustrySwitcher'
import { NAV_ITEMS } from './nav'

export default function TopNav({ onMenuClick }: { onMenuClick: () => void }) {
  const { logout } = useAuth()
  const { pathname } = useLocation()
  const [today] = useState(() => format(new Date(), 'EEEE, d MMMM yyyy'))
  const title = NAV_ITEMS.find((item) => pathname.startsWith(item.to))?.label ?? 'VigilSiddhi'

  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: async () => (await api.get<{ username: string }>('/auth/me')).data,
  })
  const { data: openEvents } = useOpenEventCount()
  const { connected, muted, setMuted } = useAlerts()

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-gold-500/60 bg-forest-900/95 px-4 backdrop-blur sm:px-6">
      <button onClick={onMenuClick} className="rounded-lg p-2 text-emerald-100/70 hover:bg-forest-800 hover:text-lime-glow lg:hidden" aria-label="Open menu">
        <Menu size={20} />
      </button>

      <div className="min-w-0">
        <h1 className="truncate text-lg font-semibold text-white">{title}</h1>
        <p className="hidden text-xs text-emerald-100/50 sm:block">{today}</p>
      </div>

      <div className="ml-auto flex items-center gap-2 sm:gap-3">
        <IndustrySwitcher />

        <button
          onClick={() => setMuted(!muted)}
          className="rounded-lg border border-forest-600 p-2 text-emerald-100/70 hover:border-gold-500 hover:text-lime-glow"
          aria-label={muted ? 'Unmute alert sound' : 'Mute alert sound'}
          aria-pressed={muted}
          title={muted ? 'Alert sound off' : 'Alert sound on'}
        >
          {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
        </button>

        <Link
          to="/events"
          className="relative rounded-lg border border-forest-600 p-2 text-emerald-100/70 hover:border-gold-500 hover:text-lime-glow"
          aria-label={openEvents ? `Notifications: ${openEvents} open events` : 'Notifications: no open events'}
        >
          <Bell size={18} />
          <span
            className={`absolute -bottom-0.5 -left-0.5 h-2 w-2 rounded-full border border-forest-900 ${connected ? 'bg-lime-glow' : 'bg-emerald-100/30'}`}
            aria-label={connected ? 'Live alerts connected' : 'Live alerts disconnected'}
            role="status"
            title={connected ? 'Live alerts connected' : 'Live alerts reconnecting…'}
          />
          {!!openEvents && (
            <span className="absolute -right-2 -top-2 min-w-5 rounded-full border-2 border-forest-900 bg-lime-glow px-1 text-center text-[10px] font-bold leading-4 text-forest-950">
              {openEvents > 99 ? '99+' : openEvents}
            </span>
          )}
        </Link>

        <div className="hidden items-center gap-2 rounded-lg border border-forest-600 px-3 py-1.5 text-sm sm:flex">
          <UserCircle2 size={18} className="text-gold-300" />
          <span className="text-emerald-50">{me?.username ?? '…'}</span>
        </div>

        <button
          onClick={logout}
          className="flex items-center gap-1.5 rounded-lg border border-gold-500 bg-forest-800 px-3 py-2 text-sm font-medium text-gold-300 transition hover:bg-gold-500 hover:text-forest-950"
        >
          <LogOut size={16} />
          <span className="hidden sm:inline">Logout</span>
        </button>
      </div>
    </header>
  )
}
