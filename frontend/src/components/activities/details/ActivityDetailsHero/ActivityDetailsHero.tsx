import { Chip, Typography } from '@mui/material'
import {
  getActivityCategoryPresentation,
  type ActivityCategoryVisualVariant,
} from '../../../../config/activityCategoryPresentation'
import type { ActivityDetails } from '../../../../types/activity'
import ActivityStatusBadge from '../ActivityStatusBadge/ActivityStatusBadge'
import './ActivityDetailsHero.css'

interface ActivityDetailsHeroProps {
  activity: ActivityDetails
}

const featuredCategoryAssets: Partial<
  Record<ActivityCategoryVisualVariant, { badge: string; hero: string }>
> = {
  music: {
    badge: '/icons/icons8-rock-music-32.png',
    hero: '/icons/icons8-rock-music-64.png',
  },
  'team-sport': {
    badge: '/icons/icons8-sport-32.png',
    hero: '/icons/icons8-sport-64.png',
  },
  'board-games': {
    badge: '/icons/icons8-dice-32.png',
    hero: '/icons/icons8-dice-64.png',
  },
  gaming: {
    badge: '/icons/icons8-games-32.png',
    hero: '/icons/icons8-games-64.png',
  },
  study: {
    badge: '/icons/icons8-book-stack-32.png',
    hero: '/icons/icons8-book-stack-64.png',
  },
  technology: {
    badge: '/icons/icons8-technology-32.png',
    hero: '/icons/icons8-technology-64.png',
  },
  creative: {
    badge: '/icons/icons8-painting-32.png',
    hero: '/icons/icons8-painting-64.png',
  },
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
  const CategoryIcon = categoryPresentation.icon
  const featuredAssets =
    featuredCategoryAssets[categoryPresentation.variant] ?? null
  const isFeatured = featuredCategoryVariants.has(categoryPresentation.variant)
  const priceVariant = activity.price_type === 'FREE' ? 'free' : 'paid'

  return (
    <section
      className={`activity-details-hero activity-details-hero--${categoryPresentation.variant}${isFeatured ? ' activity-details-hero--featured' : ''}${featuredAssets ? ' activity-details-hero--with-visual' : ''}`}
      aria-labelledby="activity-title"
    >
      <div className="activity-details-hero__content">
        <div className="activity-details-hero__chips">
          <Chip
            className="activity-details-hero__category"
            icon={
              featuredAssets ? (
                <img
                  className="activity-details-hero__category-image"
                  src={featuredAssets.badge}
                  alt=""
                  width="32"
                  height="32"
                />
              ) : (
                <CategoryIcon />
              )
            }
            label={activity.category.name}
          />
          <Chip
            className={`activity-details-hero__price activity-details-hero__price--${priceVariant}`}
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

      {featuredAssets && (
        <div
          className="activity-details-hero__category-visual"
          aria-hidden="true"
        >
          <img
            className="activity-details-hero__category-image-large"
            src={featuredAssets.hero}
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
