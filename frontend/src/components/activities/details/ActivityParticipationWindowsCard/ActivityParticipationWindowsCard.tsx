import { Card, CardContent, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'
import { formatDateTime } from '../../../../utils/dateFormat'
import './ActivityParticipationWindowsCard.css'

interface ActivityParticipationWindowsCardProps {
  activity: ActivityDetails
}

interface ParticipationWindowProps {
  emptyMessage: string
  end: string | null
  iconSrc: string
  start: string | null
  title: string
}

function ParticipationWindow({
  emptyMessage,
  end,
  iconSrc,
  start,
  title,
}: ParticipationWindowProps) {
  const isAvailable = start !== null && end !== null

  return (
    <div className="activity-participation-windows__item">
      <span className="activity-participation-windows__icon">
        <img src={iconSrc} alt="" width="64" height="64" aria-hidden="true" />
      </span>
      <div className="activity-participation-windows__item-content">
        <Typography
          className="activity-participation-windows__item-title"
          component="h3"
          variant="h6"
        >
          {title}
        </Typography>
        {isAvailable ? (
          <div className="activity-participation-windows__range">
            <time
              className="activity-participation-windows__range-start"
              dateTime={start}
            >
              <span className="activity-participation-windows__range-label">
                Od
              </span>
              <strong className="activity-participation-windows__range-value">
                {formatDateTime(start)}
              </strong>
            </time>
            <time
              className="activity-participation-windows__range-end"
              dateTime={end}
            >
              <span className="activity-participation-windows__range-label">
                Do
              </span>
              <strong className="activity-participation-windows__range-value">
                {formatDateTime(end)}
              </strong>
            </time>
          </div>
        ) : (
          <Typography
            className="activity-participation-windows__empty-message"
            color="text.secondary"
          >
            {emptyMessage}
          </Typography>
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
      <CardContent className="activity-participation-windows__content">
        <div className="activity-participation-windows__heading">
          <Typography
            className="activity-participation-windows__title"
            component="h2"
            variant="h5"
          >
            Etapy udziału
          </Typography>
          <Typography
            className="activity-participation-windows__subtitle"
            color="text.secondary"
          >
            Potwierdzenie udziału i check-in
          </Typography>
        </div>
        <div className="activity-participation-windows__list">
          <ParticipationWindow
            title="Potwierdzenie udziału"
            start={activity.confirmation_opens_at}
            end={activity.confirmation_deadline_at}
            emptyMessage="Potwierdzanie udziału nie jest jeszcze dostępne."
            iconSrc="/icons/icons8-today-64.png"
          />
          <ParticipationWindow
            title="Check-in"
            start={activity.checkin_opens_at}
            end={activity.checkin_closes_at}
            emptyMessage="Check-in nie jest jeszcze dostępny."
            iconSrc="/icons/icons8-navigation-64.png"
          />
        </div>
        {activity.checkin_radius_m !== null && (
          <Typography
            className="activity-participation-windows__radius-note"
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
