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
} from '@mui/material'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import ReactConfetti from 'react-confetti'
import { Link, useLocation } from 'react-router-dom'
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
import { getActivityAvailability } from '../../../../utils/activityAvailability'
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

const JOIN_SUCCESS_MESSAGE_DURATION_MS = 6000
const CONFETTI_COLORS = ['#32d583', '#3de5c4', '#5aa9ff', '#8b5cf6', '#e454ff']

function useViewportSize() {
  const [viewportSize, setViewportSize] = useState({ height: 0, width: 0 })

  useEffect(() => {
    function updateViewportSize() {
      setViewportSize({
        height: window.innerHeight,
        width: window.innerWidth,
      })
    }

    updateViewportSize()
    window.addEventListener('resize', updateViewportSize)

    return () => window.removeEventListener('resize', updateViewportSize)
  }, [])

  return viewportSize
}

type ParticipationStatusTone =
  'active' | 'complete' | 'confirmed' | 'waiting' | 'warning'

interface ParticipationStatusPanelProps {
  children?: ReactNode
  eyebrow: string
  iconSrc: string
  title: string
  tone: ParticipationStatusTone
}

function ParticipationStatusPanel({
  children,
  eyebrow,
  iconSrc,
  title,
  tone,
}: ParticipationStatusPanelProps) {
  return (
    <header
      className={`activity-participant-actions__status activity-participant-actions__status--${tone}`}
    >
      <span className="activity-participant-actions__status-icon">
        <img src={iconSrc} alt="" width="64" height="64" aria-hidden="true" />
      </span>

      <div className="activity-participant-actions__status-copy">
        <p className="activity-participant-actions__eyebrow">{eyebrow}</p>
        <h2 className="activity-participant-actions__title">{title}</h2>
        {children}
      </div>
    </header>
  )
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
        <ParticipationStatusPanel
          eyebrow="Twoje uczestnictwo"
          iconSrc="/icons/icons8-confetti-64.png"
          title="Jesteś w komplecie"
          tone="active"
        >
          {participation.effective_confirmation_deadline_at !== null && (
            <p className="activity-participant-actions__status-detail">
              Potwierdź udział do
              <time
                className="activity-participant-actions__deadline"
                dateTime={participation.effective_confirmation_deadline_at}
              >
                {formatDateTime(
                  participation.effective_confirmation_deadline_at,
                )}
              </time>
            </p>
          )}
        </ParticipationStatusPanel>
      )
    case 'WAITLISTED':
      return (
        <ParticipationStatusPanel
          eyebrow="Lista rezerwowa"
          iconSrc="/icons/icons8-list-64.png"
          title="Czekasz na wolne miejsce"
          tone="waiting"
        >
          {participation.waitlist_position !== null && (
            <p className="activity-participant-actions__status-detail">
              Twoja pozycja: <strong>#{participation.waitlist_position}</strong>
            </p>
          )}
          <p className="activity-participant-actions__status-detail">
            Osób na liście rezerwowej: {activity.waitlist_count}
          </p>
        </ParticipationStatusPanel>
      )
    case 'CONFIRMED':
      return (
        <ParticipationStatusPanel
          eyebrow="Gotowe"
          iconSrc="/icons/icons8-today-64.png"
          title="Udział potwierdzony"
          tone="confirmed"
        >
          {activity.checkin_opens_at !== null &&
            activity.checkin_closes_at !== null && (
              <p className="activity-participant-actions__status-detail">
                Check-in: {formatDateTime(activity.checkin_opens_at)} –{' '}
                {formatDateTime(activity.checkin_closes_at)}
              </p>
            )}
        </ParticipationStatusPanel>
      )
    case 'CHECKED_IN':
      return (
        <ParticipationStatusPanel
          eyebrow="Status check-inu"
          iconSrc="/icons/icons8-navigation-64.png"
          title="Check-in wykonany"
          tone="confirmed"
        />
      )
    case 'COMPLETED':
      return (
        <ParticipationStatusPanel
          eyebrow="Zakończone"
          iconSrc="/icons/icons8-finish-64.png"
          title="Aktywność ukończona"
          tone="complete"
        />
      )
    case 'NO_SHOW':
      return (
        <ParticipationStatusPanel
          eyebrow="Status uczestnictwa"
          iconSrc="/icons/icons8-schedule-64.png"
          title="Nieobecność"
          tone="warning"
        />
      )
    case 'CONFIRMATION_EXPIRED':
      return (
        <ParticipationStatusPanel
          eyebrow="Minął termin"
          iconSrc="/icons/icons8-schedule-64.png"
          title="Rezerwacja miejsca wygasła"
          tone="warning"
        >
          <p className="activity-participant-actions__status-detail">
            Udział nie został potwierdzony w wymaganym czasie.
          </p>
        </ParticipationStatusPanel>
      )
    case 'WAITLIST_EXPIRED':
      return (
        <ParticipationStatusPanel
          eyebrow="Lista zamknięta"
          iconSrc="/icons/icons8-list-64.png"
          title="Oczekiwanie zakończone"
          tone="warning"
        />
      )
  }
}

function ActivityParticipantActions({
  activity,
}: ActivityParticipantActionsProps) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()
  const [isLeaveDialogOpen, setIsLeaveDialogOpen] = useState(false)
  const [checkInErrorMessage, setCheckInErrorMessage] = useState<string | null>(
    null,
  )
  const [joinSuccessMessage, setJoinSuccessMessage] = useState<string | null>(
    null,
  )
  const [isJoinConfettiVisible, setIsJoinConfettiVisible] = useState(false)
  const participantActionLockRef = useRef(false)
  const viewportSize = useViewportSize()
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
  const participationStatus = participation?.status ?? null
  const previousActivityIdRef = useRef(activity.id)
  const previousParticipationStatusRef = useRef(participationStatus)
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
  const joinErrorMessage = joinMutation.isError
    ? getActivityParticipantActionErrorMessage(joinMutation.error)
    : null
  const confirmErrorMessage = confirmMutation.isError
    ? getConfirmActivityErrorMessage(confirmMutation.error)
    : null
  const leaveErrorMessage = leaveMutation.isError
    ? getActivityParticipantActionErrorMessage(leaveMutation.error)
    : null

  useEffect(() => {
    const activityChanged = previousActivityIdRef.current !== activity.id
    const participationStatusChanged =
      previousParticipationStatusRef.current !== participationStatus
    const previousParticipationStatus = previousParticipationStatusRef.current

    previousActivityIdRef.current = activity.id
    previousParticipationStatusRef.current = participationStatus

    if (activityChanged) {
      participantActionLockRef.current = false
      joinMutation.reset()
      leaveMutation.reset()
      confirmMutation.reset()
      checkInMutation.reset()
      setIsLeaveDialogOpen(false)
      setCheckInErrorMessage(null)
      setJoinSuccessMessage(null)
      setIsJoinConfettiVisible(false)
      resetGeolocationError()
      return
    }

    if (!participationStatusChanged) {
      return
    }

    if (participationStatus !== null) {
      joinMutation.reset()
    }

    if (previousParticipationStatus !== null && participationStatus === null) {
      leaveMutation.reset()
      setIsLeaveDialogOpen(false)
    }

    if (
      previousParticipationStatus === 'JOINED' &&
      participationStatus !== 'JOINED'
    ) {
      confirmMutation.reset()
    }

    if (
      previousParticipationStatus === 'CONFIRMED' &&
      participationStatus !== 'CONFIRMED'
    ) {
      checkInMutation.reset()
      setCheckInErrorMessage(null)
    }
  }, [
    activity.id,
    checkInMutation,
    confirmMutation,
    joinMutation,
    leaveMutation,
    participationStatus,
    resetGeolocationError,
  ])

  useEffect(() => {
    if (joinSuccessMessage === null) {
      return
    }

    const timeoutId = window.setTimeout(() => {
      setJoinSuccessMessage(null)
      setIsJoinConfettiVisible(false)
    }, JOIN_SUCCESS_MESSAGE_DURATION_MS)

    return () => window.clearTimeout(timeoutId)
  }, [joinSuccessMessage])

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
      onSuccess: (updatedActivity) => {
        const joinedWaitlist =
          updatedActivity.current_user_participation?.status === 'WAITLISTED'

        setJoinSuccessMessage(
          joinedWaitlist
            ? 'Zapisaliśmy Cię na listę rezerwową.'
            : 'Udało się! Dołączyłeś do aktywności.',
        )

        if (
          !joinedWaitlist &&
          !window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ) {
          setIsJoinConfettiVisible(true)
        }
      },
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
      onSuccess: () => {
        setIsLeaveDialogOpen(false)
        setJoinSuccessMessage(null)
        setIsJoinConfettiVisible(false)
      },
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

  const availability = getActivityAvailability(activity)
  const isJoiningWaitlist = availability.state === 'waitlist'
  const joinLabel = availability.joinLabel
  const shouldHighlightJoinAction = canJoin || canPromptLogin

  return (
    <>
      {isJoinConfettiVisible && viewportSize.width > 0 && (
        <ReactConfetti
          className="activity-participant-actions__confetti"
          width={viewportSize.width}
          height={viewportSize.height}
          colors={CONFETTI_COLORS}
          numberOfPieces={180}
          gravity={0.18}
          initialVelocityY={18}
          recycle={false}
          tweenDuration={1400}
          onConfettiComplete={() => setIsJoinConfettiVisible(false)}
        />
      )}

      <Card
        component="section"
        variant="outlined"
        className={`activity-participant-actions${shouldHighlightJoinAction ? ' activity-participant-actions--joinable' : ''}`}
      >
        <CardContent className="activity-participant-actions__content">
          {participation !== null ? (
            <ParticipationStatus
              activity={activity}
              participation={participation}
            />
          ) : (
            <ParticipationStatusPanel
              eyebrow={isJoiningWaitlist ? 'Lista rezerwowa' : 'Wolne miejsce'}
              iconSrc="/icons/icons8-add-64.png"
              title={joinLabel}
              tone="active"
            >
              <p className="activity-participant-actions__status-detail">
                {isJoiningWaitlist
                  ? 'Aktywność jest pełna, ale możesz zapisać się na listę rezerwową.'
                  : availability.primaryMessage}
              </p>
            </ParticipationStatusPanel>
          )}

          {joinSuccessMessage !== null && (
            <div
              className="activity-participant-actions__success-message"
              role="status"
            >
              <img
                src="/icons/icons8-confetti-64.png"
                alt=""
                width="64"
                height="64"
                aria-hidden="true"
              />
              <div>
                <strong>Gotowe!</strong>
                <span>{joinSuccessMessage}</span>
              </div>
            </div>
          )}

          {joinErrorMessage !== null && (
            <Alert severity="error">{joinErrorMessage}</Alert>
          )}

          {confirmErrorMessage !== null && (
            <Alert severity="error">{confirmErrorMessage}</Alert>
          )}

          {geolocationErrorMessage && (
            <Alert severity="error">{geolocationErrorMessage}</Alert>
          )}

          {checkInErrorMessage && (
            <Alert severity="error">{checkInErrorMessage}</Alert>
          )}

          {canCheckIn && (
            <p className="activity-participant-actions__location-note">
              Check-in wykorzysta jednorazowo lokalizację urządzenia, aby
              zweryfikować lokalizację dla check-inu.
            </p>
          )}

          <div className="activity-participant-actions__buttons">
            {canPromptLogin && (
              <Button
                className="activity-participant-actions__button activity-participant-actions__button--primary"
                component={Link}
                to="/login"
                state={{ from: location }}
                variant="contained"
                startIcon={
                  <img
                    className="activity-participant-actions__button-icon"
                    src="/icons/icons8-avatar-64.png"
                    alt=""
                    width="64"
                    height="64"
                    aria-hidden="true"
                  />
                }
              >
                Zaloguj się, aby dołączyć
              </Button>
            )}

            {canJoin && (
              <Button
                className="activity-participant-actions__button activity-participant-actions__button--primary"
                variant="contained"
                disabled={isParticipantActionPending}
                onClick={handleJoin}
                startIcon={
                  <img
                    className="activity-participant-actions__button-icon"
                    src="/icons/icons8-add-64.png"
                    alt=""
                    width="64"
                    height="64"
                    aria-hidden="true"
                  />
                }
              >
                {joinMutation.isPending ? 'Dołączanie...' : joinLabel}
              </Button>
            )}

            {canConfirm && (
              <Button
                className="activity-participant-actions__button activity-participant-actions__button--confirm"
                variant="contained"
                disabled={isParticipantActionPending}
                onClick={handleConfirm}
                startIcon={
                  <img
                    className="activity-participant-actions__button-icon"
                    src="/icons/icons8-today-64.png"
                    alt=""
                    width="64"
                    height="64"
                    aria-hidden="true"
                  />
                }
              >
                {confirmMutation.isPending
                  ? 'Potwierdzanie...'
                  : 'Potwierdź udział'}
              </Button>
            )}

            {canCheckIn && (
              <Button
                className="activity-participant-actions__button activity-participant-actions__button--check-in"
                variant="contained"
                disabled={isParticipantActionPending}
                onClick={() => void handleCheckIn()}
                startIcon={
                  <img
                    className="activity-participant-actions__button-icon"
                    src="/icons/icons8-navigation-64.png"
                    alt=""
                    width="64"
                    height="64"
                    aria-hidden="true"
                  />
                }
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
                className="activity-participant-actions__button activity-participant-actions__button--leave"
                color="error"
                variant="outlined"
                disabled={isParticipantActionPending}
                onClick={openLeaveDialog}
                startIcon={
                  <img
                    className="activity-participant-actions__button-icon"
                    src="/icons/icons8-back-64.png"
                    alt=""
                    width="64"
                    height="64"
                    aria-hidden="true"
                  />
                }
              >
                {isWaitlisted ? 'Opuść listę rezerwową' : 'Zrezygnuj'}
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
        slotProps={{
          paper: {
            className: 'activity-participant-actions__dialog-paper',
          },
        }}
      >
        <DialogTitle className="activity-participant-actions__dialog-title">
          {isWaitlisted ? 'Opuścić listę rezerwową?' : 'Zrezygnować z udziału?'}
        </DialogTitle>
        <DialogContent>
          {!isWaitlisted && (
            <DialogContentText className="activity-participant-actions__dialog-description">
              Twoje miejsce może zostać przekazane kolejnej osobie.
            </DialogContentText>
          )}
          {leaveErrorMessage !== null && (
            <Alert
              className="activity-participant-actions__dialog-error"
              severity="error"
            >
              {leaveErrorMessage}
            </Alert>
          )}
        </DialogContent>
        <DialogActions className="activity-participant-actions__dialog-actions">
          <Button
            className="activity-participant-actions__dialog-button activity-participant-actions__dialog-button--back"
            disabled={isParticipantActionPending}
            onClick={closeLeaveDialog}
          >
            Wróć
          </Button>
          <Button
            className="activity-participant-actions__dialog-button activity-participant-actions__dialog-button--leave"
            color="error"
            variant="contained"
            disabled={isParticipantActionPending}
            onClick={confirmLeave}
          >
            {leaveMutation.isPending
              ? 'Zapisywanie...'
              : isWaitlisted
                ? 'Opuść listę rezerwową'
                : 'Zrezygnuj'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

export default ActivityParticipantActions
