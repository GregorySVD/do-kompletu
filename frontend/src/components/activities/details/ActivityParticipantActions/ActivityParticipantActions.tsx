import {
  Alert,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Typography,
} from '@mui/material'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../../../context/auth'
import { useCheckInActivityMutation } from '../../../../hooks/mutations/useCheckInActivityMutation'
import { useConfirmActivityMutation } from '../../../../hooks/mutations/useConfirmActivityMutation'
import { useJoinActivityMutation } from '../../../../hooks/mutations/useJoinActivityMutation'
import { useLeaveActivityMutation } from '../../../../hooks/mutations/useLeaveActivityMutation'
import { useCurrentPosition } from '../../../../hooks/useCurrentPosition'
import type {
  ActivityDetails,
  ActivityParticipation,
} from '../../../../types/activity'
import {
  getActivityParticipantActionErrorMessage,
  getCheckInActivityErrorMessage,
  getConfirmActivityErrorMessage,
} from '../../../../utils/activityParticipantActionError'
import { formatDateTime } from '../../../../utils/dateFormat'
import './ActivityParticipantActions.css'

interface ActivityParticipantActionsProps {
  activity: ActivityDetails
}

function ParticipationStatus({
  activity,
  participation,
}: {
  activity: ActivityDetails
  participation: ActivityParticipation
}) {
  switch (participation.status) {
    case 'JOINED':
      return (
        <>
          <Typography component="h2" variant="h6">
            Jesteś w komplecie
          </Typography>
          {participation.effective_confirmation_deadline_at !== null && (
            <Typography color="text.secondary">
              Potwierdź udział do:{' '}
              {formatDateTime(participation.effective_confirmation_deadline_at)}
            </Typography>
          )}
        </>
      )
    case 'WAITLISTED':
      return (
        <>
          <Typography component="h2" variant="h6">
            Jesteś na liście oczekujących
          </Typography>
          {participation.waitlist_position !== null && (
            <Typography color="text.secondary">
              Twoja pozycja w kolejce: {participation.waitlist_position}
            </Typography>
          )}
          <Typography color="text.secondary">
            Osób na liście oczekujących: {activity.waitlist_count}
          </Typography>
        </>
      )
    case 'CONFIRMED':
      return (
        <>
          <Typography component="h2" variant="h6">
            Udział potwierdzony
          </Typography>
          {activity.checkin_opens_at !== null &&
            activity.checkin_closes_at !== null && (
              <Typography color="text.secondary">
                Check-in: {formatDateTime(activity.checkin_opens_at)} –{' '}
                {formatDateTime(activity.checkin_closes_at)}
              </Typography>
            )}
        </>
      )
    case 'CHECKED_IN':
      return (
        <Typography component="h2" variant="h6">
          Check-in wykonany
        </Typography>
      )
    case 'COMPLETED':
      return (
        <Typography component="h2" variant="h6">
          Aktywność ukończona
        </Typography>
      )
    case 'NO_SHOW':
      return (
        <Typography component="h2" variant="h6">
          Nieobecność
        </Typography>
      )
    case 'CONFIRMATION_EXPIRED':
      return (
        <>
          <Typography component="h2" variant="h6">
            Rezerwacja miejsca wygasła
          </Typography>
          <Typography color="text.secondary">
            Udział nie został potwierdzony w wymaganym czasie.
          </Typography>
        </>
      )
    case 'WAITLIST_EXPIRED':
      return (
        <Typography component="h2" variant="h6">
          Lista oczekujących została zamknięta
        </Typography>
      )
  }
}

function ActivityParticipantActions({
  activity,
}: ActivityParticipantActionsProps) {
  const { isAuthenticated, isLoading } = useAuth()
  const [isLeaveDialogOpen, setIsLeaveDialogOpen] = useState(false)
  const [checkInErrorMessage, setCheckInErrorMessage] = useState<string | null>(
    null,
  )
  const participantActionLockRef = useRef(false)
  const confirmMutation = useConfirmActivityMutation()
  const checkInMutation = useCheckInActivityMutation()
  const joinMutation = useJoinActivityMutation()
  const leaveMutation = useLeaveActivityMutation()
  const {
    errorMessage: geolocationErrorMessage,
    getCurrentPosition,
    isLocating,
    resetError: resetGeolocationError,
  } = useCurrentPosition()
  const participation = activity.current_user_participation
  const isWaitlisted = participation?.status === 'WAITLISTED'
  const isParticipantActionPending =
    confirmMutation.isPending ||
    checkInMutation.isPending ||
    joinMutation.isPending ||
    leaveMutation.isPending ||
    isLocating
  const canJoin = isAuthenticated && activity.permissions.can_join
  const canLeave =
    isAuthenticated && participation !== null && activity.permissions.can_leave
  const canConfirm = isAuthenticated && activity.permissions.can_confirm
  const canCheckIn = isAuthenticated && activity.permissions.can_check_in
  const canPromptLogin =
    !isLoading && !isAuthenticated && activity.status === 'PUBLISHED'

  function handleJoin() {
    if (
      !canJoin ||
      isParticipantActionPending ||
      participantActionLockRef.current
    ) {
      return
    }

    participantActionLockRef.current = true
    joinMutation.mutate(activity.id, {
      onSettled: () => {
        participantActionLockRef.current = false
      },
    })
  }

  function openLeaveDialog() {
    if (!canLeave || isParticipantActionPending) {
      return
    }

    leaveMutation.reset()
    setIsLeaveDialogOpen(true)
  }

  function closeLeaveDialog() {
    if (!isParticipantActionPending) {
      setIsLeaveDialogOpen(false)
    }
  }

  function confirmLeave() {
    if (
      !canLeave ||
      isParticipantActionPending ||
      participantActionLockRef.current
    ) {
      return
    }

    participantActionLockRef.current = true
    leaveMutation.mutate(activity.id, {
      onSuccess: () => setIsLeaveDialogOpen(false),
      onSettled: () => {
        participantActionLockRef.current = false
      },
    })
  }

  function handleConfirm() {
    if (
      !canConfirm ||
      isParticipantActionPending ||
      participantActionLockRef.current
    ) {
      return
    }

    participantActionLockRef.current = true
    confirmMutation.mutate(activity.id, {
      onSettled: () => {
        participantActionLockRef.current = false
      },
    })
  }

  async function handleCheckIn() {
    if (
      !canCheckIn ||
      isParticipantActionPending ||
      participantActionLockRef.current
    ) {
      return
    }

    participantActionLockRef.current = true
    setCheckInErrorMessage(null)
    resetGeolocationError()

    try {
      const position = await getCurrentPosition()

      if (position === null) {
        return
      }

      await checkInMutation.mutateAsync({
        activityId: activity.id,
        payload: {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy_m: position.coords.accuracy,
        },
      })
    } catch (error) {
      setCheckInErrorMessage(getCheckInActivityErrorMessage(error))
    } finally {
      checkInMutation.reset()
      participantActionLockRef.current = false
    }
  }

  if (isLoading || (participation === null && !canJoin && !canPromptLogin)) {
    return null
  }

  const joinLabel =
    activity.max_participants !== null && activity.available_slots === 0
      ? 'Dołącz do kolejki'
      : 'Dołącz do kompletu'

  return (
    <>
      <Card
        component="section"
        variant="outlined"
        className="activity-participant-actions"
      >
        <CardContent className="activity-participant-actions__content">
          {participation !== null ? (
            <ParticipationStatus
              activity={activity}
              participation={participation}
            />
          ) : (
            <>
              <Typography component="h2" variant="h6">
                Dołącz do aktywności
              </Typography>
              <Typography color="text.secondary">
                Zapisz się, aby dołączyć do kompletu lub listy oczekujących.
              </Typography>
            </>
          )}

          {joinMutation.isError && (
            <Alert severity="error">
              {getActivityParticipantActionErrorMessage(joinMutation.error)}
            </Alert>
          )}

          {confirmMutation.isError && (
            <Alert severity="error">
              {getConfirmActivityErrorMessage(confirmMutation.error)}
            </Alert>
          )}

          {geolocationErrorMessage && (
            <Alert severity="error">{geolocationErrorMessage}</Alert>
          )}

          {checkInErrorMessage && (
            <Alert severity="error">{checkInErrorMessage}</Alert>
          )}

          {canCheckIn && (
            <Typography color="text.secondary" variant="body2">
              Check-in wykorzysta jednorazowo lokalizację urządzenia, aby
              zweryfikować lokalizację dla check-inu.
            </Typography>
          )}

          <div className="activity-participant-actions__buttons">
            {canPromptLogin && (
              <Button component={Link} to="/login" variant="contained">
                Zaloguj się, aby dołączyć
              </Button>
            )}

            {canJoin && (
              <Button
                variant="contained"
                disabled={isParticipantActionPending}
                onClick={handleJoin}
              >
                {joinMutation.isPending ? 'Dołączanie...' : joinLabel}
              </Button>
            )}

            {canConfirm && (
              <Button
                variant="contained"
                disabled={isParticipantActionPending}
                onClick={handleConfirm}
              >
                {confirmMutation.isPending
                  ? 'Potwierdzanie...'
                  : 'Potwierdź udział'}
              </Button>
            )}

            {canCheckIn && (
              <Button
                variant="contained"
                disabled={isParticipantActionPending}
                onClick={() => void handleCheckIn()}
              >
                {isLocating
                  ? 'Pobieranie lokalizacji...'
                  : checkInMutation.isPending
                    ? 'Weryfikowanie lokalizacji...'
                    : 'Wykonaj check-in'}
              </Button>
            )}

            {canLeave && (
              <Button
                color="error"
                variant="outlined"
                disabled={isParticipantActionPending}
                onClick={openLeaveDialog}
              >
                {isWaitlisted ? 'Opuść kolejkę' : 'Zrezygnuj'}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Dialog
        fullWidth
        maxWidth="sm"
        open={isLeaveDialogOpen}
        onClose={closeLeaveDialog}
      >
        <DialogTitle>
          {isWaitlisted ? 'Opuścić kolejkę?' : 'Zrezygnować z udziału?'}
        </DialogTitle>
        <DialogContent>
          {!isWaitlisted && (
            <DialogContentText>
              Twoje miejsce może zostać przekazane kolejnej osobie.
            </DialogContentText>
          )}
          {leaveMutation.isError && (
            <Alert
              className="activity-participant-actions__dialog-error"
              severity="error"
            >
              {getActivityParticipantActionErrorMessage(leaveMutation.error)}
            </Alert>
          )}
        </DialogContent>
        <DialogActions className="activity-participant-actions__dialog-actions">
          <Button
            disabled={isParticipantActionPending}
            onClick={closeLeaveDialog}
          >
            Wróć
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={isParticipantActionPending}
            onClick={confirmLeave}
          >
            {leaveMutation.isPending
              ? 'Zapisywanie...'
              : isWaitlisted
                ? 'Opuść kolejkę'
                : 'Zrezygnuj'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

export default ActivityParticipantActions
