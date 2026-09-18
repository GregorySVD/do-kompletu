import { Button, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import ActivityCard from '../../components/ActivityCard/ActivityCard'
import { mockActivities } from '../../data/mockActivities'
import { mockCurrentUser } from '../../data/mockCurrentUser'
import { mockUserActivities } from '../../data/mockUserActivities'
import type { Activity } from '../../types/activity'
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

function MyActivitiesPage() {
  const now = new Date()
  const joinedActivityIds = new Set(mockUserActivities.joined_activity_ids)
  const organizedActivityIds = new Set(
    mockUserActivities.organized_activity_ids,
  )

  const joinedActivities = mockActivities.filter((activity) =>
    joinedActivityIds.has(activity.id),
  )
  const upcomingActivities = joinedActivities.filter(
    (activity) => new Date(activity.end_at) >= now,
  )
  const organizedActivities = mockActivities.filter((activity) =>
    organizedActivityIds.has(activity.id),
  )
  const historyActivities = joinedActivities.filter(
    (activity) => new Date(activity.end_at) < now,
  )

  return (
    <main className="my-activities-page">
      <div className="my-activities-page__heading">
        <div>
          <Typography component="h1" variant="h4">
            Moje aktywności
          </Typography>
          <Typography color="text.secondary">
            Aktywności powiązane z profilem {mockCurrentUser.display_name}.
          </Typography>
        </div>

        <Button component={Link} to="/profile">
          Wróć do profilu
        </Button>
      </div>

      <ActivitySection
        id="upcoming-activities-title"
        title="Nadchodzące"
        activities={upcomingActivities}
        emptyMessage="Nie masz jeszcze nadchodzących aktywności."
      />

      <ActivitySection
        id="organized-activities-title"
        title="Organizowane przeze mnie"
        activities={organizedActivities}
        emptyMessage="Nie organizujesz obecnie żadnych aktywności."
        statusLabel="Organizujesz"
      />

      <ActivitySection
        id="activity-history-title"
        title="Historia"
        activities={historyActivities}
        emptyMessage="Nie masz jeszcze zakończonych aktywności."
        statusLabel="Zakończona"
      />
    </main>
  )
}

export default MyActivitiesPage
