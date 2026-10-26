import axios from 'axios'
import { useParams } from 'react-router-dom'
import ActivityDetailsContent from '../../components/activities/details/ActivityDetailsContent/ActivityDetailsContent'
import BackButton from '../../components/navigation/BackButton/BackButton'
import QueryStateMessage from '../../components/system/QueryStateMessage/QueryStateMessage'
import { useActivityDetailsQuery } from '../../hooks/queries/useActivityDetailsQuery'
import './ActivityDetailsPage.css'

function ActivityNotFound() {
  return (
    <main className="activity-details-page activity-details-page--not-found">
      <BackButton to="/" />

      <section
        className="activity-not-found"
        aria-labelledby="activity-not-found-title"
      >
        <div className="activity-not-found__visual" aria-hidden="true">
          <img src="/error.gif" alt="" width="500" height="500" />
          <span className="activity-not-found__error-code">404</span>
        </div>

        <div className="activity-not-found__content">
          <p className="activity-not-found__eyebrow">Błąd 404</p>
          <h1
            id="activity-not-found-title"
            className="activity-not-found__title"
          >
            Nie znaleziono aktywności
          </h1>
          <p className="activity-not-found__message">
            Ta aktywność nie istnieje albo nie jest już dostępna.
          </p>
          <p className="activity-not-found__hint">
            Wróć do listy i wybierz inną aktywność w swojej okolicy.
          </p>
        </div>
      </section>
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
        <BackButton to="/" />
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
        <BackButton to="/" />
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
      <BackButton to="/" />

      <ActivityDetailsContent activity={activityQuery.data} />
    </main>
  )
}

export default ActivityDetailsPage
