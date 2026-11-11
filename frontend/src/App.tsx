import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import { NAV_ITEMS } from './components/layout/nav'
import { RequireAuth } from './lib/auth'
import CamerasPage from './pages/CamerasPage'
import DashboardPage from './pages/DashboardPage'
import EventsPage from './pages/EventsPage'
import LivePage from './pages/LivePage'
import LoginPage from './pages/LoginPage'
import PlaceholderPage from './pages/PlaceholderPage'
import ReportsPage from './pages/ReportsPage'
import SettingsPage from './pages/SettingsPage'
import ZonesPage from './pages/ZonesPage'

const BUILT_PAGES = ['/dashboard', '/live', '/cameras', '/events', '/zones', '/reports', '/settings']

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/live" element={<LivePage />} />
        <Route path="/cameras" element={<CamerasPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/zones" element={<ZonesPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        {NAV_ITEMS.filter((item) => !BUILT_PAGES.includes(item.to)).map((item) => (
          <Route key={item.to} path={item.to} element={<PlaceholderPage title={item.label} />} />
        ))}
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
