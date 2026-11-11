import { formatDistanceToNowStrict } from 'date-fns'
import { CircleDashed, CircleOff, LoaderCircle, Wifi, WifiOff } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Camera } from '../../api/cameras'

export default function StatusBadge({ camera, checking }: { camera: Camera; checking: boolean }) {
  const s = camera.status

  if (!camera.enabled) {
    return <Badge icon={<CircleOff size={12} />} label="Disabled" className="border-forest-600 text-emerald-100/50" />
  }
  if (checking) {
    return <Badge icon={<LoaderCircle size={12} className="animate-spin" />} label="Checking…" className="border-gold-500/50 text-gold-300" />
  }
  if (!s) {
    return <Badge icon={<CircleDashed size={12} />} label="Not checked" className="border-forest-600 text-emerald-100/60" />
  }

  const when = `checked ${formatDistanceToNowStrict(new Date(s.checked_at), { addSuffix: true })}`
  if (s.state === 'online') {
    return (
      <div>
        <Badge icon={<Wifi size={12} />} label="Online" className="border-lime-glow/60 bg-lime-glow/10 text-lime-glow" />
        <div className="mt-1 text-xs text-emerald-100/50">
          {s.width}×{s.height} · {when}
        </div>
      </div>
    )
  }
  return (
    <div className="max-w-[240px]">
      <Badge icon={<WifiOff size={12} />} label="Offline" className="border-red-400/50 bg-red-500/15 text-red-200" />
      <div className="mt-1 line-clamp-2 text-xs text-red-200/70" title={s.error ?? undefined}>
        {s.error}
      </div>
    </div>
  )
}

function Badge({ icon, label, className }: { icon: ReactNode; label: string; className: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${className}`}>
      {icon}
      {label}
    </span>
  )
}
