import { Avatar, Card, CardContent, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'
import './ActivityOrganizerCard.css'

interface ActivityOrganizerCardProps {
  activity: ActivityDetails
}

function ActivityOrganizerCard({ activity }: ActivityOrganizerCardProps) {
  const { organizer } = activity
  const avatarFallback = organizer.display_name.charAt(0).toUpperCase()

  return (
    <Card
      component="section"
      variant="outlined"
      className="activity-organizer-card"
    >
      <CardContent>
        <Typography component="h2" variant="h6">
          Organizator
        </Typography>
        <div className="activity-organizer-card__profile">
          <Avatar
            className="activity-organizer-card__avatar"
            src={organizer.avatar_url ?? undefined}
            alt={organizer.display_name}
          >
            {avatarFallback}
          </Avatar>
          <div>
            <Typography className="activity-organizer-card__name">
              {organizer.display_name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Organizator aktywności
            </Typography>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default ActivityOrganizerCard
