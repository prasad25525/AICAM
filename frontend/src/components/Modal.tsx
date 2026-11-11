import { X } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'

const SIZES = { md: 'max-w-lg', xl: 'max-w-5xl' }

export default function Modal({
  title,
  onClose,
  children,
  footer,
  size = 'md',
}: {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  size?: keyof typeof SIZES
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-label={title} className={`relative flex max-h-[90vh] w-full ${SIZES[size]} flex-col rounded-xl border border-gold-500 bg-forest-900 shadow-[0_0_40px_rgba(201,162,39,0.15)]`}>
        <div className="flex items-center justify-between border-b border-forest-700 px-5 py-3">
          <h2 className="font-semibold text-gold-300">{title}</h2>
          <button onClick={onClose} className="rounded p-1 text-emerald-100/60 hover:text-lime-glow" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="overflow-y-auto p-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-forest-700 px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export const btnPrimary =
  'inline-flex items-center justify-center gap-1.5 rounded-lg border border-gold-400 bg-lime-glow px-4 py-2 text-sm font-semibold text-forest-950 transition hover:bg-lime-300 disabled:cursor-not-allowed disabled:opacity-60'
export const btnSecondary =
  'inline-flex items-center justify-center gap-1.5 rounded-lg border border-forest-600 px-4 py-2 text-sm text-emerald-100/80 transition hover:border-gold-500 hover:text-white'
export const btnDanger =
  'inline-flex items-center justify-center gap-1.5 rounded-lg border border-red-400/60 bg-red-500/15 px-4 py-2 text-sm font-medium text-red-200 transition hover:bg-red-500/30 disabled:opacity-60'
export const inputBase =
  'w-full rounded-lg border border-forest-600 bg-forest-950/70 px-3 py-2 text-sm text-white placeholder:text-emerald-200/40 outline-none transition focus:border-lime-glow focus:ring-2 focus:ring-lime-glow/30'
