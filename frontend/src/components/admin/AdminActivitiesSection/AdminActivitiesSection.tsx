import { BlockOutlined, EventNoteOutlined } from '@mui/icons-material'
import {
  Alert,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import ActivityStatusBadge from '../../activities/details/ActivityStatusBadge/ActivityStatusBadge'
import { useAdminCancelActivityMutation } from '../../../hooks/mutations/useAdminCancelActivityMutation'
import { useAdminActivitiesQuery } from '../../../hooks/queries/useAdminActivitiesQuery'
import type { AdminActivity } from '../../../types/admin'
import {
  getAdminErrorMessage,
  getAdminErrorStatus,
} from '../../../utils/adminError'
import { formatDateTime } from '../../../utils/dateFormat'
import AdminPagination from '../AdminPagination/AdminPagination'

interface AdminActivitiesSectionProps {
  onForbidden: () => void
}

const pageSize = 20

function cancellationIsBlocked(activity: AdminActivity) {
  return (
    activity.status === 'CANCELLED' ||
    activity.status === 'ENDED' ||
    Date.parse(activity.end_at) <= Date.now()
  )
}

function AdminActivitiesSection({ onForbidden }: AdminActivitiesSectionProps) {
  const [offset, setOffset] = useState(0)
  const [activityToCancel, setActivityToCancel] =
    useState<AdminActivity | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const activitiesQuery = useAdminActivitiesQuery({ limit: pageSize, offset })
  const cancelMutation = useAdminCancelActivityMutation()
  const pendingActivityId = cancelMutation.isPending
    ? cancelMutation.variables
    : undefined

  useEffect(() => {
    if (
      getAdminErrorStatus(activitiesQuery.error) === 403 ||
      getAdminErrorStatus(cancelMutation.error) === 403
    ) {
      onForbidden()
    }
  }, [activitiesQuery.error, cancelMutation.error, onForbidden])

  function openCancellationDialog(activity: AdminActivity) {
    if (cancelMutation.isPending || cancellationIsBlocked(activity)) {
      return
    }

    cancelMutation.reset()
    setSuccessMessage(null)
    setActivityToCancel(activity)
  }

  function closeCancellationDialog() {
    if (!cancelMutation.isPending) {
      setActivityToCancel(null)
    }
  }

  function confirmCancellation() {
    if (!activityToCancel || cancelMutation.isPending) {
      return
    }

    cancelMutation.mutate(activityToCancel.id, {
      onSuccess: (activity) => {
        setSuccessMessage(`Aktywność „${activity.title}” została anulowana.`)
        setActivityToCancel(null)
      },
    })
  }

  return (
    <Card
      component="section"
      variant="outlined"
      className="admin-section admin-section--activities"
      aria-labelledby="admin-activities-title"
    >
      <CardContent className="admin-section__content">
        <header className="admin-section__heading">
          <span className="admin-section__icon" aria-hidden="true">
            <EventNoteOutlined />
          </span>
          <div>
            <span className="admin-section__eyebrow">AKTYWNOŚCI // 02</span>
            <Typography id="admin-activities-title" component="h2" variant="h4">
              Aktywności
            </Typography>
            <Typography color="text.secondary">
              Moderacja cyklu życia i aktualnego obłożenia aktywności.
            </Typography>
          </div>
        </header>

        {successMessage && (
          <Alert severity="success" role="status">
            {successMessage}
          </Alert>
        )}

        {activitiesQuery.isPending ? (
          <div className="admin-section__loading" role="status">
            <CircularProgress size="1.8rem" />
            <span>Ładowanie aktywności...</span>
          </div>
        ) : activitiesQuery.isError ? (
          <div className="admin-section__error">
            <Alert severity="error">
              {getAdminErrorMessage(activitiesQuery.error, 'load-activities')}
            </Alert>
            {getAdminErrorStatus(activitiesQuery.error) !== 403 && (
              <Button
                disabled={activitiesQuery.isFetching}
                variant="outlined"
                onClick={() => void activitiesQuery.refetch()}
              >
                {activitiesQuery.isFetching
                  ? 'Ponawianie...'
                  : 'Spróbuj ponownie'}
              </Button>
            )}
          </div>
        ) : activitiesQuery.data.length === 0 ? (
          <p className="admin-section__empty">
            Brak aktywności na tej stronie.
          </p>
        ) : (
          <ul className="admin-record-list">
            {activitiesQuery.data.map((activity) => {
              const isBlocked = cancellationIsBlocked(activity)
              const isThisActivityPending = pendingActivityId === activity.id

              return (
                <li key={activity.id}>
                  <article className="admin-record-card">
                    <header className="admin-record-card__heading">
                      <div>
                        <Typography component="h3" variant="h6">
                          {activity.title}
                        </Typography>
                        <span className="admin-record-card__identifier">
                          Organizator: {activity.organizer.display_name}
                        </span>
                      </div>
                      <ActivityStatusBadge status={activity.status} />
                    </header>

                    <dl className="admin-record-card__metadata admin-record-card__metadata--activity">
                      <div>
                        <dt>Start</dt>
                        <dd>
                          <time dateTime={activity.start_at}>
                            {formatDateTime(activity.start_at)}
                          </time>
                        </dd>
                      </div>
                      <div>
                        <dt>Koniec</dt>
                        <dd>
                          <time dateTime={activity.end_at}>
                            {formatDateTime(activity.end_at)}
                          </time>
                        </dd>
                      </div>
                      <div>
                        <dt>Uczestnicy</dt>
                        <dd>{activity.participant_count}</dd>
                      </div>
                      <div>
                        <dt>Lista rezerwowa</dt>
                        <dd>{activity.waitlist_count}</dd>
                      </div>
                      <div>
                        <dt>Status anulowania</dt>
                        <dd>
                          {activity.cancelled_at ? (
                            <time dateTime={activity.cancelled_at}>
                              Anulowano {formatDateTime(activity.cancelled_at)}
                            </time>
                          ) : (
                            'Nieanulowana'
                          )}
                        </dd>
                      </div>
                    </dl>

                    <div className="admin-record-card__actions">
                      <Button
                        color="error"
                        disabled={cancelMutation.isPending || isBlocked}
                        startIcon={
                          isThisActivityPending ? (
                            <CircularProgress aria-hidden="true" size="1rem" />
                          ) : (
                            <BlockOutlined aria-hidden="true" />
                          )
                        }
                        variant="outlined"
                        onClick={() => openCancellationDialog(activity)}
                      >
                        {isThisActivityPending ? 'Anulowanie...' : 'Anuluj'}
                      </Button>
                    </div>
                  </article>
                </li>
              )
            })}
          </ul>
        )}

        {activitiesQuery.isSuccess && (
          <AdminPagination
            isFetching={activitiesQuery.isFetching}
            itemCount={activitiesQuery.data.length}
            offset={offset}
            pageSize={pageSize}
            onOffsetChange={setOffset}
          />
        )}
      </CardContent>

      <Dialog
        fullWidth
        maxWidth="sm"
        open={activityToCancel !== null}
        aria-describedby="admin-activity-cancel-description"
        aria-labelledby="admin-activity-cancel-title"
        onClose={closeCancellationDialog}
      >
        <DialogTitle id="admin-activity-cancel-title">
          Anulować aktywność?
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="admin-activity-cancel-description">
            Aktywność „{activityToCancel?.title}” zniknie z odkrywania, ale jej
            historia i dane uczestnictwa pozostaną zachowane.
          </DialogContentText>
          {cancelMutation.isError && (
            <Alert className="admin-dialog__error" severity="error">
              {getAdminErrorMessage(cancelMutation.error, 'cancel-activity')}
            </Alert>
          )}
        </DialogContent>
        <DialogActions className="admin-dialog__actions">
          <Button
            disabled={cancelMutation.isPending}
            onClick={closeCancellationDialog}
          >
            Wróć
          </Button>
          <Button
            color="error"
            disabled={cancelMutation.isPending}
            variant="contained"
            onClick={confirmCancellation}
          >
            {cancelMutation.isPending ? 'Anulowanie...' : 'Anuluj aktywność'}
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  )
}

export default AdminActivitiesSection
