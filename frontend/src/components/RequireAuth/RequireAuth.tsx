import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/auth'
import LoadingSkeleton from '../system/LoadingSkeleton/LoadingSkeleton'
import './RequireAuth.css'

function RequireAuth() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <main className="auth-loading">
        <LoadingSkeleton message="Sprawdzanie sesji..." variant="route" />
      </main>
    )
  }

  return isAuthenticated ? (
    <Outlet />
  ) : (
    <Navigate to="/login" replace state={{ from: location }} />
  )
}

export default RequireAuth
