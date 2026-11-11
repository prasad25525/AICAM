import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import AlertsProvider from '../alerts/AlertsProvider'
import Sidebar from './Sidebar'
import TopNav from './TopNav'

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <AlertsProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
          <TopNav onMenuClick={() => setSidebarOpen(true)} />
          <main className="flex-1 p-4 sm:p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </AlertsProvider>
  )
}
