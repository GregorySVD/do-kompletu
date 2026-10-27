import type { UseQueryResult } from '@tanstack/react-query'
import axios from 'axios'
import { Button, Typography, type ChipProps } from '@mui/material'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import ActivityCard from '../../components/ActivityCard/ActivityCard'
import QueryStateMessage from '../../components/system/QueryStateMessage/QueryStateMessage'
import { useAuth } from '../../context/auth'
import { useMyActivitiesQuery } from '../../hooks/queries/useMyActivitiesQuery'
import type { ActivityDetails } from '../../types/activity'
import './MyActivitiesPage.css'

interface ActivitySectionProps {
  activities: ActivityDetails[]
  emptyMessage: string
  getStatusPresentation?: (
    activity: ActivityDetails,
  ) => ActivityStatusPresentation
  id: string
  secondaryStatusText?: (activity: ActivityDetails) => string | undefined
  showParticipationStats?: boolean
  statusLabel?: string
  title: string
}

interface ActivityStatusPresentation {
  color: ChipProps['color']
  label: string
  secondaryStatusText?: string
}

function getHistoryActivityPresentation(
  activity: ActivityDetails,
): ActivityStatusPresentation {
  if (activity.status === 'CANCELLED') {
    return { label: 'Anulowana', color: 'error' }
  }

  const participation = activity.current_user_participation

  if (participation?.status === 'COMPLETED') {
    return {
      label: 'Ukończona',
      color: 'success',
      secondaryStatusText:
        participation.checked_in_at !== null
          ? 'Check-in zweryfikowany lokalizacyjnie'
          : undefined,
    }
  }

  if (participation?.status === 'NO_SHOW') {
    return { label: 'Nieobecność', color: 'warning' }
  }

  return { label: 'Oczekuje na rozliczenie', color: 'default' }
}

function ActivitySection({
  activities,
  emptyMessage,
  getStatusPresentation,
  id,
  secondaryStatusText,
  showParticipationStats,
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
          {activities.map((activity) => {
            const statusPresentation = getStatusPresentation?.(activity)

            return (
              <ActivityCard
                key={activity.id}
                activity={activity}
                secondaryStatusText={
                  statusPresentation?.secondaryStatusText ??
                  secondaryStatusText?.(activity)
                }
                showParticipationStats={showParticipationStats}
                statusColor={statusPresentation?.color}
                statusLabel={statusPresentation?.label ?? statusLabel}
              />
            )
          })}
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
  if (axios.isCancel(error)) {
    return null
  }

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
    const errorMessage = getActivitiesErrorMessage(query.error)

    if (errorMessage === null) {
      return (
        <ActivitySectionState id={sectionProps.id} title={sectionProps.title}>
          <QueryStateMessage message="Ładowanie aktywności..." isLoading />
        </ActivitySectionState>
      )
    }

    return (
      <ActivitySectionState id={sectionProps.id} title={sectionProps.title}>
        <QueryStateMessage
          message={errorMessage}
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
  const waitlistedActivitiesQuery = useMyActivitiesQuery(
    'waitlisted',
    'upcoming',
  )
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
        id="waitlisted-activities-title"
        title="Lista rezerwowa"
        query={waitlistedActivitiesQuery}
        emptyMessage="Nie oczekujesz obecnie na miejsce w żadnej aktywności."
        statusLabel="Lista rezerwowa"
        secondaryStatusText={(activity) => {
          const participation = activity.current_user_participation

          return participation?.status === 'WAITLISTED' &&
            participation.waitlist_position !== null
            ? `Pozycja: ${participation.waitlist_position}`
            : undefined
        }}
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
        getStatusPresentation={getHistoryActivityPresentation}
        showParticipationStats={false}
      />
    </main>
  )
}

export default MyActivitiesPage
