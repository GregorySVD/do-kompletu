import { Card, CardContent, Chip, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'
import './ActivityDetailsSummary.css'

interface ActivityDetailsSummaryProps {
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

function ActivityDetailsSummary({ activity }: ActivityDetailsSummaryProps) {
  return (
    <Card variant="outlined" className="activity-details-summary">
      <CardContent>
        <div className="activity-details-content__chips">
          <Chip label={activity.category.name} size="small" />
          <Chip
            label={getPriceLabel(activity)}
            size="small"
            color={activity.price_type === 'FREE' ? 'success' : 'default'}
            variant="outlined"
          />
          {activity.status === 'CANCELLED' && (
            <Chip label="Anulowana" size="small" color="error" />
          )}
        </div>

        <Typography component="h1" variant="h4" gutterBottom>
          {activity.title}
        </Typography>
        <Typography>{activity.description}</Typography>
      </CardContent>
    </Card>
  )
}

export default ActivityDetailsSummary
