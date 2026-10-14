import { Alert, Button, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import CreateActivityForm from '../../components/activities/create/CreateActivityForm/CreateActivityForm'
import { useActivityCategoriesQuery } from '../../hooks/queries/useActivityCategoriesQuery'
import './CreateActivityPage.css'

function CreateActivityPage() {
  const categoriesQuery = useActivityCategoriesQuery()

  function handleCreate() {
    // Intentionally left ready for the create-activity mutation.
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

      {categoriesQuery.isSuccess && (
        <CreateActivityForm
          categories={categoriesQuery.data}
          onSubmit={handleCreate}
        />
      )}
    </main>
  )
}

export default CreateActivityPage
