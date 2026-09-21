import { CircularProgress, Typography } from '@mui/material'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/auth'
import './RequireAuth.css'

function RequireAuth() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <main className="auth-loading">
        <CircularProgress size={28} />
        <Typography>Sprawdzanie sesji...</Typography>
      </main>
    )
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />
}

export default RequireAuth
