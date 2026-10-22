import {
  Card,
  CardContent,
  Chip,
  Typography,
  type ChipProps,
} from '@mui/material'
import { Link } from 'react-router-dom'
import type { Activity } from '../../types/activity'
import './ActivityCard.css'

interface ActivityCardProps {
  activity: Activity
  secondaryStatusText?: string
  showParticipationStats?: boolean
  statusColor?: ChipProps['color']
  statusLabel?: string
}

const dateFormatter = new Intl.DateTimeFormat('pl-PL', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function ActivityCard({
  activity,
  secondaryStatusText,
  showParticipationStats = true,
  statusColor = 'primary',
  statusLabel,
}: ActivityCardProps) {
  const isCancelled = activity.status === 'CANCELLED'
  const effectiveStatusLabel = isCancelled ? 'Anulowana' : statusLabel
  const effectiveStatusColor = isCancelled ? 'error' : statusColor
  const missingToMinimum = Math.max(
    activity.min_participants - activity.participant_count,
    0,
  )
  const hasParticipantLimit = activity.max_participants !== null

  return (
    <Link
      className="activity-card__link"
      to={`/activities/${activity.id}`}
      aria-label={`Zobacz szczegóły: ${activity.title}`}
    >
      <Card component="article" variant="outlined" className="activity-card">
        <CardContent>
          <div className="activity-card__top">
            <div>
              <Typography component="h2" variant="h6">
                {activity.title}
              </Typography>
              <Typography color="text.secondary">
                {dateFormatter.format(new Date(activity.start_at))}
              </Typography>
            </div>

            <div className="activity-card__chips">
              <Chip label={activity.category.name} size="small" />
              {effectiveStatusLabel && (
                <Chip
                  label={effectiveStatusLabel}
                  size="small"
                  color={effectiveStatusColor}
                  variant="outlined"
                />
              )}
            </div>
          </div>

          <Typography className="activity-card__location">
            {activity.location_name}
          </Typography>
          {secondaryStatusText && (
            <Typography
              className="activity-card__secondary-status"
              color="text.secondary"
            >
              {secondaryStatusText}
            </Typography>
          )}

          <div className="activity-card__details">
            <Chip
              label={activity.price_type === 'FREE' ? 'Bezpłatna' : 'Płatna'}
              size="small"
              color={activity.price_type === 'FREE' ? 'success' : 'default'}
              variant="outlined"
            />

            {showParticipationStats && (
              <div className="activity-card__participants">
                <Typography>
                  {hasParticipantLimit
                    ? `${activity.participant_count} / ${activity.max_participants} uczestników`
                    : `${activity.participant_count} uczestników`}
                </Typography>
                <Typography color="text.secondary">
                  {missingToMinimum > 0
                    ? `Brakuje ${missingToMinimum} osób do kompletu`
                    : 'Komplet zebrany'}
                </Typography>
                <Typography color="text.secondary">
                  {hasParticipantLimit
                    ? activity.available_slots !== null &&
                      activity.available_slots > 0
                      ? `${activity.available_slots} wolnych miejsc`
                      : 'Brak wolnych miejsc'
                    : 'Bez limitu miejsc'}
                </Typography>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

export default ActivityCard
