import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'

import { ThemeProvider } from '@/app/ThemeProvider'
import { AuthProvider } from '@/auth/AuthProvider'
import { useAuth } from '@/auth/auth-context'
import { Skeleton } from '@/components/ui/skeleton'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AuthPage } from '@/pages/AuthPage'
import { ChatPage } from '@/pages/ChatPage'

// The landing page carries the display face and the animation runtime. Split so
// signed-in users going straight to /app never download either.
const HomePage = lazy(async () => ({ default: (await import('@/pages/HomePage')).HomePage }))

function ProtectedRoute() {
  const { loading, session } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div aria-label="Loading workspace" className="flex h-svh" role="status">
        <div className="w-64 shrink-0 space-y-2 border-r bg-sidebar p-3">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
        <div className="flex-1 p-6">
          <Skeleton className="h-4 w-48" />
        </div>
      </div>
    )
  }

  if (!session) {
    return <Navigate replace state={{ from: location.pathname }} to="/sign-in" />
  }

  return <Outlet />
}

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <TooltipProvider>
          <AuthProvider>
            <Routes>
              <Route
                element={
                  <Suspense fallback={<div className="min-h-svh bg-background" />}>
                    <HomePage />
                  </Suspense>
                }
                path="/"
              />
              <Route element={<AuthPage mode="sign-in" />} path="/sign-in" />
              <Route element={<AuthPage mode="sign-up" />} path="/sign-up" />
              <Route element={<ProtectedRoute />}>
                <Route element={<ChatPage />} path="/app" />
                <Route element={<ChatPage />} path="/app/chats/:threadId" />
              </Route>
              <Route element={<Navigate replace to="/" />} path="*" />
            </Routes>
          </AuthProvider>
        </TooltipProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

export default App
