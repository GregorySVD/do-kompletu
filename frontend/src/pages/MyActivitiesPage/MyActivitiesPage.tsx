import type { UseQueryResult } from '@tanstack/react-query'
import axios from 'axios'
import { Typography } from '@mui/material'
import type { ReactNode } from 'react'
import ProfileActivitySection, {
  type ProfileActivitySectionProps,
  type ProfileActivityStatusPresentation,
} from '../../components/profile/ProfileActivitySection/ProfileActivitySection'
import BackButton from '../../components/navigation/BackButton/BackButton'
import QueryStateMessage from '../../components/system/QueryStateMessage/QueryStateMessage'
import { useAuth } from '../../context/auth'
import { useMyActivitiesQuery } from '../../hooks/queries/useMyActivitiesQuery'
import type { ActivityDetails } from '../../types/activity'
import './MyActivitiesPage.css'

interface ActivityQuerySectionProps extends Omit<
  ProfileActivitySectionProps,
  'activities' | 'contentFallback'
> {
  query: UseQueryResult<ActivityDetails[], Error>
  sortActivities: (activities: ActivityDetails[]) => ActivityDetails[]
}

function sortByStartTime(activities: ActivityDetails[]) {
  return activities.toSorted(
    (firstActivity, secondActivity) =>
      Date.parse(firstActivity.start_at) - Date.parse(secondActivity.start_at),
  )
}

function sortByLatestEndTime(activities: ActivityDetails[]) {
  return activities.toSorted(
    (firstActivity, secondActivity) =>
      Date.parse(secondActivity.end_at) - Date.parse(firstActivity.end_at),
  )
}

function sortOrganizedActivities(activities: ActivityDetails[]) {
  const currentTime = Date.now()

  return activities.toSorted((firstActivity, secondActivity) => {
    const firstStartTime = Date.parse(firstActivity.start_at)
    const secondStartTime = Date.parse(secondActivity.start_at)
    const firstIsActive =
      !['CANCELLED', 'ENDED'].includes(firstActivity.status) &&
      Date.parse(firstActivity.end_at) >= currentTime
    const secondIsActive =
      !['CANCELLED', 'ENDED'].includes(secondActivity.status) &&
      Date.parse(secondActivity.end_at) >= currentTime

    if (firstIsActive !== secondIsActive) {
      return firstIsActive ? -1 : 1
    }

    return firstIsActive
      ? firstStartTime - secondStartTime
      : secondStartTime - firstStartTime
  })
}

function getParticipationPresentation(
  activity: ActivityDetails,
): ProfileActivityStatusPresentation | undefined {
  switch (activity.current_user_participation?.status) {
    case 'JOINED':
      return { label: 'Zapisany', color: 'success' }
    case 'CONFIRMED':
      return { label: 'Potwierdzony', color: 'success' }
    case 'CHECKED_IN':
      return { label: 'Check-in wykonany', color: 'success' }
    default:
      return undefined
  }
}

function getWaitlistPresentation(
  activity: ActivityDetails,
): ProfileActivityStatusPresentation {
  const waitlistPosition =
    activity.current_user_participation?.status === 'WAITLISTED'
      ? activity.current_user_participation.waitlist_position
      : null

  return {
    label: 'Lista rezerwowa',
    color: 'secondary',
    secondaryStatusText:
      waitlistPosition !== null
        ? `Twoja pozycja na liście: ${waitlistPosition}`
        : undefined,
  }
}

function getOrganizedActivityPresentation(
  activity: ActivityDetails,
): ProfileActivityStatusPresentation {
  switch (activity.status) {
    case 'CANCELLED':
      return { label: 'Anulowana', color: 'error' }
    case 'ENDED':
      return { label: 'Zakończona', color: 'default' }
    case 'ONGOING':
      return { label: 'Trwa teraz', color: 'warning' }
    default:
      return { label: 'Organizujesz', color: 'secondary' }
  }
}

function getHistoryActivityPresentation(
  activity: ActivityDetails,
): ProfileActivityStatusPresentation {
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

function getActivitiesErrorMessage(error: Error | null) {
  if (axios.isCancel(error)) {
    return null
  }

  if (axios.isAxiosError(error) && error.response?.status === 401) {
    return 'Sesja wygasła lub jest nieprawidłowa.'
  }

  return 'Nie udało się pobrać aktywności.'
}

function getQueryFallback(
  query: UseQueryResult<ActivityDetails[], Error>,
): ReactNode | undefined {
  if (query.isPending) {
    return <QueryStateMessage message="Ładowanie aktywności..." isLoading />
  }

  if (query.isError) {
    const errorMessage = getActivitiesErrorMessage(query.error)

    if (errorMessage === null) {
      return <QueryStateMessage message="Ładowanie aktywności..." isLoading />
    }

    return (
      <QueryStateMessage
        message={errorMessage}
        isRetrying={query.isFetching}
        onRetry={() => void query.refetch()}
      />
    )
  }

  return undefined
}

function ActivityQuerySection({
  query,
  sortActivities,
  ...sectionProps
}: ActivityQuerySectionProps) {
  const contentFallback = getQueryFallback(query)
  const activities = query.isSuccess ? sortActivities(query.data) : []

  return (
    <ProfileActivitySection
      {...sectionProps}
      activities={activities}
      contentFallback={contentFallback}
    />
  )
}

function getQueryCount(query: UseQueryResult<ActivityDetails[], Error>) {
  return query.isSuccess ? String(query.data.length) : '—'
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
      <header className="my-activities-page__heading">
        <div>
          <span className="my-activities-page__eyebrow">
            CENTRUM GRACZA // 02
          </span>
          <Typography component="h1" variant="h3">
            Moje aktywności
          </Typography>
          <Typography color="text.secondary">
            Wszystkie aktywności powiązane z profilem {user?.display_name},
            podzielone według Twojej roli.
          </Typography>
        </div>

        <BackButton to="/profile">Wróć do profilu</BackButton>
      </header>

      <nav
        className="my-activities-page__index"
        aria-label="Przejdź do sekcji aktywności"
      >
        <a href="#upcoming-activities-title">
          <span>01</span>
          <strong>Nadchodzące</strong>
          <small>{getQueryCount(upcomingActivitiesQuery)}</small>
        </a>
        <a href="#waitlisted-activities-title">
          <span>02</span>
          <strong>Lista rezerwowa</strong>
          <small>{getQueryCount(waitlistedActivitiesQuery)}</small>
        </a>
        <a href="#organized-activities-title">
          <span>03</span>
          <strong>Organizowane</strong>
          <small>{getQueryCount(organizedActivitiesQuery)}</small>
        </a>
        <a href="#activity-history-title">
          <span>04</span>
          <strong>Historia</strong>
          <small>{getQueryCount(historyActivitiesQuery)}</small>
        </a>
      </nav>

      <div className="my-activities-page__sections">
        <ActivityQuerySection
          id="upcoming-activities-title"
          kicker="01 // TWÓJ PLAN"
          title="Nadchodzące"
          description="Aktywności, w których bierzesz udział — od najbliższego terminu."
          query={upcomingActivitiesQuery}
          sortActivities={sortByStartTime}
          emptyMessage="Nie masz jeszcze nadchodzących aktywności."
          statusPresentation={getParticipationPresentation}
          tone="upcoming"
          activityReturnTo="/profile/activities"
        />

        <ActivityQuerySection
          id="waitlisted-activities-title"
          kicker="02 // OCZEKIWANIE"
          title="Lista rezerwowa"
          description="Wydarzenia, w których czekasz na zwolnienie miejsca."
          query={waitlistedActivitiesQuery}
          sortActivities={sortByStartTime}
          emptyMessage="Nie oczekujesz obecnie na miejsce w żadnej aktywności."
          statusPresentation={getWaitlistPresentation}
          tone="waitlist"
          activityReturnTo="/profile/activities"
        />

        <ActivityQuerySection
          id="organized-activities-title"
          kicker="03 // TRYB ORGANIZATORA"
          title="Organizowane przeze mnie"
          description="Najpierw aktywności trwające i te, które rozpoczną się wkrótce."
          query={organizedActivitiesQuery}
          sortActivities={sortOrganizedActivities}
          emptyMessage="Nie organizujesz jeszcze żadnych aktywności."
          statusPresentation={getOrganizedActivityPresentation}
          tone="organized"
          activityReturnTo="/profile/activities"
        />

        <ActivityQuerySection
          id="activity-history-title"
          kicker="04 // ARCHIWUM"
          title="Historia"
          description="Zakończone aktywności, od najnowszych do najstarszych."
          query={historyActivitiesQuery}
          sortActivities={sortByLatestEndTime}
          emptyMessage="Nie masz jeszcze zakończonych aktywności."
          statusPresentation={getHistoryActivityPresentation}
          showParticipationStats={false}
          tone="history"
          activityReturnTo="/profile/activities"
        />
      </div>
    </main>
  )
}

export default MyActivitiesPage
