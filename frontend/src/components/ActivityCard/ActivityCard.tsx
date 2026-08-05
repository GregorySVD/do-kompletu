import { Card, CardContent, Chip, Typography } from '@mui/material'
import type { Activity } from '../../types/activity'
import './ActivityCard.css'

interface ActivityCardProps {
  activity: Activity
}

const dateFormatter = new Intl.DateTimeFormat('pl-PL', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function ActivityCard({ activity }: ActivityCardProps) {
  const missingParticipants =
    activity.max_participants - activity.participant_count

  return (
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

          <Chip label={activity.category} size="small" />
        </div>

        <Typography className="activity-card__location">
          {activity.location_name}
        </Typography>

        <div className="activity-card__details">
          <Chip
            label={activity.price_type === 'free' ? 'Bezpłatna' : 'Płatna'}
            size="small"
            color={activity.price_type === 'free' ? 'success' : 'default'}
            variant="outlined"
          />

          <div className="activity-card__participants">
            <Typography>
              {activity.participant_count} / {activity.max_participants}{' '}
              uczestników
            </Typography>
            <Typography color="text.secondary">
              Brakuje {missingParticipants} osób
            </Typography>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default ActivityCard
