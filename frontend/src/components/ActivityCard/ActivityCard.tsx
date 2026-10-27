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
import { getActivityAvailability } from '../../utils/activityAvailability'
import ActivityCategoryBadge from '../ActivityCategoryBadge/ActivityCategoryBadge'
import ActivityPriceBadge from '../ActivityPriceBadge/ActivityPriceBadge'
import './ActivityCard.css'

interface ActivityCardProps {
  activity: Activity
  emphasizeMetadata?: boolean
  headingLevel?: 'h2' | 'h3'
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
  headingLevel = 'h2',
  secondaryStatusText,
  showParticipationStats = true,
  statusColor = 'primary',
  statusLabel,
}: ActivityCardProps) {
  const categoryPresentation = getActivityCategoryPresentation(
    activity.category.slug,
  )
  const startDate = new Date(activity.start_at)
  const endDate = new Date(activity.end_at)
  const isCancelled = activity.status === 'CANCELLED'
  const effectiveStatusLabel = isCancelled ? 'Anulowana' : statusLabel
  const effectiveStatusColor = isCancelled ? 'error' : statusColor
  const availability = getActivityAvailability(activity)
  const shouldBoostActivity =
    showParticipationStats &&
    activity.status === 'PUBLISHED' &&
    availability.isNearMinimum
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
        className={`activity-card activity-card--${categoryPresentation.variant}${shouldBoostActivity ? ' activity-card--near-minimum' : ''}`}
      >
        <CardContent>
          <div className="activity-card__top">
            <div className="activity-card__summary">
              <Typography component={headingLevel} variant="h6">
                {activity.title}
              </Typography>
              {emphasizeMetadata ? (
                <dl className="activity-card__metadata">
                  <div className="activity-card__metadata-item activity-card__metadata-item--timepoint">
                    <dt>
                      <img
                        className="activity-card__metadata-icon"
                        src="/icons/icons8-start-64.png"
                        alt=""
                        width="64"
                        height="64"
                      />
                      Start
                    </dt>
                    <dd>
                      <time dateTime={activity.start_at}>
                        <span>{dateFormatter.format(startDate)}</span>
                        <span className="activity-card__metadata-time">
                          {timeFormatter.format(startDate)}
                        </span>
                      </time>
                    </dd>
                  </div>

                  <div className="activity-card__metadata-item activity-card__metadata-item--timepoint">
                    <dt>
                      <img
                        className="activity-card__metadata-icon"
                        src="/icons/icons8-finish-64.png"
                        alt=""
                        width="64"
                        height="64"
                      />
                      Zakończenie
                    </dt>
                    <dd>
                      <time dateTime={activity.end_at}>
                        <span>{dateFormatter.format(endDate)}</span>
                        <span className="activity-card__metadata-time">
                          {timeFormatter.format(endDate)}
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
            <ActivityPriceBadge priceType={activity.price_type} size="small" />

            {showParticipationStats && (
              <div className="activity-card__participants">
                <Typography>
                  {hasParticipantLimit
                    ? `${activity.participant_count} / ${activity.max_participants} uczestników`
                    : `${activity.participant_count} uczestników`}
                </Typography>
                <Typography
                  className={`activity-card__availability activity-card__availability--${availability.state}${shouldBoostActivity ? ' activity-card__availability--near-minimum' : ''}`}
                  color="text.secondary"
                >
                  {shouldBoostActivity && (
                    <img
                      className="activity-card__flame"
                      src="/icons/flame-lit.gif"
                      alt=""
                      width="200"
                      height="200"
                    />
                  )}
                  <span>{availability.primaryMessage}</span>
                </Typography>
                <Typography color="text.secondary">
                  {availability.secondaryMessage}
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
