import type { UseQueryResult } from '@tanstack/react-query'
import { Add, Edit, Event, Explore } from '@mui/icons-material'
import axios from 'axios'
import { Alert, Button, Typography } from '@mui/material'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import ProfileActivitySection, {
  type ProfileActivitySectionProps,
  type ProfileActivityStatusPresentation,
} from '../../components/profile/ProfileActivitySection/ProfileActivitySection'
import EditProfileDialog from '../../components/profile/EditProfileDialog/EditProfileDialog'
import LoadingSkeleton from '../../components/system/LoadingSkeleton/LoadingSkeleton'
import QueryStateMessage from '../../components/system/QueryStateMessage/QueryStateMessage'
import UserAvatar from '../../components/UserAvatar/UserAvatar'
import { useAuth } from '../../context/auth'
import { useMyActivitiesQuery } from '../../hooks/queries/useMyActivitiesQuery'
import type { ActivityDetails } from '../../types/activity'
import './ProfilePage.css'

const profileSectionLimit = 3

function sortUpcomingActivities(activities: ActivityDetails[]) {
  return activities.toSorted((firstActivity, secondActivity) => {
    const firstIsInactive = ['CANCELLED', 'ENDED'].includes(
      firstActivity.status,
    )
    const secondIsInactive = ['CANCELLED', 'ENDED'].includes(
      secondActivity.status,
    )

    if (firstIsInactive !== secondIsInactive) {
      return firstIsInactive ? 1 : -1
    }

    return (
      Date.parse(firstActivity.start_at) - Date.parse(secondActivity.start_at)
    )
  })
}

function sortOrganizedActivities(activities: ActivityDetails[]) {
  const currentTime = Date.now()

  return activities.toSorted((firstActivity, secondActivity) => {
    const firstStartTime = Date.parse(firstActivity.start_at)
    const secondStartTime = Date.parse(secondActivity.start_at)
    const firstEndTime = Date.parse(firstActivity.end_at)
    const secondEndTime = Date.parse(secondActivity.end_at)
    const firstIsUpcoming =
      !['CANCELLED', 'ENDED'].includes(firstActivity.status) &&
      firstEndTime >= currentTime
    const secondIsUpcoming =
      !['CANCELLED', 'ENDED'].includes(secondActivity.status) &&
      secondEndTime >= currentTime

    if (firstIsUpcoming !== secondIsUpcoming) {
      return firstIsUpcoming ? -1 : 1
    }

    return firstIsUpcoming
      ? firstStartTime - secondStartTime
      : secondStartTime - firstStartTime
  })
}

function sortActivityHistory(activities: ActivityDetails[]) {
  return activities.toSorted(
    (firstActivity, secondActivity) =>
      Date.parse(secondActivity.end_at) - Date.parse(firstActivity.end_at),
  )
}

function getParticipationStatus(
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

function getOrganizedActivityStatus(
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

function getHistoryActivityStatus(
  activity: ActivityDetails,
): ProfileActivityStatusPresentation {
  if (activity.status === 'CANCELLED') {
    return { label: 'Anulowana', color: 'error' }
  }

  switch (activity.current_user_participation?.status) {
    case 'COMPLETED':
      return {
        label: 'Ukończona',
        color: 'success',
        secondaryStatusText:
          activity.current_user_participation.checked_in_at !== null
            ? 'Check-in zweryfikowany lokalizacyjnie'
            : undefined,
      }
    case 'NO_SHOW':
      return { label: 'Nieobecność', color: 'warning' }
    default:
      return { label: 'Zakończona', color: 'default' }
  }
}

interface ProfileActivityQuerySectionProps extends Omit<
  ProfileActivitySectionProps,
  'activities' | 'contentFallback'
> {
  query: UseQueryResult<ActivityDetails[], Error>
  sortActivities: (activities: ActivityDetails[]) => ActivityDetails[]
}

function getQueryFallback(
  query: UseQueryResult<ActivityDetails[], Error>,
): ReactNode | undefined {
  if (query.isPending || (query.isError && axios.isCancel(query.error))) {
    return (
      <LoadingSkeleton
        embedded
        message="Ładowanie sekcji aktywności..."
        variant="profile-section"
      />
    )
  }

  if (query.isError) {
    return (
      <QueryStateMessage
        message="Nie udało się pobrać tej części profilu."
        isRetrying={query.isFetching}
        onRetry={() => void query.refetch()}
      />
    )
  }

  return undefined
}

function ProfileActivityQuerySection({
  query,
  sortActivities,
  ...sectionProps
}: ProfileActivityQuerySectionProps) {
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

function ProfilePage() {
  const { user } = useAuth()
  const participatingActivitiesQuery = useMyActivitiesQuery(
    'joined',
    'upcoming',
  )
  const organizedActivitiesQuery = useMyActivitiesQuery('organized')
  const historyActivitiesQuery = useMyActivitiesQuery('joined', 'history')
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)

  if (!user) {
    return null
  }

  function openEditDialog() {
    setShowSuccess(false)
    setIsEditDialogOpen(true)
  }

  function handleProfileUpdated() {
    setIsEditDialogOpen(false)
    setShowSuccess(true)
  }

  return (
    <main className="profile-page">
      <header className="profile-page__heading">
        <div>
          <span className="profile-page__eyebrow">PANEL GRACZA // 01</span>
          <Typography component="h1" variant="h3">
            Twoje centrum aktywności
          </Typography>
          <Typography color="text.secondary">
            Zapisy, aktywności i historia w jednym miejscu.
          </Typography>
        </div>

        <span className="profile-page__sync-status">
          <span aria-hidden="true" />
          Profil aktywny
        </span>
      </header>

      {showSuccess && (
        <Alert className="profile-page__success" severity="success">
          Profil został zaktualizowany.
        </Alert>
      )}

      <div className="profile-page__overview">
        <section
          className="profile-player-card"
          aria-labelledby="profile-summary-title"
        >
          <div className="profile-player-card__identity">
            <div className="profile-player-card__avatar-frame">
              <UserAvatar
                className="profile-player-card__avatar"
                avatarUrl={user.avatar_url}
                displayName={user.display_name}
              />
              <span
                className="profile-player-card__online"
                aria-hidden="true"
              />
            </div>

            <div className="profile-player-card__details">
              <span className="profile-player-card__label">GRACZ</span>
              <Typography
                id="profile-summary-title"
                component="h2"
                variant="h4"
              >
                {user.display_name}
              </Typography>
              <Typography color="text.secondary">{user.email}</Typography>
            </div>

            <Button
              className="profile-player-card__edit"
              variant="outlined"
              startIcon={<Edit />}
              onClick={openEditDialog}
            >
              Edytuj profil
            </Button>
          </div>

          <div
            className="profile-player-card__stats"
            aria-label="Statystyki profilu"
          >
            <div>
              <span>{user.points_total}</span>
              <small>Punkty</small>
            </div>
            <div>
              <span>{getQueryCount(participatingActivitiesQuery)}</span>
              <small>Nadchodzące</small>
            </div>
            <div>
              <span>{getQueryCount(organizedActivitiesQuery)}</span>
              <small>Organizowane</small>
            </div>
            <div>
              <span>{getQueryCount(historyActivitiesQuery)}</span>
              <small>Historia</small>
            </div>
          </div>
        </section>

        <nav
          className="profile-command-panel"
          aria-label="Szybkie akcje profilu"
        >
          <div className="profile-command-panel__heading">
            <span>SKRÓTY // MENU</span>
            <Typography component="h2" variant="h5">
              Co robimy dalej?
            </Typography>
          </div>

          <div className="profile-command-panel__actions">
            <Button component={Link} to="/" startIcon={<Explore />}>
              <span>Odkrywaj aktywności</span>
              <small>Znajdź coś w okolicy</small>
            </Button>
            <Button component={Link} to="/activities/new" startIcon={<Add />}>
              <span>Dodaj aktywność</span>
              <small>Zbierz własny komplet</small>
            </Button>
            <Button
              component={Link}
              to="/profile/activities"
              startIcon={<Event />}
            >
              <span>Wszystkie aktywności</span>
              <small>Pełny widok zapisów</small>
            </Button>
          </div>
        </nav>
      </div>

      <div className="profile-page__activity-sections">
        <ProfileActivityQuerySection
          id="profile-participating-title"
          kicker="TWÓJ PLAN // NAJBLIŻSZE"
          title="Aktywności, w których bierzesz udział"
          description="Posortowane od najbliższego terminu - pierwsza pozycja jest Twoją następną aktywnością."
          query={participatingActivitiesQuery}
          sortActivities={sortUpcomingActivities}
          emptyMessage="Nie bierzesz jeszcze udziału w żadnej nadchodzącej aktywności."
          statusPresentation={getParticipationStatus}
          highlightFirst
          limit={profileSectionLimit}
          actionLabel="Zobacz wszystkie zapisy"
          actionTo="/profile/activities"
          activityReturnTo="/profile"
        />

        <ProfileActivityQuerySection
          id="profile-organized-title"
          kicker="TWOJE AKTYWNOŚCI // HOST"
          title="Organizowane przeze mnie"
          description="Najpierw pokazujemy aktywności, które wymagają Twojej uwagi w najbliższym terminie."
          query={organizedActivitiesQuery}
          sortActivities={sortOrganizedActivities}
          emptyMessage="Nie organizujesz jeszcze żadnej aktywności."
          statusPresentation={getOrganizedActivityStatus}
          limit={profileSectionLimit}
          actionLabel="Zarządzaj aktywnościami"
          actionTo="/profile/activities"
          activityReturnTo="/profile"
        />

        <ProfileActivityQuerySection
          id="profile-history-title"
          kicker="ARCHIWUM // OSTATNIO"
          title="Historia"
          description="Ostatnio zakończone aktywności — najnowsze są na początku."
          query={historyActivitiesQuery}
          sortActivities={sortActivityHistory}
          emptyMessage="Twoja historia aktywności jest jeszcze pusta."
          statusPresentation={getHistoryActivityStatus}
          showParticipationStats={false}
          limit={profileSectionLimit}
          actionLabel="Otwórz pełną historię"
          actionTo="/profile/activities"
          activityReturnTo="/profile"
        />
      </div>

      {isEditDialogOpen && (
        <EditProfileDialog
          user={user}
          onClose={() => setIsEditDialogOpen(false)}
          onUpdated={handleProfileUpdated}
        />
      )}
    </main>
  )
}

export default ProfilePage
