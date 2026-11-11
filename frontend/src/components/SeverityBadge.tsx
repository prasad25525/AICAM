import { AlertOctagon, AlertTriangle, Info } from 'lucide-react'
import type { Severity } from '../api/events'

const STYLES: Record<Severity, { label: string; icon: typeof Info; className: string }> = {
  critical: { label: 'Critical', icon: AlertOctagon, className: 'border-red-400/50 bg-red-500/15 text-red-200' },
  warning: { label: 'Warning', icon: AlertTriangle, className: 'border-amber-400/50 bg-amber-500/15 text-amber-200' },
  info: { label: 'Info', icon: Info, className: 'border-sky-400/50 bg-sky-500/15 text-sky-200' },
}

export default function SeverityBadge({ severity }: { severity: Severity }) {
  const { label, icon: Icon, className } = STYLES[severity]
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${className}`}>
      <Icon size={12} />
      {label}
    </span>
  )
}
