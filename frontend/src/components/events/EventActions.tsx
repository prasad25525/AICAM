import { Ban, CheckCheck, Eye, RotateCcw } from 'lucide-react'
import type { EventStatus } from '../../api/events'

/** Which status changes make sense from each status. */
export const NEXT_ACTIONS: Record<EventStatus, EventStatus[]> = {
  open: ['acknowledged', 'resolved', 'false_alarm'],
  acknowledged: ['resolved', 'false_alarm'],
  resolved: ['open'],
  false_alarm: ['open'],
}

export const ACTION_META: Record<EventStatus, { label: string; icon: typeof Eye }> = {
  acknowledged: { label: 'Acknowledge', icon: Eye },
  resolved: { label: 'Resolve', icon: CheckCheck },
  false_alarm: { label: 'False alarm', icon: Ban },
  open: { label: 'Reopen', icon: RotateCcw },
}
