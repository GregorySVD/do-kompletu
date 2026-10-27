import { Button, Typography, type ChipProps } from '@mui/material'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { ActivityDetails } from '../../../types/activity'
import type { ActivityReturnPath } from '../../../utils/activityNavigation'
import ActivityCard from '../../ActivityCard/ActivityCard'
import './ProfileActivitySection.css'

export interface ProfileActivityStatusPresentation {
  color?: ChipProps['color']
  label?: string
  secondaryStatusText?: string
}

export interface ProfileActivitySectionProps {
  actionLabel?: string
  actionTo?: string
  activityReturnTo?: ActivityReturnPath
  activities: ActivityDetails[]
  contentFallback?: ReactNode
  description: string
  emptyMessage: string
  highlightFirst?: boolean
  id: string
  kicker: string
  limit?: number
  showParticipationStats?: boolean
  statusPresentation?: (
    activity: ActivityDetails,
  ) => ProfileActivityStatusPresentation | undefined
  tone?: 'default' | 'upcoming' | 'waitlist' | 'organized' | 'history'
  title: string
}

function ProfileActivitySection({
  actionLabel,
  actionTo,
  activityReturnTo,
  activities,
  contentFallback,
  description,
  emptyMessage,
  highlightFirst = false,
  id,
  kicker,
  limit,
  showParticipationStats = true,
  statusPresentation,
  tone = 'default',
  title,
}: ProfileActivitySectionProps) {
  const visibleActivities =
    limit === undefined ? activities : activities.slice(0, limit)
  const hasAction = actionLabel !== undefined && actionTo !== undefined
  const activityCountLabel =
    contentFallback === undefined ? String(activities.length) : '—'

  return (
    <section
      className={`profile-activity-section profile-activity-section--${tone}`}
      aria-labelledby={id}
    >
      <div className="profile-activity-section__heading">
        <div>
          <Typography
            className="profile-activity-section__kicker"
            component="p"
          >
            {kicker}
          </Typography>
          <Typography id={id} component="h2" variant="h4">
            {title}
          </Typography>
          <Typography
            className="profile-activity-section__description"
            color="text.secondary"
          >
            {description}
          </Typography>
        </div>

        <div
          className="profile-activity-section__count"
          aria-label={`Liczba aktywności: ${activityCountLabel}`}
        >
          <span aria-hidden="true">{activityCountLabel}</span>
          <small>AKTYWNOŚCI</small>
        </div>
      </div>

      {contentFallback ??
        (visibleActivities.length > 0 ? (
          <div className="profile-activity-section__list">
            {visibleActivities.map((activity, index) => {
              const presentation = statusPresentation?.(activity)
              const isNearestActivity =
                highlightFirst &&
                index === 0 &&
                !['CANCELLED', 'ENDED'].includes(activity.status)

              return (
                <div
                  className={`profile-activity-section__item${
                    isNearestActivity
                      ? ' profile-activity-section__item--nearest'
                      : ''
                  }`}
                  key={activity.id}
                >
                  {isNearestActivity && (
                    <span className="profile-activity-section__nearest-label">
                      <span aria-hidden="true">//</span> NAJBLIŻSZA
                    </span>
                  )}
                  <ActivityCard
                    activity={activity}
                    emphasizeMetadata
                    headingLevel="h3"
                    returnTo={activityReturnTo}
                    secondaryStatusText={presentation?.secondaryStatusText}
                    showParticipationStats={showParticipationStats}
                    statusColor={presentation?.color}
                    statusLabel={presentation?.label}
                  />
                </div>
              )
            })}
          </div>
        ) : (
          <div className="profile-activity-section__empty">
            <span className="profile-activity-section__empty-code" aria-hidden>
              [ 0 ]
            </span>
            <Typography>{emptyMessage}</Typography>
          </div>
        ))}

      {hasAction && (
        <Button
          className="profile-activity-section__action"
          component={Link}
          to={actionTo}
          variant="outlined"
        >
          {actionLabel}
        </Button>
      )}
    </section>
  )
}

export default ProfileActivitySection
