import { useRef } from 'react'
import axios from 'axios'
import { Alert, Button, Typography } from '@mui/material'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ActivityForm from '../../components/activities/create/ActivityForm/ActivityForm'
import BackButton from '../../components/navigation/BackButton/BackButton'
import UserAvatar from '../../components/UserAvatar/UserAvatar'
import { useUpdateActivityMutation } from '../../hooks/mutations/useUpdateActivityMutation'
import { useActivityCategoriesQuery } from '../../hooks/queries/useActivityCategoriesQuery'
import { useActivityDetailsQuery } from '../../hooks/queries/useActivityDetailsQuery'
import type {
  ActivityDetails,
  UpdateActivityPayload,
} from '../../types/activity'
import type { ActivityFormValues } from '../../types/activityForm'
import { getUpdateActivityErrorMessage } from '../../utils/updateActivityError'
import './EditActivityPage.css'

function mapActivityToFormValues(
  activity: ActivityDetails,
): ActivityFormValues {
  return {
    title: activity.title,
    description: activity.description,
    category_id: activity.category.id,
    start_at: activity.start_at,
    end_at: activity.end_at,
    location_name: activity.location_name,
    address: activity.address,
    latitude: activity.latitude,
    longitude: activity.longitude,
    min_participants: activity.min_participants,
    has_participant_limit: activity.max_participants !== null,
    max_participants: activity.max_participants,
    price_type: activity.price_type,
    price_amount: activity.price_amount,
  }
}

function getActivityLoadErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return 'Nie udało się połączyć z serwerem. Spróbuj ponownie.'
    }

    if (error.response.status === 401) {
      return 'Sesja wygasła lub jest nieprawidłowa.'
    }

    if (error.response.status === 404) {
      return 'Ta aktywność nie istnieje.'
    }
  }

  return 'Nie udało się pobrać danych aktywności.'
}

function EditPermissionDenied({ activity }: { activity: ActivityDetails }) {
  return (
    <section
      className="edit-access-denied"
      aria-labelledby="edit-access-denied-title"
    >
      <div className="edit-access-denied__visual" aria-hidden="true">
        <img src="/denied.gif" alt="" width="480" height="270" />
        <span className="edit-access-denied__code">403</span>
      </div>

      <div className="edit-access-denied__content">
        <p className="edit-access-denied__eyebrow">Dostęp zablokowany</p>
        <h1 id="edit-access-denied-title" className="edit-access-denied__title">
          Nie możesz edytować tej aktywności
        </h1>
        <p className="edit-access-denied__message">
          Zmiany może wprowadzać wyłącznie osoba, która utworzyła aktywność.
        </p>

        <div className="edit-access-denied__organizer">
          <UserAvatar
            className="edit-access-denied__organizer-avatar"
            avatarUrl={activity.organizer.avatar_url}
            displayName={activity.organizer.display_name}
          />
          <span className="edit-access-denied__organizer-copy">
            <span>Organizator aktywności</span>
            <strong>{activity.organizer.display_name}</strong>
          </span>
        </div>

        <p className="edit-access-denied__hint">
          Jeśli coś wymaga zmiany, skontaktuj się bezpośrednio z organizatorem.
        </p>

        <Button
          className="edit-access-denied__browse-button"
          component={Link}
          to="/"
          startIcon={
            <img
              src="/icons/icons8-list-64.png"
              alt=""
              width="64"
              height="64"
              aria-hidden="true"
            />
          }
        >
          Zobacz inne aktywności
        </Button>
      </div>
    </section>
  )
}

function EditActivityPage() {
  const { activityId = '' } = useParams()
  const activityQuery = useActivityDetailsQuery(activityId)
  const canEditActivity = activityQuery.data?.permissions.can_edit === true
  const categoriesQuery = useActivityCategoriesQuery(canEditActivity)
  const updateMutation = useUpdateActivityMutation()
  const navigate = useNavigate()
  const isUpdatingRef = useRef(false)
  const activityPath = activityId ? `/activities/${activityId}` : '/'
  const isLoading =
    activityId !== '' &&
    (activityQuery.isPending || (canEditActivity && categoriesQuery.isPending))
  const hasLoadError =
    activityQuery.isError || (canEditActivity && categoriesQuery.isError)

  async function handleUpdate(values: ActivityFormValues) {
    if (
      activityId === '' ||
      values.latitude === null ||
      values.longitude === null ||
      isUpdatingRef.current
    ) {
      return
    }

    const payload: UpdateActivityPayload = {
      title: values.title,
      description: values.description,
      category_id: values.category_id,
      start_at: values.start_at,
      end_at: values.end_at,
      location_name: values.location_name,
      address: values.address,
      latitude: values.latitude,
      longitude: values.longitude,
      min_participants: values.min_participants,
      has_participant_limit: values.has_participant_limit,
      max_participants: values.max_participants,
      price_type: values.price_type,
      price_amount: values.price_amount,
    }

    isUpdatingRef.current = true

    try {
      const updatedActivity = await updateMutation.mutateAsync({
        activityId,
        payload,
      })
      navigate(`/activities/${updatedActivity.id}`)
    } catch {
      return
    } finally {
      isUpdatingRef.current = false
    }
  }

  if (activityQuery.isSuccess && !canEditActivity) {
    return (
      <main className="edit-activity-page edit-activity-page--denied">
        <BackButton
          className="edit-activity-page__denied-back"
          to={activityPath}
        >
          Wróć do szczegółów
        </BackButton>
        <EditPermissionDenied activity={activityQuery.data} />
      </main>
    )
  }

  return (
    <main className="edit-activity-page">
      <div className="edit-activity-page__heading">
        <div>
          <Typography component="h1" variant="h4">
            Edytuj aktywność
          </Typography>
          <Typography color="text.secondary">
            Zaktualizuj informacje o swojej aktywności.
          </Typography>
        </div>

        <BackButton to={activityPath} />
      </div>

      {activityId === '' && (
        <Alert severity="error">Ta aktywność nie istnieje.</Alert>
      )}

      {isLoading && (
        <Alert severity="info">Ładowanie danych aktywności...</Alert>
      )}

      {hasLoadError && (
        <Alert
          action={
            <Button
              color="inherit"
              disabled={activityQuery.isFetching || categoriesQuery.isFetching}
              size="small"
              onClick={() => {
                void Promise.all([
                  activityQuery.refetch(),
                  categoriesQuery.refetch(),
                ])
              }}
            >
              {activityQuery.isFetching || categoriesQuery.isFetching
                ? 'Ponawianie...'
                : 'Spróbuj ponownie'}
            </Button>
          }
          severity="error"
        >
          {activityQuery.isError
            ? getActivityLoadErrorMessage(activityQuery.error)
            : 'Nie udało się pobrać kategorii.'}
        </Alert>
      )}

      {updateMutation.isError &&
        updateMutation.variables?.activityId === activityId && (
          <Alert severity="error">
            {getUpdateActivityErrorMessage(updateMutation.error)}
          </Alert>
        )}

      {activityQuery.isSuccess &&
        categoriesQuery.isSuccess &&
        canEditActivity && (
          <ActivityForm
            key={activityQuery.data.id}
            categories={categoriesQuery.data}
            initialValues={mapActivityToFormValues(activityQuery.data)}
            disabled={updateMutation.isPending}
            submitLabel="Zapisz zmiany"
            submittingLabel="Zapisywanie..."
            onSubmit={handleUpdate}
          />
        )}
    </main>
  )
}

export default EditActivityPage
