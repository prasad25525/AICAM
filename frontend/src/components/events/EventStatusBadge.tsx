import { Ban, CheckCheck, CircleDot, Eye } from 'lucide-react'
import { STATUS_LABELS, type EventStatus } from '../../api/events'

const STYLES: Record<EventStatus, { icon: typeof Eye; className: string }> = {
  open: { icon: CircleDot, className: 'border-lime-glow/60 bg-lime-glow/10 text-lime-glow' },
  acknowledged: { icon: Eye, className: 'border-gold-500/60 bg-gold-500/10 text-gold-300' },
  resolved: { icon: CheckCheck, className: 'border-forest-600 text-emerald-100/60' },
  false_alarm: { icon: Ban, className: 'border-forest-600 text-emerald-100/50' },
}

export default function EventStatusBadge({ status }: { status: EventStatus }) {
  const { icon: Icon, className } = STYLES[status]
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-2 py-0.5 text-xs font-medium ${className}`}>
      <Icon size={12} />
      {STATUS_LABELS[status]}
    </span>
  )
}
