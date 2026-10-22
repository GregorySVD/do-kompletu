import { CircularProgress, Typography } from '@mui/material'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/auth'
import './RequireAuth.css'

function RequireAuth() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <main className="auth-loading">
        <CircularProgress size={28} />
        <Typography>Sprawdzanie sesji...</Typography>
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
