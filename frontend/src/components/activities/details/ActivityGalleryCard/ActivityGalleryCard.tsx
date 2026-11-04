import {
  AddPhotoAlternateOutlined,
  DeleteOutlined,
  PhotoLibraryOutlined,
  Refresh,
} from '@mui/icons-material'
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
  Skeleton,
  Typography,
} from '@mui/material'
import { useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { useEffect, useState, type ChangeEvent } from 'react'
import { useAuth } from '../../../../context/auth'
import { useDeleteActivityPhotoMutation } from '../../../../hooks/mutations/useDeleteActivityPhotoMutation'
import { useUploadActivityPhotoMutation } from '../../../../hooks/mutations/useUploadActivityPhotoMutation'
import { getActivityDetailsQueryKey } from '../../../../hooks/queries/useActivityDetailsQuery'
import {
  getActivityPhotosQueryKey,
  useActivityPhotosQuery,
} from '../../../../hooks/queries/useActivityPhotosQuery'
import type { ActivityDetails, ActivityPhoto } from '../../../../types/activity'
import {
  getActivityGalleryErrorMessage,
  getActivityGalleryErrorStatus,
} from '../../../../utils/activityGalleryError'
import UserAvatar from '../../../UserAvatar/UserAvatar'
import './ActivityGalleryCard.css'

interface ActivityGalleryCardProps {
  activity: ActivityDetails
}

interface GalleryPhotoProps {
  activityTitle: string
  canDelete: boolean
  isRefreshing: boolean
  onDelete: (photo: ActivityPhoto) => void
  onRefresh: () => void
  photo: ActivityPhoto
}

interface ActivityGalleryContentProps {
  activity: ActivityDetails
  userId: string
}

const allowedPhotoTypes = new Set(['image/jpeg', 'image/png', 'image/webp'])
const maximumPhotoSizeBytes = 10_485_760
const maximumOwnPhotoCount = 3
const galleryLifetimeHours = 72
const maximumTimeoutDelayMs = 2_147_000_000

const photoDateFormatter = new Intl.DateTimeFormat('pl-PL', {
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  month: 'short',
  year: 'numeric',
})

function getSelectedPhotoError(file: File, ownPhotoCount: number) {
  if (ownPhotoCount >= maximumOwnPhotoCount) {
    return 'Możesz dodać maksymalnie 3 zdjęcia do tej aktywności.'
  }

  if (!allowedPhotoTypes.has(file.type)) {
    return 'Wybierz zdjęcie w formacie JPEG, PNG lub WebP.'
  }

  if (file.size > maximumPhotoSizeBytes) {
    return 'Zdjęcie jest za duże. Maksymalny rozmiar to 10 MB.'
  }

  return null
}

function GalleryLoadingSkeleton() {
  return (
    <div
      className="activity-gallery-card__skeleton-grid"
      role="status"
      aria-live="polite"
    >
      <span className="activity-gallery-card__visually-hidden">
        Ładowanie galerii...
      </span>
      {[0, 1, 2].map((placeholderIndex) => (
        <div
          key={placeholderIndex}
          className="activity-gallery-card__skeleton-photo"
          aria-hidden="true"
        >
          <Skeleton
            className="activity-gallery-card__skeleton-image"
            variant="rectangular"
          />
          <div className="activity-gallery-card__skeleton-caption">
            <Skeleton
              className="activity-gallery-card__skeleton-avatar"
              variant="circular"
            />
            <div className="activity-gallery-card__skeleton-copy">
              <Skeleton variant="text" />
              <Skeleton variant="text" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function useGalleryDeadlineReached(activityEndAt: string) {
  const galleryClosesAt = dayjs(activityEndAt)
    .add(galleryLifetimeHours, 'hour')
    .valueOf()
  const [hasReachedDeadline, setHasReachedDeadline] = useState(
    () => Number.isFinite(galleryClosesAt) && Date.now() >= galleryClosesAt,
  )

  useEffect(() => {
    let timeoutId: number | undefined

    function updateDeadlineState() {
      if (!Number.isFinite(galleryClosesAt)) {
        setHasReachedDeadline(false)
        return
      }

      const remainingTime = galleryClosesAt - Date.now()

      if (remainingTime <= 0) {
        setHasReachedDeadline(true)
        return
      }

      setHasReachedDeadline(false)
      timeoutId = window.setTimeout(
        updateDeadlineState,
        Math.min(remainingTime, maximumTimeoutDelayMs),
      )
    }

    timeoutId = window.setTimeout(updateDeadlineState, 0)

    return () => {
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [galleryClosesAt])

  return hasReachedDeadline
}

function GalleryPhoto({
  activityTitle,
  canDelete,
  isRefreshing,
  onDelete,
  onRefresh,
  photo,
}: GalleryPhotoProps) {
  const [hasImageError, setHasImageError] = useState(false)
  const formattedDate = photoDateFormatter.format(new Date(photo.created_at))

  function refreshPhoto() {
    setHasImageError(false)
    onRefresh()
  }

  return (
    <figure className="activity-gallery-card__photo">
      <div className="activity-gallery-card__image-frame">
        {hasImageError ? (
          <div className="activity-gallery-card__image-unavailable">
            <div
              className="activity-gallery-card__image-unavailable-message"
              role="status"
              aria-live="polite"
            >
              <PhotoLibraryOutlined aria-hidden="true" />
              <span>Zdjęcie wygasło lub jest chwilowo niedostępne.</span>
            </div>
            <Button
              className="activity-gallery-card__image-refresh"
              disabled={isRefreshing}
              size="small"
              startIcon={
                isRefreshing ? (
                  <CircularProgress aria-hidden="true" size="0.9rem" />
                ) : (
                  <Refresh aria-hidden="true" />
                )
              }
              variant="outlined"
              onClick={refreshPhoto}
            >
              {isRefreshing ? 'Odświeżanie...' : 'Odśwież galerię'}
            </Button>
          </div>
        ) : (
          <img
            className="activity-gallery-card__image"
            src={photo.url}
            alt={`Zdjęcie z aktywności „${activityTitle}” dodane przez ${photo.uploader.display_name}`}
            loading="lazy"
            decoding="async"
            onError={() => setHasImageError(true)}
          />
        )}
      </div>

      <figcaption className="activity-gallery-card__caption">
        <div className="activity-gallery-card__uploader">
          <UserAvatar
            className="activity-gallery-card__avatar"
            avatarUrl={photo.uploader.avatar_url}
            displayName={photo.uploader.display_name}
          />
          <div className="activity-gallery-card__uploader-copy">
            <strong>{photo.uploader.display_name}</strong>
            <time dateTime={photo.created_at}>{formattedDate}</time>
          </div>
        </div>

        {canDelete && (
          <Button
            className="activity-gallery-card__delete"
            color="error"
            size="small"
            startIcon={<DeleteOutlined aria-hidden="true" />}
            variant="outlined"
            aria-label={`Usuń zdjęcie dodane przez ${photo.uploader.display_name}`}
            onClick={() => onDelete(photo)}
          >
            Usuń
          </Button>
        )}
      </figcaption>
    </figure>
  )
}

function ActivityGalleryContent({
  activity,
  userId,
}: ActivityGalleryContentProps) {
  const queryClient = useQueryClient()
  const canViewGallery = activity.permissions.can_view_gallery
  const canUploadPhoto = activity.permissions.can_upload_photo
  const [hasLostGalleryAccess, setHasLostGalleryAccess] = useState(false)
  const photosQuery = useActivityPhotosQuery(
    activity.id,
    canViewGallery && !hasLostGalleryAccess,
  )
  const uploadMutation = useUploadActivityPhotoMutation()
  const deleteMutation = useDeleteActivityPhotoMutation()
  const [clientUploadError, setClientUploadError] = useState<string | null>(
    null,
  )
  const [photoToDelete, setPhotoToDelete] = useState<ActivityPhoto | null>(null)
  const photos = photosQuery.data ?? []
  const ownPhotoCount = photos.filter(
    (photo) => photo.uploader.id === userId,
  ).length
  const galleryErrorStatus = getActivityGalleryErrorStatus(photosQuery.error)
  const uploadErrorStatus = getActivityGalleryErrorStatus(uploadMutation.error)
  const deleteErrorStatus = getActivityGalleryErrorStatus(deleteMutation.error)
  const uploadError = clientUploadError
    ? clientUploadError
    : uploadMutation.isError
      ? getActivityGalleryErrorMessage(uploadMutation.error, 'upload')
      : null
  const galleryTitleId = `activity-gallery-title-${activity.id}`
  const deleteDialogTitleId = `activity-gallery-delete-title-${activity.id}`
  const deleteDialogDescriptionId = `activity-gallery-delete-description-${activity.id}`
  const isBusy =
    (!hasLostGalleryAccess && photosQuery.isPending) ||
    uploadMutation.isPending ||
    deleteMutation.isPending
  const canSelectPhoto =
    !hasLostGalleryAccess &&
    photosQuery.data !== undefined &&
    ownPhotoCount < maximumOwnPhotoCount &&
    !photosQuery.isFetching &&
    !uploadMutation.isPending
  const canRetryGallery =
    galleryErrorStatus !== 401 &&
    galleryErrorStatus !== 403 &&
    galleryErrorStatus !== 404

  useEffect(() => {
    if (galleryErrorStatus !== 403) {
      return
    }

    const timeoutId = window.setTimeout(() => setHasLostGalleryAccess(true), 0)

    return () => window.clearTimeout(timeoutId)
  }, [galleryErrorStatus])

  useEffect(() => {
    if (!hasLostGalleryAccess) {
      return
    }

    queryClient.removeQueries({
      queryKey: getActivityPhotosQueryKey(activity.id, userId),
      exact: true,
    })
    void queryClient.invalidateQueries({
      queryKey: getActivityDetailsQueryKey(activity.id, userId),
      exact: true,
    })
  }, [activity.id, hasLostGalleryAccess, queryClient, userId])

  useEffect(() => {
    if (uploadErrorStatus !== 403 && deleteErrorStatus !== 403) {
      return
    }

    void queryClient.invalidateQueries({
      queryKey: getActivityDetailsQueryKey(activity.id, userId),
      exact: true,
    })
  }, [activity.id, deleteErrorStatus, queryClient, uploadErrorStatus, userId])

  function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''

    if (!file || uploadMutation.isPending) {
      return
    }

    uploadMutation.reset()
    setClientUploadError(null)

    const validationError = getSelectedPhotoError(file, ownPhotoCount)

    if (validationError) {
      setClientUploadError(validationError)
      return
    }

    uploadMutation.mutate({ activityId: activity.id, file })
  }

  function openDeleteDialog(photo: ActivityPhoto) {
    deleteMutation.reset()
    setPhotoToDelete(photo)
  }

  function closeDeleteDialog() {
    if (!deleteMutation.isPending) {
      setPhotoToDelete(null)
    }
  }

  function confirmPhotoDeletion() {
    if (!photoToDelete || deleteMutation.isPending) {
      return
    }

    deleteMutation.mutate(
      { activityId: activity.id, photoId: photoToDelete.id },
      { onSuccess: () => setPhotoToDelete(null) },
    )
  }

  function refreshGallery() {
    void photosQuery.refetch()
  }

  return (
    <>
      <Card
        component="section"
        variant="outlined"
        className="activity-gallery-card"
        aria-busy={isBusy}
        aria-labelledby={galleryTitleId}
      >
        <CardContent className="activity-gallery-card__content">
          <div className="activity-gallery-card__heading">
            <div className="activity-gallery-card__heading-copy">
              <span className="activity-gallery-card__heading-icon">
                <PhotoLibraryOutlined aria-hidden="true" />
              </span>
              <div>
                <Typography
                  id={galleryTitleId}
                  className="activity-gallery-card__title"
                  component="h2"
                  variant="h5"
                >
                  Galeria aktywności
                </Typography>
                <Typography color="text.secondary">
                  Zdjęcia dodane przez uczestników
                </Typography>
              </div>
            </div>

            {canUploadPhoto && !hasLostGalleryAccess && (
              <div className="activity-gallery-card__upload-controls">
                <Button
                  className="activity-gallery-card__upload-button"
                  component="label"
                  disabled={!canSelectPhoto}
                  startIcon={
                    uploadMutation.isPending ? (
                      <CircularProgress aria-hidden="true" size="1rem" />
                    ) : (
                      <AddPhotoAlternateOutlined aria-hidden="true" />
                    )
                  }
                  variant="contained"
                >
                  {uploadMutation.isPending
                    ? 'Wysyłanie zdjęcia...'
                    : 'Dodaj zdjęcie'}
                  <input
                    className="activity-gallery-card__file-input"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={!canSelectPhoto}
                    onChange={handleFileSelection}
                  />
                </Button>
                <Typography
                  className="activity-gallery-card__quota"
                  color="text.secondary"
                  variant="body2"
                >
                  Twoje zdjęcia: {ownPhotoCount}/{maximumOwnPhotoCount}
                </Typography>
              </div>
            )}
          </div>

          {uploadError && <Alert severity="error">{uploadError}</Alert>}
          {uploadMutation.isSuccess && (
            <Alert severity="success">Zdjęcie zostało dodane.</Alert>
          )}

          {hasLostGalleryAccess ? (
            <Alert severity="error">Galeria nie jest już dostępna.</Alert>
          ) : photosQuery.isPending ? (
            <GalleryLoadingSkeleton />
          ) : photosQuery.isError ? (
            <div className="activity-gallery-card__error">
              <Alert severity="error">
                {getActivityGalleryErrorMessage(photosQuery.error, 'load')}
              </Alert>
              {canRetryGallery && (
                <Button
                  disabled={photosQuery.isFetching}
                  startIcon={
                    photosQuery.isFetching ? (
                      <CircularProgress aria-hidden="true" size="1rem" />
                    ) : (
                      <Refresh aria-hidden="true" />
                    )
                  }
                  variant="outlined"
                  onClick={refreshGallery}
                >
                  {photosQuery.isFetching
                    ? 'Odświeżanie...'
                    : 'Spróbuj ponownie'}
                </Button>
              )}
            </div>
          ) : photos.length === 0 ? (
            <div className="activity-gallery-card__empty" role="status">
              <PhotoLibraryOutlined aria-hidden="true" />
              <Typography component="p">
                W galerii nie ma jeszcze zdjęć.
              </Typography>
            </div>
          ) : (
            <>
              <div className="activity-gallery-card__grid">
                {photos.map((photo) => (
                  <GalleryPhoto
                    key={`${photo.id}:${photosQuery.dataUpdatedAt}`}
                    activityTitle={activity.title}
                    canDelete={photo.uploader.id === userId}
                    isRefreshing={photosQuery.isFetching}
                    photo={photo}
                    onDelete={openDeleteDialog}
                    onRefresh={refreshGallery}
                  />
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Dialog
        fullWidth
        maxWidth="sm"
        open={photoToDelete !== null}
        aria-describedby={deleteDialogDescriptionId}
        aria-labelledby={deleteDialogTitleId}
        onClose={closeDeleteDialog}
      >
        <DialogTitle id={deleteDialogTitleId}>Usunąć zdjęcie?</DialogTitle>
        <DialogContent>
          <DialogContentText id={deleteDialogDescriptionId}>
            Tej operacji nie można cofnąć.
          </DialogContentText>
          {deleteMutation.isError && (
            <Alert
              className="activity-gallery-card__delete-error"
              severity="error"
            >
              {getActivityGalleryErrorMessage(deleteMutation.error, 'delete')}
            </Alert>
          )}
        </DialogContent>
        <DialogActions className="activity-gallery-card__dialog-actions">
          <Button
            disabled={deleteMutation.isPending}
            onClick={closeDeleteDialog}
          >
            Anuluj
          </Button>
          <Button
            color="error"
            disabled={deleteMutation.isPending}
            startIcon={
              deleteMutation.isPending ? (
                <CircularProgress aria-hidden="true" size="1rem" />
              ) : (
                <DeleteOutlined aria-hidden="true" />
              )
            }
            variant="contained"
            onClick={confirmPhotoDeletion}
          >
            {deleteMutation.isPending ? 'Usuwanie...' : 'Usuń zdjęcie'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

function ActivityGalleryCard({ activity }: ActivityGalleryCardProps) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const canViewGallery = activity.permissions.can_view_gallery
  const hasReachedGalleryDeadline = useGalleryDeadlineReached(activity.end_at)
  const canDisplayGallery = canViewGallery && !hasReachedGalleryDeadline

  useEffect(() => {
    if (canDisplayGallery || user === null) {
      return
    }

    queryClient.removeQueries({
      queryKey: getActivityPhotosQueryKey(activity.id, user.id),
      exact: true,
    })

    if (canViewGallery && hasReachedGalleryDeadline) {
      void queryClient.invalidateQueries({
        queryKey: getActivityDetailsQueryKey(activity.id, user.id),
        exact: true,
      })
    }
  }, [
    activity.id,
    canDisplayGallery,
    canViewGallery,
    hasReachedGalleryDeadline,
    queryClient,
    user,
  ])

  if (!canDisplayGallery || user === null) {
    return null
  }

  return (
    <ActivityGalleryContent
      key={activity.id}
      activity={activity}
      userId={user.id}
    />
  )
}

export default ActivityGalleryCard
