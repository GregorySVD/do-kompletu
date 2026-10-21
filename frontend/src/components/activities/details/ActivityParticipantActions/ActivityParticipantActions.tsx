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
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../../../context/auth'
import { useJoinActivityMutation } from '../../../../hooks/mutations/useJoinActivityMutation'
import { useLeaveActivityMutation } from '../../../../hooks/mutations/useLeaveActivityMutation'
import type {
  ActivityDetails,
  ActivityParticipation,
} from '../../../../types/activity'
import { getActivityParticipantActionErrorMessage } from '../../../../utils/activityParticipantActionError'
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
        <Typography component="h2" variant="h6">
          Udział potwierdzony
        </Typography>
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
  const joinMutation = useJoinActivityMutation()
  const leaveMutation = useLeaveActivityMutation()
  const participation = activity.current_user_participation
  const isWaitlisted = participation?.status === 'WAITLISTED'
  const isPending = joinMutation.isPending || leaveMutation.isPending
  const canJoin = isAuthenticated && activity.permissions.can_join
  const canLeave =
    isAuthenticated && participation !== null && activity.permissions.can_leave
  const canPromptLogin =
    !isLoading && !isAuthenticated && activity.status === 'PUBLISHED'

  function handleJoin() {
    if (!canJoin || isPending) {
      return
    }

    joinMutation.mutate(activity.id)
  }

  function openLeaveDialog() {
    if (!canLeave || isPending) {
      return
    }

    leaveMutation.reset()
    setIsLeaveDialogOpen(true)
  }

  function closeLeaveDialog() {
    if (!leaveMutation.isPending) {
      setIsLeaveDialogOpen(false)
    }
  }

  function confirmLeave() {
    if (!canLeave || leaveMutation.isPending) {
      return
    }

    leaveMutation.mutate(activity.id, {
      onSuccess: () => setIsLeaveDialogOpen(false),
    })
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

          <div className="activity-participant-actions__buttons">
            {canPromptLogin && (
              <Button component={Link} to="/login" variant="contained">
                Zaloguj się, aby dołączyć
              </Button>
            )}

            {canJoin && (
              <Button
                variant="contained"
                disabled={isPending}
                onClick={handleJoin}
              >
                {joinMutation.isPending ? 'Dołączanie...' : joinLabel}
              </Button>
            )}

            {canLeave && (
              <Button
                color="error"
                variant="outlined"
                disabled={isPending}
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
          <Button disabled={leaveMutation.isPending} onClick={closeLeaveDialog}>
            Wróć
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={leaveMutation.isPending}
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
