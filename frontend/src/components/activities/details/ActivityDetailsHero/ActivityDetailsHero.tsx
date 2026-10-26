import { Chip, Typography } from '@mui/material'
import {
  getActivityCategoryPresentation,
  type ActivityCategoryVisualVariant,
} from '../../../../config/activityCategoryPresentation'
import type { ActivityDetails } from '../../../../types/activity'
import ActivityCategoryBadge from '../../../ActivityCategoryBadge/ActivityCategoryBadge'
import ActivityStatusBadge from '../ActivityStatusBadge/ActivityStatusBadge'
import './ActivityDetailsHero.css'

interface ActivityDetailsHeroProps {
  activity: ActivityDetails
}

const featuredCategoryVariants = new Set<ActivityCategoryVisualVariant>([
  'music',
  'team-sport',
  'board-games',
  'rpg',
  'gaming',
  'study',
  'technology',
  'creative',
])

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
  const categoryHeroIconSrc = categoryPresentation.pixelHeroIconSrc
  const isFeatured = featuredCategoryVariants.has(categoryPresentation.variant)
  const priceVariant = activity.price_type === 'FREE' ? 'free' : 'paid'
  const priceIconSrc =
    activity.price_type === 'FREE'
      ? '/icons/icons8-confetti-64.png'
      : '/icons/icons8-money-64.png'

  return (
    <section
      className={`activity-details-hero activity-details-hero--${categoryPresentation.variant}${isFeatured ? ' activity-details-hero--featured' : ''}${categoryHeroIconSrc ? ' activity-details-hero--with-visual' : ''}`}
      aria-labelledby="activity-title"
    >
      <div className="activity-details-hero__content">
        <div className="activity-details-hero__chips">
          <ActivityCategoryBadge category={activity.category} />
          <Chip
            className={`activity-details-hero__price activity-details-hero__price--${priceVariant}`}
            icon={
              <img
                className="activity-details-hero__price-image"
                src={priceIconSrc}
                alt=""
                width="64"
                height="64"
              />
            }
            label={getPriceLabel(activity)}
            variant="outlined"
          />
          <ActivityStatusBadge
            className="activity-details-hero__status"
            status={activity.status}
          />
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
      </div>

      {categoryHeroIconSrc && (
        <div
          className="activity-details-hero__category-visual"
          aria-hidden="true"
        >
          <img
            className="activity-details-hero__category-image-large"
            src={categoryHeroIconSrc}
            alt=""
            width="64"
            height="64"
          />
        </div>
      )}
    </section>
  )
}

export default ActivityDetailsHero
