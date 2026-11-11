import { Construction } from 'lucide-react'

export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center rounded-xl border border-gold-500/60 bg-forest-900 px-6 py-16 text-center">
      <Construction size={36} className="mb-4 text-lime-glow" />
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <p className="mt-1 text-sm text-emerald-100/60">This section is coming next.</p>
    </div>
  )
}
