import { Chip, type ChipProps } from '@mui/material'
import { getActivityCategoryPresentation } from '../../config/activityCategoryPresentation'
import './ActivityCategoryBadge.css'

interface ActivityCategoryBadgeProps {
  category: {
    name: string
    slug: string
  }
  className?: string
  size?: ChipProps['size']
}

function ActivityCategoryBadge({
  category,
  className,
  size,
}: ActivityCategoryBadgeProps) {
  const presentation = getActivityCategoryPresentation(category.slug)
  const CategoryIcon = presentation.icon

  return (
    <Chip
      className={[
        'activity-category-badge',
        `activity-category-badge--${presentation.variant}`,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      icon={
        presentation.pixelIconSrc ? (
          <img
            className="activity-category-badge__image"
            src={presentation.pixelIconSrc}
            alt=""
            width="32"
            height="32"
          />
        ) : (
          <CategoryIcon />
        )
      }
      label={category.name}
      size={size}
    />
  )
}

export default ActivityCategoryBadge
