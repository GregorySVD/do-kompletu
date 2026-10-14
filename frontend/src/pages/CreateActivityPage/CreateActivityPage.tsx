import { useRef } from 'react'
import axios from 'axios'
import { Alert, Button, Typography } from '@mui/material'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import CreateActivityForm from '../../components/activities/create/CreateActivityForm/CreateActivityForm'
import { useCreateActivityMutation } from '../../hooks/mutations/useCreateActivityMutation'
import { activitiesQueryKey } from '../../hooks/queries/useActivitiesQuery'
import { useActivityCategoriesQuery } from '../../hooks/queries/useActivityCategoriesQuery'
import type { CreateActivityPayload } from '../../types/activity'
import type { CreateActivityFormValues } from '../../types/createActivityForm'
import './CreateActivityPage.css'

function getCreateActivityErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return 'Nie udało się połączyć z serwerem. Spróbuj ponownie.'
    }

    if (error.response.status === 401) {
      return 'Sesja wygasła lub jest nieprawidłowa. Zaloguj się ponownie.'
    }

    if (error.response.status === 422) {
      return 'Nie udało się utworzyć aktywności. Sprawdź poprawność danych.'
    }
  }

  return 'Nie udało się utworzyć aktywności. Spróbuj ponownie.'
}

function CreateActivityPage() {
  const categoriesQuery = useActivityCategoriesQuery()
  const createMutation = useCreateActivityMutation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const isCreatingRef = useRef(false)

  async function handleCreate(values: CreateActivityFormValues) {
    if (
      values.latitude === null ||
      values.longitude === null ||
      isCreatingRef.current
    ) {
      return
    }

    const payload: CreateActivityPayload = {
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

    isCreatingRef.current = true

    try {
      const createdActivity = await createMutation.mutateAsync(payload)

      await queryClient.invalidateQueries({ queryKey: activitiesQueryKey })
      navigate(`/activities/${createdActivity.id}`)
    } catch {
      return
    } finally {
      isCreatingRef.current = false
    }
  }

  return (
    <main className="create-activity-page">
      <div className="create-activity-page__heading">
        <div>
          <Typography component="h1" variant="h4">
            Dodaj aktywność
          </Typography>
          <Typography color="text.secondary">
            Uzupełnij podstawowe informacje o planowanej aktywności.
          </Typography>
        </div>

        <Button component={Link} to="/">
          Wróć do listy
        </Button>
      </div>

      {categoriesQuery.isPending && (
        <Alert severity="info">Ładowanie kategorii...</Alert>
      )}

      {categoriesQuery.isError && (
        <Alert
          action={
            <Button
              color="inherit"
              disabled={categoriesQuery.isFetching}
              size="small"
              onClick={() => {
                void categoriesQuery.refetch()
              }}
            >
              {categoriesQuery.isFetching
                ? 'Ponawianie...'
                : 'Spróbuj ponownie'}
            </Button>
          }
          severity="error"
        >
          Nie udało się pobrać kategorii.
        </Alert>
      )}

      {createMutation.isError && (
        <Alert severity="error">
          {getCreateActivityErrorMessage(createMutation.error)}
        </Alert>
      )}

      {categoriesQuery.isSuccess && (
        <CreateActivityForm
          categories={categoriesQuery.data}
          disabled={createMutation.isPending}
          onSubmit={handleCreate}
        />
      )}
    </main>
  )
}

export default CreateActivityPage
