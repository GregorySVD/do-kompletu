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
import { useCancelActivityMutation } from '../../../../hooks/mutations/useCancelActivityMutation'
import { useFinalizeActivityMutation } from '../../../../hooks/mutations/useFinalizeActivityMutation'
import type { ActivityDetails } from '../../../../types/activity'
import { getActivityOrganizerActionErrorMessage } from '../../../../utils/activityOrganizerActionError'
import './ActivityOrganizerActions.css'

type OrganizerAction = 'cancel' | 'finalize'

interface ActivityOrganizerActionsProps {
  activity: ActivityDetails
}

const dialogContent = {
  cancel: {
    title: 'Anulować aktywność?',
    description:
      'Aktywność przestanie być widoczna w głównym odkrywaniu, ale pozostanie w historii.',
    confirmLabel: 'Anuluj aktywność',
    pendingLabel: 'Anulowanie...',
  },
  finalize: {
    title: 'Finalizować aktywność?',
    description:
      'Finalizacja zapisze końcowe wyniki uczestnictwa. Osoby z check-inem otrzymają status ukończenia, a pozostałe nierozliczone uczestnictwa zostaną oznaczone jako nieobecność.',
    confirmLabel: 'Finalizuj',
    pendingLabel: 'Finalizowanie...',
  },
} as const

function ActivityOrganizerActions({ activity }: ActivityOrganizerActionsProps) {
  const [openAction, setOpenAction] = useState<OrganizerAction | null>(null)
  const cancelMutation = useCancelActivityMutation()
  const finalizeMutation = useFinalizeActivityMutation()
  const activeMutation =
    openAction === 'cancel' ? cancelMutation : finalizeMutation
  const isPending = cancelMutation.isPending || finalizeMutation.isPending
  const error = cancelMutation.error ?? finalizeMutation.error
  const successMessage = cancelMutation.isSuccess
    ? 'Aktywność została anulowana.'
    : finalizeMutation.isSuccess
      ? 'Aktywność została sfinalizowana.'
      : null

  function openDialog(action: OrganizerAction) {
    cancelMutation.reset()
    finalizeMutation.reset()
    setOpenAction(action)
  }

  function closeDialog() {
    if (!isPending) {
      setOpenAction(null)
    }
  }

  function confirmAction() {
    if (openAction === null || isPending) {
      return
    }

    activeMutation.mutate(activity.id, {
      onSuccess: () => setOpenAction(null),
    })
  }

  if (
    !activity.permissions.can_edit &&
    !activity.permissions.can_cancel &&
    !activity.permissions.can_finalize &&
    !successMessage &&
    openAction === null
  ) {
    return null
  }

  const currentDialog = openAction ? dialogContent[openAction] : null

  return (
    <>
      <Card
        component="section"
        variant="outlined"
        className="activity-organizer-actions"
      >
        <CardContent className="activity-organizer-actions__content">
          <div className="activity-organizer-actions__heading">
            <Typography
              className="activity-organizer-actions__title"
              component="h2"
              variant="h6"
            >
              Zarządzanie aktywnością
            </Typography>
            <Typography
              className="activity-organizer-actions__subtitle"
              color="text.secondary"
            >
              Akcje dostępne dla organizatora.
            </Typography>
          </div>

          {successMessage && <Alert severity="success">{successMessage}</Alert>}

          <div className="activity-organizer-actions__buttons">
            {activity.permissions.can_edit && (
              <Button
                className="activity-organizer-actions__button activity-organizer-actions__button--edit"
                component={Link}
                to={`/activities/${activity.id}/edit`}
                variant="outlined"
                disabled={isPending}
                startIcon={
                  <img
                    className="activity-organizer-actions__button-icon"
                    src="/icons/icons8-edit-64.png"
                    alt=""
                    width="64"
                    height="64"
                    aria-hidden="true"
                  />
                }
              >
                Edytuj aktywność
              </Button>
            )}

            {activity.permissions.can_finalize && (
              <Button
                className="activity-organizer-actions__button activity-organizer-actions__button--finalize"
                variant="contained"
                disabled={isPending}
                onClick={() => openDialog('finalize')}
              >
                Finalizuj aktywność
              </Button>
            )}

            {activity.permissions.can_cancel && (
              <Button
                className="activity-organizer-actions__button activity-organizer-actions__button--cancel"
                color="error"
                variant="outlined"
                disabled={isPending}
                onClick={() => openDialog('cancel')}
                startIcon={
                  <img
                    className="activity-organizer-actions__button-icon"
                    src="/icons/icons8-trash-64.png"
                    alt=""
                    width="64"
                    height="64"
                    aria-hidden="true"
                  />
                }
              >
                Anuluj aktywność
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Dialog
        fullWidth
        maxWidth="sm"
        open={openAction !== null}
        onClose={closeDialog}
      >
        {currentDialog && (
          <>
            <DialogTitle>{currentDialog.title}</DialogTitle>
            <DialogContent>
              <DialogContentText>{currentDialog.description}</DialogContentText>
              {error && (
                <Alert
                  className="activity-organizer-actions__dialog-error"
                  severity="error"
                >
                  {getActivityOrganizerActionErrorMessage(error)}
                </Alert>
              )}
            </DialogContent>
            <DialogActions className="activity-organizer-actions__dialog-actions">
              <Button disabled={isPending} onClick={closeDialog}>
                Wróć
              </Button>
              <Button
                color={openAction === 'cancel' ? 'error' : 'primary'}
                variant="contained"
                disabled={isPending}
                onClick={confirmAction}
              >
                {isPending
                  ? currentDialog.pendingLabel
                  : currentDialog.confirmLabel}
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </>
  )
}

export default ActivityOrganizerActions
