import { Navigate, Route, Routes } from 'react-router-dom'
import { MainLayout } from './layout/MainLayout'
import { HistoryPage } from './pages/HistoryPage'
import { HomePage } from './pages/HomePage'
import { JobDetailPage } from './pages/JobDetailPage'
import { LoginPage } from './pages/LoginPage'
import { LogsPage } from './pages/LogsPage'
import { NotificationsPage } from './pages/NotificationsPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
