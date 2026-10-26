import {
  Card,
  CardContent,
  Chip,
  Typography,
  type ChipProps,
} from '@mui/material'
import { Link } from 'react-router-dom'
import { getActivityCategoryPresentation } from '../../config/activityCategoryPresentation'
import type { Activity } from '../../types/activity'
import ActivityCategoryBadge from '../ActivityCategoryBadge/ActivityCategoryBadge'
import './ActivityCard.css'

interface ActivityCardProps {
  activity: Activity
  emphasizeMetadata?: boolean
  secondaryStatusText?: string
  showParticipationStats?: boolean
  statusColor?: ChipProps['color']
  statusLabel?: string
}

const dateFormatter = new Intl.DateTimeFormat('pl-PL', { dateStyle: 'medium' })

const timeFormatter = new Intl.DateTimeFormat('pl-PL', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

function ActivityCard({
  activity,
  emphasizeMetadata = false,
  secondaryStatusText,
  showParticipationStats = true,
  statusColor = 'primary',
  statusLabel,
}: ActivityCardProps) {
  const categoryPresentation = getActivityCategoryPresentation(
    activity.category.slug,
  )
  const startDate = new Date(activity.start_at)
  const isCancelled = activity.status === 'CANCELLED'
  const effectiveStatusLabel = isCancelled ? 'Anulowana' : statusLabel
  const effectiveStatusColor = isCancelled ? 'error' : statusColor
  const missingToMinimum = Math.max(
    activity.min_participants - activity.participant_count,
    0,
  )
  const isAlmostComplete =
    showParticipationStats &&
    activity.status === 'PUBLISHED' &&
    missingToMinimum > 0 &&
    missingToMinimum <= 2
  const hasParticipantLimit = activity.max_participants !== null

  return (
    <Link
      className="activity-card__link"
      to={`/activities/${activity.id}`}
      aria-label={`Zobacz szczegóły: ${activity.title}`}
    >
      <Card
        component="article"
        variant="outlined"
        className={`activity-card activity-card--${categoryPresentation.variant}${isAlmostComplete ? ' activity-card--almost-complete' : ''}`}
      >
        <CardContent>
          <div className="activity-card__top">
            <div className="activity-card__summary">
              <Typography component="h2" variant="h6">
                {activity.title}
              </Typography>
              {emphasizeMetadata ? (
                <dl className="activity-card__metadata">
                  <div className="activity-card__metadata-item activity-card__metadata-item--date">
                    <dt>Termin</dt>
                    <dd>
                      <time dateTime={activity.start_at}>
                        <span>{dateFormatter.format(startDate)}</span>
                        <span className="activity-card__metadata-time">
                          {timeFormatter.format(startDate)}
                        </span>
                      </time>
                    </dd>
                  </div>

                  <div className="activity-card__metadata-item activity-card__metadata-item--location">
                    <dt>Miejsce</dt>
                    <dd>{activity.location_name}</dd>
                  </div>
                </dl>
              ) : (
                <Typography color="text.secondary">
                  {dateFormatter.format(startDate)},{' '}
                  {timeFormatter.format(startDate)}
                </Typography>
              )}
            </div>

            <div className="activity-card__chips">
              <ActivityCategoryBadge
                category={activity.category}
                size="small"
              />
              {effectiveStatusLabel && (
                <Chip
                  className="activity-card__status"
                  label={effectiveStatusLabel}
                  size="small"
                  color={effectiveStatusColor}
                  variant="outlined"
                />
              )}
            </div>
          </div>

          {!emphasizeMetadata && (
            <Typography className="activity-card__location">
              {activity.location_name}
            </Typography>
          )}
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
              className={`activity-card__price activity-card__price--${activity.price_type === 'FREE' ? 'free' : 'paid'}`}
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
                <Typography
                  className={
                    isAlmostComplete
                      ? 'activity-card__missing activity-card__missing--almost-complete'
                      : 'activity-card__missing'
                  }
                  color="text.secondary"
                >
                  {isAlmostComplete && (
                    <img
                      className="activity-card__flame"
                      src="/icons/flame-lit.gif"
                      alt=""
                      width="200"
                      height="200"
                    />
                  )}
                  <span>
                    {missingToMinimum > 0
                      ? `Brakuje${isAlmostComplete ? ' tylko' : ''} ${missingToMinimum} ${missingToMinimum === 1 ? 'osoby' : 'osób'} do kompletu`
                      : 'Komplet zebrany'}
                  </span>
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
