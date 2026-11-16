import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/auth'
import AdminAccessDenied from '../admin/AdminAccessDenied/AdminAccessDenied'
import LoadingSkeleton from '../system/LoadingSkeleton/LoadingSkeleton'
import './RequireAdmin.css'

function RequireAdmin() {
  const { isLoading, user } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <main className="admin-auth-loading">
        <LoadingSkeleton
          message="Sprawdzanie uprawnień administratora..."
          variant="route"
        />
      </main>
    )
  }

  if (user === null) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return user.is_admin ? <Outlet /> : <AdminAccessDenied />
}

export default RequireAdmin
