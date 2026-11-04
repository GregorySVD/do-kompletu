import {
  PeopleAltOutlined,
  PowerSettingsNewOutlined,
} from '@mui/icons-material'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useSetAdminUserActiveMutation } from '../../../hooks/mutations/useSetAdminUserActiveMutation'
import { useAdminUsersQuery } from '../../../hooks/queries/useAdminUsersQuery'
import type { AdminUser } from '../../../types/admin'
import {
  getAdminErrorMessage,
  getAdminErrorStatus,
} from '../../../utils/adminError'
import { formatDateTime } from '../../../utils/dateFormat'
import AdminPagination from '../AdminPagination/AdminPagination'

interface AdminUsersSectionProps {
  currentUserId: string
  onForbidden: () => void
}

const pageSize = 20

function AdminUsersSection({
  currentUserId,
  onForbidden,
}: AdminUsersSectionProps) {
  const [offset, setOffset] = useState(0)
  const [userToDeactivate, setUserToDeactivate] = useState<AdminUser | null>(
    null,
  )
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const usersQuery = useAdminUsersQuery({ limit: pageSize, offset })
  const activeMutation = useSetAdminUserActiveMutation()
  const pendingUserId = activeMutation.isPending
    ? activeMutation.variables?.userId
    : undefined
  const dialogError =
    userToDeactivate !== null && activeMutation.isError
      ? getAdminErrorMessage(activeMutation.error, 'set-user-active')
      : null
  const sectionError =
    userToDeactivate === null && activeMutation.isError
      ? getAdminErrorMessage(activeMutation.error, 'set-user-active')
      : null

  useEffect(() => {
    if (
      getAdminErrorStatus(usersQuery.error) === 403 ||
      getAdminErrorStatus(activeMutation.error) === 403
    ) {
      onForbidden()
    }
  }, [activeMutation.error, onForbidden, usersQuery.error])

  function activateUser(user: AdminUser) {
    if (activeMutation.isPending) {
      return
    }

    activeMutation.reset()
    setSuccessMessage(null)
    activeMutation.mutate(
      { userId: user.id, isActive: true },
      {
        onSuccess: (updatedUser) => {
          setSuccessMessage(`Konto ${updatedUser.display_name} jest aktywne.`)
        },
      },
    )
  }

  function openDeactivationDialog(user: AdminUser) {
    if (activeMutation.isPending || user.id === currentUserId) {
      return
    }

    activeMutation.reset()
    setSuccessMessage(null)
    setUserToDeactivate(user)
  }

  function closeDeactivationDialog() {
    if (!activeMutation.isPending) {
      setUserToDeactivate(null)
    }
  }

  function confirmDeactivation() {
    if (!userToDeactivate || activeMutation.isPending) {
      return
    }

    activeMutation.mutate(
      { userId: userToDeactivate.id, isActive: false },
      {
        onSuccess: (updatedUser) => {
          setSuccessMessage(
            `Konto ${updatedUser.display_name} jest nieaktywne.`,
          )
          setUserToDeactivate(null)
        },
      },
    )
  }

  return (
    <Card
      component="section"
      variant="outlined"
      className="admin-section admin-section--users"
      aria-labelledby="admin-users-title"
    >
      <CardContent className="admin-section__content">
        <header className="admin-section__heading">
          <span className="admin-section__icon" aria-hidden="true">
            <PeopleAltOutlined />
          </span>
          <div>
            <span className="admin-section__eyebrow">KONTA // 01</span>
            <Typography id="admin-users-title" component="h2" variant="h4">
              Użytkownicy
            </Typography>
            <Typography color="text.secondary">
              Status kont, uprawnienia i punkty użytkowników.
            </Typography>
          </div>
        </header>

        {successMessage && (
          <Alert severity="success" role="status">
            {successMessage}
          </Alert>
        )}
        {sectionError && <Alert severity="error">{sectionError}</Alert>}

        {usersQuery.isPending ? (
          <div className="admin-section__loading" role="status">
            <CircularProgress size="1.8rem" />
            <span>Ładowanie użytkowników...</span>
          </div>
        ) : usersQuery.isError ? (
          <div className="admin-section__error">
            <Alert severity="error">
              {getAdminErrorMessage(usersQuery.error, 'load-users')}
            </Alert>
            {getAdminErrorStatus(usersQuery.error) !== 403 && (
              <Button
                disabled={usersQuery.isFetching}
                variant="outlined"
                onClick={() => void usersQuery.refetch()}
              >
                {usersQuery.isFetching ? 'Ponawianie...' : 'Spróbuj ponownie'}
              </Button>
            )}
          </div>
        ) : usersQuery.data.length === 0 ? (
          <p className="admin-section__empty">
            Brak użytkowników na tej stronie.
          </p>
        ) : (
          <ul className="admin-record-list">
            {usersQuery.data.map((adminUser) => {
              const isCurrentUser = adminUser.id === currentUserId
              const isThisUserPending = pendingUserId === adminUser.id

              return (
                <li key={adminUser.id}>
                  <article className="admin-record-card">
                    <header className="admin-record-card__heading">
                      <div>
                        <Typography component="h3" variant="h6">
                          {adminUser.display_name}
                        </Typography>
                        <span className="admin-record-card__identifier">
                          {adminUser.email}
                        </span>
                      </div>
                      <div className="admin-record-card__badges">
                        <Chip
                          color={adminUser.is_active ? 'success' : 'default'}
                          label={adminUser.is_active ? 'Aktywne' : 'Nieaktywne'}
                          size="small"
                          variant="outlined"
                        />
                        {adminUser.is_admin && (
                          <Chip
                            color="secondary"
                            label="Administrator"
                            size="small"
                            variant="outlined"
                          />
                        )}
                      </div>
                    </header>

                    <dl className="admin-record-card__metadata">
                      <div>
                        <dt>Punkty</dt>
                        <dd>{adminUser.points_total}</dd>
                      </div>
                      <div>
                        <dt>Utworzono</dt>
                        <dd>
                          <time dateTime={adminUser.created_at}>
                            {formatDateTime(adminUser.created_at)}
                          </time>
                        </dd>
                      </div>
                      <div>
                        <dt>Status administratora</dt>
                        <dd>{adminUser.is_admin ? 'Tak' : 'Nie'}</dd>
                      </div>
                    </dl>

                    <div className="admin-record-card__actions">
                      <Button
                        color={adminUser.is_active ? 'error' : 'primary'}
                        disabled={
                          activeMutation.isPending ||
                          (adminUser.is_active && isCurrentUser)
                        }
                        startIcon={
                          isThisUserPending ? (
                            <CircularProgress aria-hidden="true" size="1rem" />
                          ) : (
                            <PowerSettingsNewOutlined aria-hidden="true" />
                          )
                        }
                        variant={adminUser.is_active ? 'outlined' : 'contained'}
                        title={
                          adminUser.is_active && isCurrentUser
                            ? 'Nie możesz dezaktywować własnego konta'
                            : undefined
                        }
                        onClick={() =>
                          adminUser.is_active
                            ? openDeactivationDialog(adminUser)
                            : activateUser(adminUser)
                        }
                      >
                        {isThisUserPending
                          ? 'Zapisywanie...'
                          : adminUser.is_active
                            ? 'Dezaktywuj'
                            : 'Aktywuj'}
                      </Button>
                    </div>
                  </article>
                </li>
              )
            })}
          </ul>
        )}

        {usersQuery.isSuccess && (
          <AdminPagination
            isFetching={usersQuery.isFetching}
            itemCount={usersQuery.data.length}
            offset={offset}
            pageSize={pageSize}
            onOffsetChange={setOffset}
          />
        )}
      </CardContent>

      <Dialog
        fullWidth
        maxWidth="sm"
        open={userToDeactivate !== null}
        aria-describedby="admin-user-deactivate-description"
        aria-labelledby="admin-user-deactivate-title"
        onClose={closeDeactivationDialog}
      >
        <DialogTitle id="admin-user-deactivate-title">
          Dezaktywować konto?
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="admin-user-deactivate-description">
            Użytkownik {userToDeactivate?.display_name} utraci możliwość
            logowania i korzystania z chronionych funkcji aplikacji.
          </DialogContentText>
          {dialogError && (
            <Alert className="admin-dialog__error" severity="error">
              {dialogError}
            </Alert>
          )}
        </DialogContent>
        <DialogActions className="admin-dialog__actions">
          <Button
            disabled={activeMutation.isPending}
            onClick={closeDeactivationDialog}
          >
            Wróć
          </Button>
          <Button
            color="error"
            disabled={activeMutation.isPending}
            variant="contained"
            onClick={confirmDeactivation}
          >
            {activeMutation.isPending ? 'Dezaktywowanie...' : 'Dezaktywuj'}
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  )
}

export default AdminUsersSection
