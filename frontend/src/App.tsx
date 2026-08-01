import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'

import { AuthProvider } from '@/auth/AuthProvider'
import { useAuth } from '@/auth/auth-context'
import { AuthPage } from '@/pages/AuthPage'
import { ProtectedPage } from '@/pages/ProtectedPage'

function ProtectedRoute() {
  const { loading, session } = useAuth()
  const location = useLocation()
  if (loading) return <main className="p-8">Loading…</main>
  if (!session) return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  return <Outlet />
}

function App() {
  return <BrowserRouter><AuthProvider><Routes><Route path="/sign-in" element={<AuthPage mode="sign-in" />} /><Route path="/sign-up" element={<AuthPage mode="sign-up" />} /><Route element={<ProtectedRoute />}><Route path="/app" element={<ProtectedPage />} /></Route><Route path="*" element={<Navigate to="/app" replace />} /></Routes></AuthProvider></BrowserRouter>
}

export default App
