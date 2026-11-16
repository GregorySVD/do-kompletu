import { DeleteForeverOutlined, PhotoCameraOutlined } from '@mui/icons-material'
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
  TextField,
  Typography,
} from '@mui/material'
import { type FormEvent, useEffect, useState } from 'react'
import { useDeleteActivityPhotoMutation } from '../../../hooks/mutations/useDeleteActivityPhotoMutation'
import {
  getAdminErrorMessage,
  getAdminErrorStatus,
} from '../../../utils/adminError'

interface AdminPhotoModerationSectionProps {
  onForbidden: () => void
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function AdminPhotoModerationSection({
  onForbidden,
}: AdminPhotoModerationSectionProps) {
  const [activityId, setActivityId] = useState('')
  const [photoId, setPhotoId] = useState('')
  const [activityIdError, setActivityIdError] = useState<string | null>(null)
  const [photoIdError, setPhotoIdError] = useState<string | null>(null)
  const [isConfirmationOpen, setIsConfirmationOpen] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const deleteMutation = useDeleteActivityPhotoMutation()

  useEffect(() => {
    if (getAdminErrorStatus(deleteMutation.error) === 403) {
      onForbidden()
    }
  }, [deleteMutation.error, onForbidden])

  function requestDeletion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (deleteMutation.isPending) {
      return
    }

    const normalizedActivityId = activityId.trim()
    const normalizedPhotoId = photoId.trim()
    const nextActivityError = uuidPattern.test(normalizedActivityId)
      ? null
      : 'Wpisz prawidłowy UUID aktywności.'
    const nextPhotoError = uuidPattern.test(normalizedPhotoId)
      ? null
      : 'Wpisz prawidłowy UUID zdjęcia.'

    setActivityIdError(nextActivityError)
    setPhotoIdError(nextPhotoError)
    setShowSuccess(false)
    deleteMutation.reset()

    if (nextActivityError || nextPhotoError) {
      return
    }

    setActivityId(normalizedActivityId)
    setPhotoId(normalizedPhotoId)
    setIsConfirmationOpen(true)
  }

  function closeConfirmationDialog() {
    if (!deleteMutation.isPending) {
      setIsConfirmationOpen(false)
    }
  }

  function confirmDeletion() {
    if (deleteMutation.isPending) {
      return
    }

    deleteMutation.mutate(
      { activityId, photoId },
      {
        onSuccess: () => {
          setIsConfirmationOpen(false)
          setPhotoId('')
          setShowSuccess(true)
        },
      },
    )
  }

  return (
    <Card
      component="section"
      variant="outlined"
      className="admin-section admin-section--photos"
      aria-labelledby="admin-photos-title"
    >
      <CardContent className="admin-section__content">
        <header className="admin-section__heading">
          <span className="admin-section__icon" aria-hidden="true">
            <PhotoCameraOutlined />
          </span>
          <div>
            <span className="admin-section__eyebrow">MEDIA // 03</span>
            <Typography id="admin-photos-title" component="h2" variant="h4">
              Moderacja zdjęć
            </Typography>
            <Typography color="text.secondary">
              Usuń wskazane zdjęcie bez przeglądania prywatnej galerii.
            </Typography>
          </div>
        </header>

        <Alert severity="info">
          Identyfikatory muszą pochodzić z autoryzowanej odpowiedzi galerii albo
          z zaufanego zgłoszenia moderacyjnego. Panel nie wyszukuje zdjęć.
        </Alert>

        {showSuccess && (
          <Alert severity="success" role="status">
            Zdjęcie zostało usunięte.
          </Alert>
        )}

        <form className="admin-photo-form" onSubmit={requestDeletion}>
          <TextField
            fullWidth
            className="admin-photo-form__field"
            error={activityIdError !== null}
            helperText={
              activityIdError ?? 'UUID aktywności powiązanej ze zdjęciem'
            }
            label="UUID aktywności"
            value={activityId}
            autoComplete="off"
            onChange={(event) => {
              setActivityId(event.target.value)
              setActivityIdError(null)
              setShowSuccess(false)
            }}
          />
          <TextField
            fullWidth
            className="admin-photo-form__field"
            error={photoIdError !== null}
            helperText={
              photoIdError ?? 'UUID zdjęcia przeznaczonego do usunięcia'
            }
            label="UUID zdjęcia"
            value={photoId}
            autoComplete="off"
            onChange={(event) => {
              setPhotoId(event.target.value)
              setPhotoIdError(null)
              setShowSuccess(false)
            }}
          />
          <Button
            className="admin-photo-form__submit"
            color="error"
            disabled={deleteMutation.isPending}
            startIcon={<DeleteForeverOutlined aria-hidden="true" />}
            type="submit"
            variant="outlined"
          >
            Usuń zdjęcie po identyfikatorach
          </Button>
        </form>
      </CardContent>

      <Dialog
        fullWidth
        maxWidth="sm"
        open={isConfirmationOpen}
        aria-describedby="admin-photo-delete-description"
        aria-labelledby="admin-photo-delete-title"
        onClose={closeConfirmationDialog}
      >
        <DialogTitle id="admin-photo-delete-title">
          Usunąć wskazane zdjęcie?
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="admin-photo-delete-description">
            Operacja jest nieodwracalna. Backend sprawdzi, czy zdjęcie należy do
            podanej aktywności.
          </DialogContentText>
          <dl className="admin-dialog__identifiers">
            <div>
              <dt>Aktywność</dt>
              <dd>{activityId}</dd>
            </div>
            <div>
              <dt>Zdjęcie</dt>
              <dd>{photoId}</dd>
            </div>
          </dl>
          {deleteMutation.isError && (
            <Alert className="admin-dialog__error" severity="error">
              {getAdminErrorMessage(deleteMutation.error, 'delete-photo')}
            </Alert>
          )}
        </DialogContent>
        <DialogActions className="admin-dialog__actions">
          <Button
            disabled={deleteMutation.isPending}
            onClick={closeConfirmationDialog}
          >
            Wróć
          </Button>
          <Button
            color="error"
            disabled={deleteMutation.isPending}
            startIcon={
              deleteMutation.isPending ? (
                <CircularProgress aria-hidden="true" size="1rem" />
              ) : (
                <DeleteForeverOutlined aria-hidden="true" />
              )
            }
            variant="contained"
            onClick={confirmDeletion}
          >
            {deleteMutation.isPending ? 'Usuwanie...' : 'Usuń trwale'}
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  )
}

export default AdminPhotoModerationSection
