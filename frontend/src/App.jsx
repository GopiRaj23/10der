import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import { useAuth } from './context/AuthContext'
import Admin from './pages/admin/Admin'
import Alerts from './pages/Alerts'
import Dashboard from './pages/Dashboard'
import ForgotPassword from './pages/ForgotPassword'
import Keywords from './pages/Keywords'
import Login from './pages/Login'
import MyTenders from './pages/MyTenders'
import Register from './pages/Register'
import Reports from './pages/Reports'
import Search from './pages/Search'
import Settings from './pages/Settings'
import ShareView from './pages/ShareView'
import TenderDetail from './pages/TenderDetail'
import VerifyEmail from './pages/VerifyEmail'

function Protected({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return <div className="flex h-screen items-center justify-center"><Spinner className="h-8 w-8" /></div>
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/share/:token" element={<ShareView />} />

      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/my-tenders" element={<MyTenders />} />
        <Route path="/search" element={<Search />} />
        <Route path="/tenders/:id" element={<TenderDetail />} />
        <Route path="/keywords" element={<Keywords />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/admin" element={<Admin />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
