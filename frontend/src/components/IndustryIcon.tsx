import { ChefHat, Factory, ScanEye, type LucideProps } from 'lucide-react'

const ICONS = { 'chef-hat': ChefHat, factory: Factory }

/** The icon an industry pack names (unknown names fall back to the platform icon). */
export default function IndustryIcon({ name, ...props }: { name: string } & LucideProps) {
  const Icon = ICONS[name as keyof typeof ICONS] ?? ScanEye
  return <Icon {...props} />
}
