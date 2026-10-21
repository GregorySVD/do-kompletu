import type { UseQueryResult } from '@tanstack/react-query'
import axios from 'axios'
import { Button, Typography } from '@mui/material'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import ActivityCard from '../../components/ActivityCard/ActivityCard'
import QueryStateMessage from '../../components/system/QueryStateMessage/QueryStateMessage'
import { useAuth } from '../../context/auth'
import { useMyActivitiesQuery } from '../../hooks/queries/useMyActivitiesQuery'
import type { Activity, ActivityDetails } from '../../types/activity'
import './MyActivitiesPage.css'

interface ActivitySectionProps {
  activities: Activity[]
  emptyMessage: string
  id: string
  statusLabel?: string
  title: string
}

function ActivitySection({
  activities,
  emptyMessage,
  id,
  statusLabel,
  title,
}: ActivitySectionProps) {
  return (
    <section className="my-activities-section" aria-labelledby={id}>
      <Typography id={id} component="h2" variant="h5">
        {title}
      </Typography>

      {activities.length > 0 ? (
        <div className="my-activities-section__list">
          {activities.map((activity) => (
            <ActivityCard
              key={activity.id}
              activity={activity}
              statusLabel={statusLabel}
            />
          ))}
        </div>
      ) : (
        <Typography
          className="my-activities-section__empty"
          color="text.secondary"
        >
          {emptyMessage}
        </Typography>
      )}
    </section>
  )
}

interface ActivityQuerySectionProps extends Omit<
  ActivitySectionProps,
  'activities'
> {
  query: UseQueryResult<ActivityDetails[], Error>
}

function getActivitiesErrorMessage(error: Error | null) {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    return 'Sesja wygasła lub jest nieprawidłowa.'
  }

  return 'Nie udało się pobrać aktywności.'
}

function ActivitySectionState({
  id,
  title,
  children,
}: Pick<ActivitySectionProps, 'id' | 'title'> & {
  children: ReactNode
}) {
  return (
    <section className="my-activities-section" aria-labelledby={id}>
      <Typography id={id} component="h2" variant="h5">
        {title}
      </Typography>
      {children}
    </section>
  )
}

function ActivityQuerySection({
  query,
  ...sectionProps
}: ActivityQuerySectionProps) {
  if (query.isPending) {
    return (
      <ActivitySectionState id={sectionProps.id} title={sectionProps.title}>
        <QueryStateMessage message="Ładowanie aktywności..." isLoading />
      </ActivitySectionState>
    )
  }

  if (query.isError) {
    return (
      <ActivitySectionState id={sectionProps.id} title={sectionProps.title}>
        <QueryStateMessage
          message={getActivitiesErrorMessage(query.error)}
          isRetrying={query.isFetching}
          onRetry={() => void query.refetch()}
        />
      </ActivitySectionState>
    )
  }

  return <ActivitySection {...sectionProps} activities={query.data} />
}

function MyActivitiesPage() {
  const { user } = useAuth()
  const upcomingActivitiesQuery = useMyActivitiesQuery('joined', 'upcoming')
  const organizedActivitiesQuery = useMyActivitiesQuery('organized')
  const historyActivitiesQuery = useMyActivitiesQuery('joined', 'history')

  return (
    <main className="my-activities-page">
      <div className="my-activities-page__heading">
        <div>
          <Typography component="h1" variant="h4">
            Moje aktywności
          </Typography>
          <Typography color="text.secondary">
            Aktywności powiązane z profilem {user?.display_name}.
          </Typography>
        </div>

        <Button component={Link} to="/profile">
          Wróć do profilu
        </Button>
      </div>

      <ActivityQuerySection
        id="upcoming-activities-title"
        title="Nadchodzące"
        query={upcomingActivitiesQuery}
        emptyMessage="Nie masz jeszcze nadchodzących aktywności."
      />

      <ActivityQuerySection
        id="organized-activities-title"
        title="Organizowane przeze mnie"
        query={organizedActivitiesQuery}
        emptyMessage="Nie organizujesz jeszcze żadnych aktywności."
        statusLabel="Organizujesz"
      />

      <ActivityQuerySection
        id="activity-history-title"
        title="Historia"
        query={historyActivitiesQuery}
        emptyMessage="Nie masz jeszcze zakończonych aktywności."
        statusLabel="Zakończona"
      />
    </main>
  )
}

export default MyActivitiesPage
