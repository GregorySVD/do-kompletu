import { Card, CardContent, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'
import { formatDateTime } from '../../../../utils/dateFormat'

interface ActivityScheduleLocationProps {
  activity: ActivityDetails
}

function ActivityScheduleLocation({ activity }: ActivityScheduleLocationProps) {
  return (
    <>
      <Card component="section" variant="outlined">
        <CardContent>
          <Typography component="h2" variant="h6" gutterBottom>
            Termin
          </Typography>
          <Typography>Od: {formatDateTime(activity.start_at)}</Typography>
          <Typography>Do: {formatDateTime(activity.end_at)}</Typography>
        </CardContent>
      </Card>

      <Card component="section" variant="outlined">
        <CardContent>
          <Typography component="h2" variant="h6" gutterBottom>
            Miejsce
          </Typography>
          <Typography>{activity.location_name}</Typography>
          <Typography color="text.secondary">{activity.address}</Typography>
        </CardContent>
      </Card>
    </>
  )
}

export default ActivityScheduleLocation
