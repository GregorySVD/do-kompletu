import { Card, CardContent, Chip, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'

interface ActivityOrganizerInfoProps {
  activity: ActivityDetails
}

function ActivityOrganizerInfo({ activity }: ActivityOrganizerInfoProps) {
  return (
    <>
      <Card component="section" variant="outlined">
        <CardContent>
          <Typography component="h2" variant="h6" gutterBottom>
            Organizator
          </Typography>
          <Typography>{activity.organizer.display_name}</Typography>
        </CardContent>
      </Card>

      <Card component="section" variant="outlined">
        <CardContent>
          <Typography component="h2" variant="h6" gutterBottom>
            Tagi
          </Typography>
          {activity.tags.length > 0 ? (
            <div className="activity-details-content__chips">
              {activity.tags.map((tag) => (
                <Chip key={tag.id} label={tag.name} size="small" />
              ))}
            </div>
          ) : (
            <Typography color="text.secondary">Brak tagów</Typography>
          )}
        </CardContent>
      </Card>
    </>
  )
}

export default ActivityOrganizerInfo
