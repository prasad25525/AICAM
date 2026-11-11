/** The Azkashine company logo. The image has a light grey background, so it sits on a matching
 * rounded tile rather than straight on the dark theme. */
export default function AzkashineLogo({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center rounded-md bg-[#c0c0be] px-1.5 py-0.5 ring-1 ring-gold-500/50 ${className}`}>
      <img src="/azkashine-logo.jpg" alt="Azkashine Software & Services Pvt. Ltd." className="h-full w-auto" />
    </span>
  )
}
