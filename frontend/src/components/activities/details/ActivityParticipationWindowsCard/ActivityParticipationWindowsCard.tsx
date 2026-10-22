import { LocationSearching, VerifiedOutlined } from '@mui/icons-material'
import { Card, CardContent, Typography } from '@mui/material'
import type { ReactNode } from 'react'
import type { ActivityDetails } from '../../../../types/activity'
import { formatDateTime } from '../../../../utils/dateFormat'
import './ActivityParticipationWindowsCard.css'

interface ActivityParticipationWindowsCardProps {
  activity: ActivityDetails
}

interface ParticipationWindowProps {
  emptyMessage: string
  end: string | null
  icon: ReactNode
  start: string | null
  title: string
}

function ParticipationWindow({
  emptyMessage,
  end,
  icon,
  start,
  title,
}: ParticipationWindowProps) {
  const isAvailable = start !== null && end !== null

  return (
    <div className="activity-participation-windows__item">
      <span className="activity-participation-windows__icon">{icon}</span>
      <div>
        <Typography component="h3" variant="h6">
          {title}
        </Typography>
        {isAvailable ? (
          <Typography color="text.secondary">
            <time dateTime={start}>{formatDateTime(start)}</time>
            <span aria-hidden="true"> — </span>
            <time dateTime={end}>{formatDateTime(end)}</time>
          </Typography>
        ) : (
          <Typography color="text.secondary">{emptyMessage}</Typography>
        )}
      </div>
    </div>
  )
}

function ActivityParticipationWindowsCard({
  activity,
}: ActivityParticipationWindowsCardProps) {
  return (
    <Card
      component="section"
      variant="outlined"
      className="activity-participation-windows"
    >
      <CardContent>
        <Typography component="h2" variant="h5">
          Ważne terminy udziału
        </Typography>
        <div className="activity-participation-windows__list">
          <ParticipationWindow
            title="Potwierdzenie udziału"
            start={activity.confirmation_opens_at}
            end={activity.confirmation_deadline_at}
            emptyMessage="Potwierdzanie udziału nie jest jeszcze dostępne."
            icon={<VerifiedOutlined aria-hidden="true" />}
          />
          <ParticipationWindow
            title="Check-in"
            start={activity.checkin_opens_at}
            end={activity.checkin_closes_at}
            emptyMessage="Check-in nie jest jeszcze dostępny."
            icon={<LocationSearching aria-hidden="true" />}
          />
        </div>
        {activity.checkin_radius_m !== null && (
          <Typography
            className="activity-participation-windows__radius"
            variant="body2"
            color="text.secondary"
          >
            Check-in jest możliwy w promieniu {activity.checkin_radius_m} m od
            miejsca aktywności.
          </Typography>
        )}
      </CardContent>
    </Card>
  )
}

export default ActivityParticipationWindowsCard
