import { Chip, Typography } from '@mui/material'
import { getActivityCategoryPresentation } from '../../../../config/activityCategoryPresentation'
import type { ActivityDetails } from '../../../../types/activity'
import ActivityStatusBadge from '../ActivityStatusBadge/ActivityStatusBadge'
import './ActivityDetailsHero.css'

interface ActivityDetailsHeroProps {
  activity: ActivityDetails
}

function getPriceLabel(activity: ActivityDetails) {
  if (activity.price_type === 'FREE') {
    return 'Bezpłatna'
  }

  if (activity.price_amount !== null && activity.currency !== null) {
    return `${activity.price_amount} ${activity.currency}`
  }

  return 'Płatna'
}

function ActivityDetailsHero({ activity }: ActivityDetailsHeroProps) {
  const categoryPresentation = getActivityCategoryPresentation(
    activity.category.slug,
  )
  const CategoryIcon = categoryPresentation.icon

  return (
    <section
      className={`activity-details-hero activity-details-hero--${categoryPresentation.variant}`}
      aria-labelledby="activity-title"
    >
      <div className="activity-details-hero__chips">
        <Chip
          className="activity-details-hero__category"
          icon={<CategoryIcon />}
          label={activity.category.name}
        />
        <Chip label={getPriceLabel(activity)} variant="outlined" />
        <ActivityStatusBadge status={activity.status} />
      </div>

      <Typography
        id="activity-title"
        className="activity-details-hero__title"
        component="h1"
        variant="h2"
      >
        {activity.title}
      </Typography>
      <Typography
        className="activity-details-hero__description"
        color="text.secondary"
      >
        {activity.description}
      </Typography>
    </section>
  )
}

export default ActivityDetailsHero
