import { ArrowBack } from '@mui/icons-material'
import axios from 'axios'
import { Button, Card, CardContent, Typography } from '@mui/material'
import { Link, useParams } from 'react-router-dom'
import ActivityDetailsContent from '../../components/activities/details/ActivityDetailsContent/ActivityDetailsContent'
import QueryStateMessage from '../../components/system/QueryStateMessage/QueryStateMessage'
import { useActivityDetailsQuery } from '../../hooks/queries/useActivityDetailsQuery'
import './ActivityDetailsPage.css'

function ActivityNotFound() {
  return (
    <main className="activity-details-page">
      <Button component={Link} to="/" startIcon={<ArrowBack />}>
        Wróć do aktywności
      </Button>

      <Card variant="outlined" className="activity-details-page__not-found">
        <CardContent>
          <Typography component="h1" variant="h5" gutterBottom>
            Nie znaleziono aktywności
          </Typography>
          <Typography color="text.secondary">
            Aktywność o podanym identyfikatorze nie istnieje.
          </Typography>
        </CardContent>
      </Card>
    </main>
  )
}

function ActivityDetailsPage() {
  const { activityId } = useParams()
  const activityQuery = useActivityDetailsQuery(activityId ?? '')
  const isNotFound =
    !activityId ||
    (axios.isAxiosError(activityQuery.error) &&
      activityQuery.error.response?.status === 404)

  if (activityQuery.isPending && activityId) {
    return (
      <main className="activity-details-page">
        <Button component={Link} to="/" startIcon={<ArrowBack />}>
          Wróć do aktywności
        </Button>
        <QueryStateMessage message="Ładowanie aktywności..." isLoading />
      </main>
    )
  }

  if (isNotFound) {
    return <ActivityNotFound />
  }

  if (activityQuery.isError) {
    return (
      <main className="activity-details-page">
        <Button component={Link} to="/" startIcon={<ArrowBack />}>
          Wróć do aktywności
        </Button>
        <QueryStateMessage
          message="Nie udało się pobrać aktywności."
          isRetrying={activityQuery.isFetching}
          onRetry={() => {
            void activityQuery.refetch()
          }}
        />
      </main>
    )
  }

  if (!activityQuery.data) {
    return <ActivityNotFound />
  }

  return (
    <main className="activity-details-page">
      <Button component={Link} to="/" startIcon={<ArrowBack />}>
        Wróć do aktywności
      </Button>

      <ActivityDetailsContent activity={activityQuery.data} />
    </main>
  )
}

export default ActivityDetailsPage
