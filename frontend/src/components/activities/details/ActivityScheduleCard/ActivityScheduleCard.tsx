import { ScheduleOutlined } from '@mui/icons-material'
import { Card, CardContent, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'
import './ActivityScheduleCard.css'

interface ActivityScheduleCardProps {
  activity: ActivityDetails
}

const dateFormatter = new Intl.DateTimeFormat('pl-PL', {
  day: 'numeric',
  month: 'long',
  weekday: 'long',
  year: 'numeric',
})

const timeFormatter = new Intl.DateTimeFormat('pl-PL', {
  hour: '2-digit',
  minute: '2-digit',
})

function SchedulePoint({ label, value }: { label: string; value: string }) {
  const date = new Date(value)

  return (
    <div className="activity-schedule-card__point">
      <span className="activity-schedule-card__point-icon">
        <img
          src="/icons/icons8-schedule-64.png"
          alt=""
          width="64"
          height="64"
          aria-hidden="true"
        />
      </span>
      <div>
        <Typography
          className="activity-schedule-card__point-label"
          variant="body2"
          color="text.secondary"
        >
          {label}
        </Typography>
        <time dateTime={value}>
          <Typography className="activity-schedule-card__date">
            {dateFormatter.format(date)}
          </Typography>
          <span className="activity-schedule-card__time">
            <ScheduleOutlined aria-hidden="true" />
            {timeFormatter.format(date)}
          </span>
        </time>
      </div>
    </div>
  )
}

function ActivityScheduleCard({ activity }: ActivityScheduleCardProps) {
  return (
    <Card
      component="section"
      variant="outlined"
      className="activity-schedule-card"
    >
      <CardContent className="activity-schedule-card__content">
        <div className="activity-schedule-card__heading">
          <span className="activity-schedule-card__heading-icon">
            <img
              src="/icons/icons8-schedule-64.png"
              alt=""
              width="64"
              height="64"
              aria-hidden="true"
            />
          </span>
          <div>
            <Typography component="h2" variant="h5">
              Termin aktywności
            </Typography>
            <Typography color="text.secondary">
              Zaplanuj czas od rozpoczęcia do zakończenia
            </Typography>
          </div>
        </div>
        <div className="activity-schedule-card__timeline">
          <SchedulePoint label="Start" value={activity.start_at} />
          <SchedulePoint label="Koniec" value={activity.end_at} />
        </div>
      </CardContent>
    </Card>
  )
}

export default ActivityScheduleCard
