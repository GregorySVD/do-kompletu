import { AdminPanelSettingsOutlined } from '@mui/icons-material'
import { Typography } from '@mui/material'
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import AdminAccessDenied from '../../components/admin/AdminAccessDenied/AdminAccessDenied'
import AdminActivitiesSection from '../../components/admin/AdminActivitiesSection/AdminActivitiesSection'
import AdminPhotoModerationSection from '../../components/admin/AdminPhotoModerationSection/AdminPhotoModerationSection'
import AdminUsersSection from '../../components/admin/AdminUsersSection/AdminUsersSection'
import { useAuth } from '../../context/auth'
import { adminQueryKey } from '../../hooks/queries/adminQueryKeys'
import './AdminPage.css'

function AdminPage() {
  const queryClient = useQueryClient()
  const { refreshUser, user } = useAuth()
  const [hasLostAdminAccess, setHasLostAdminAccess] = useState(false)
  const accessLossHandledRef = useRef(false)
  const permissionRefreshStartedRef = useRef(false)

  const handleForbidden = useCallback(() => {
    if (accessLossHandledRef.current) {
      return
    }

    accessLossHandledRef.current = true
    setHasLostAdminAccess(true)
  }, [])

  useEffect(() => {
    if (hasLostAdminAccess === false || permissionRefreshStartedRef.current) {
      return
    }

    permissionRefreshStartedRef.current = true
    void queryClient.cancelQueries(
      { queryKey: adminQueryKey },
      { silent: true },
    )
    queryClient.removeQueries({ queryKey: adminQueryKey })
    void refreshUser().catch(() => undefined)
  }, [hasLostAdminAccess, queryClient, refreshUser])

  if (user === null) {
    return null
  }

  if (hasLostAdminAccess) {
    return (
      <AdminAccessDenied message="Serwer odrzucił uprawnienia administratora. Dane panelu zostały usunięte z pamięci aplikacji." />
    )
  }

  return (
    <main className="admin-page">
      <header className="admin-page__heading">
        <div>
          <span className="admin-page__eyebrow">CENTRUM KONTROLI // MVP</span>
          <Typography component="h1" variant="h3">
            Panel administratora
          </Typography>
          <Typography color="text.secondary">
            Zarządzaj kontami, aktywnościami i wskazanymi materiałami.
          </Typography>
        </div>
        <span className="admin-page__status">
          <AdminPanelSettingsOutlined aria-hidden="true" />
          Sesja administratora
        </span>
      </header>

      <div className="admin-page__sections">
        <AdminUsersSection
          currentUserId={user.id}
          onForbidden={handleForbidden}
        />
        <AdminActivitiesSection onForbidden={handleForbidden} />
        <AdminPhotoModerationSection onForbidden={handleForbidden} />
      </div>
    </main>
  )
}

export default AdminPage
