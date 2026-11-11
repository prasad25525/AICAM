import { BarChart3, Bell, Camera, LayoutDashboard, Map, MonitorPlay, Settings, type LucideIcon } from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/live', label: 'Live View', icon: MonitorPlay },
  { to: '/cameras', label: 'Cameras', icon: Camera },
  { to: '/events', label: 'Events & Alerts', icon: Bell },
  { to: '/zones', label: 'Zones', icon: Map },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
]
