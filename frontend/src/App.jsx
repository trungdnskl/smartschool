import { useEffect, Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Layout/Sidebar';
import TitleBar from './components/Layout/TitleBar';
import { ToastProvider } from './components/UI/Toast';
import { useWebSocket } from './hooks/useWebSocket';
import useAuthStore from './store/authStore';
import './App.css';

// ── Lazy-loaded pages (tối ưu #1) ─────────────────────
// Mỗi page thành chunk riêng, chỉ load khi navigate tới
const DashboardPage = lazy(() => import('./pages/Dashboard/DashboardPage'));
const CamerasPage = lazy(() => import('./pages/Cameras/CamerasPage'));
const StudentsPage = lazy(() => import('./pages/Students/StudentsPage'));
const TeachersPage = lazy(() => import('./pages/Teachers/TeachersPage'));
const ClassesPage = lazy(() => import('./pages/Classes/ClassesPage'));
const AttendancePage = lazy(() => import('./pages/Attendance/AttendancePage'));
const EmotionsPage = lazy(() => import('./pages/Emotions/EmotionsPage'));
const AnalyticsPage = lazy(() => import('./pages/Analytics/AnalyticsPage'));
const SettingsPage = lazy(() => import('./pages/Settings/SettingsPage'));
const LoginPage = lazy(() => import('./pages/Login/LoginPage'));

/** Page loading fallback */
function PageLoader() {
  return (
    <div className="page-loader">
      <div className="page-loader-spinner" />
      <p>Đang tải trang...</p>
    </div>
  );
}

/** Mount WebSocket globally so it stays alive across page navigations */
function WebSocketProvider({ children }) {
  useWebSocket()
  return children
}

/** Auth guard — redirects to /login if not authenticated */
function RequireAuth({ children }) {
  const { isAuthenticated, isLoading } = useAuthStore()
  if (isLoading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner" />
        <p>Đang kiểm tra đăng nhập...</p>
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return children
}

/** Role guard — only admin can access */
function RequireAdmin({ children }) {
  const { user } = useAuthStore()
  if (user?.role !== 'admin') {
    return (
      <div className="page-enter" style={{ padding: 40, textAlign: 'center' }}>
        <h2 style={{ color: 'var(--accent-danger)', marginBottom: 8 }}>🚫 Không có quyền truy cập</h2>
        <p style={{ color: 'var(--text-muted)' }}>Bạn cần quyền quản trị viên để xem trang này.</p>
      </div>
    )
  }
  return children
}

function MainLayout({ children }) {
  return (
    <div className="app-container">
      <TitleBar />
      <div className="main-content">
        <Sidebar />
        <div className="content-area page-enter">
          <Suspense fallback={<PageLoader />}>
            {children}
          </Suspense>
        </div>
      </div>
    </div>
  );
}

function AuthenticatedApp() {
  return (
    <RequireAuth>
      <WebSocketProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<MainLayout><DashboardPage /></MainLayout>} />
          <Route path="/cameras" element={<MainLayout><CamerasPage /></MainLayout>} />
          <Route path="/students" element={<MainLayout><StudentsPage /></MainLayout>} />
          <Route path="/teachers" element={<MainLayout><TeachersPage /></MainLayout>} />
          <Route path="/classes" element={<MainLayout><ClassesPage /></MainLayout>} />
          <Route path="/attendance" element={<MainLayout><AttendancePage /></MainLayout>} />
          <Route path="/emotions" element={<MainLayout><EmotionsPage /></MainLayout>} />
          <Route path="/analytics" element={<MainLayout><AnalyticsPage /></MainLayout>} />
          <Route path="/settings" element={<MainLayout><SettingsPage /></MainLayout>} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </WebSocketProvider>
    </RequireAuth>
  )
}

function App() {
  const init = useAuthStore(s => s.init)
  useEffect(() => { init() }, [init])

  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={
            <Suspense fallback={<PageLoader />}>
              <LoginPage />
            </Suspense>
          } />
          <Route path="/*" element={<AuthenticatedApp />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}

export default App;
