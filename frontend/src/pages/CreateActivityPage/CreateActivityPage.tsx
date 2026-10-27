import { useRef } from 'react'
import { Alert, Button, Typography } from '@mui/material'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import ActivityForm from '../../components/activities/create/ActivityForm/ActivityForm'
import BackButton from '../../components/navigation/BackButton/BackButton'
import { useCreateActivityMutation } from '../../hooks/mutations/useCreateActivityMutation'
import { activitiesQueryKey } from '../../hooks/queries/useActivitiesQuery'
import { useActivityCategoriesQuery } from '../../hooks/queries/useActivityCategoriesQuery'
import type { ActivityFormValues } from '../../types/activityForm'
import { mapActivityFormValuesToPayload } from '../../utils/activityFormMappers'
import { getCreateActivityErrorMessage } from '../../utils/createActivityError'
import './CreateActivityPage.css'

function CreateActivityPage() {
  const categoriesQuery = useActivityCategoriesQuery()
  const createMutation = useCreateActivityMutation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const isCreatingRef = useRef(false)

  async function handleCreate(values: ActivityFormValues) {
    const payload = mapActivityFormValuesToPayload(values)

    if (payload === null || isCreatingRef.current) {
      return
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
      <header className="create-activity-page__hero">
        <div className="create-activity-page__hero-icon" aria-hidden="true">
          <img src="/icons/icons8-add-64.png" alt="" width="64" height="64" />
        </div>

        <div className="create-activity-page__hero-copy">
          <span className="create-activity-page__eyebrow">
            Kreator spotkania
          </span>
          <Typography component="h1" className="create-activity-page__title">
            Stwórz nową aktywność
          </Typography>
          <Typography className="create-activity-page__subtitle">
            Opowiedz, co planujesz, ustal najważniejsze szczegóły i zbierz
            ekipę. Podgląd po prawej aktualizuje się na żywo.
          </Typography>
        </div>

        <BackButton className="create-activity-page__back" to="/">
          Wróć do listy
        </BackButton>

        <ol
          className="create-activity-page__steps"
          aria-label="Etapy formularza"
        >
          <li>
            <span>01</span> Podstawy
          </li>
          <li>
            <span>02</span> Termin
          </li>
          <li>
            <span>03</span> Miejsce
          </li>
          <li>
            <span>04</span> Uczestnicy i koszt
          </li>
        </ol>
      </header>

      <div className="create-activity-page__feedback">
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
      </div>

      {categoriesQuery.isSuccess && (
        <ActivityForm
          categories={categoriesQuery.data}
          disabled={createMutation.isPending}
          submitLabel="Utwórz aktywność"
          submittingLabel="Tworzenie..."
          submitIconSrc="/icons/icons8-add-64.png"
          onSubmit={handleCreate}
        />
      )}
    </main>
  )
}

export default CreateActivityPage
