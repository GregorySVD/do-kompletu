import { Chip, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'
import './ActivityTagsCard.css'

interface ActivityTagsCardProps {
  activity: ActivityDetails
}

function ActivityTagsCard({ activity }: ActivityTagsCardProps) {
  return (
    <section
      className="activity-tags-card"
      aria-labelledby="activity-tags-title"
    >
      <div className="activity-tags-card__heading">
        <span className="activity-tags-card__heading-icon" aria-hidden="true">
          #
        </span>
        <Typography
          id="activity-tags-title"
          className="activity-tags-card__title"
          component="h2"
          variant="h5"
        >
          Tagi
        </Typography>
      </div>
      {activity.tags.length > 0 ? (
        <div className="activity-tags-card__list">
          {activity.tags.map((tag) => (
            <Chip
              key={tag.id}
              className="activity-tags-card__tag"
              label={tag.name}
              size="small"
            />
          ))}
        </div>
      ) : (
        <Typography
          className="activity-tags-card__empty"
          variant="body2"
          color="text.secondary"
        >
          Brak dodatkowych tagów
        </Typography>
      )}
    </section>
  )
}

export default ActivityTagsCard
