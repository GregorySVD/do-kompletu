import { Card, CardContent, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'

interface ActivityParticipantsInfoProps {
  activity: ActivityDetails
}

function ActivityParticipantsInfo({ activity }: ActivityParticipantsInfoProps) {
  const missingToMinimum = Math.max(
    activity.min_participants - activity.participant_count,
    0,
  )
  const hasParticipantLimit = activity.max_participants !== null

  return (
    <Card component="section" variant="outlined">
      <CardContent>
        <Typography component="h2" variant="h6" gutterBottom>
          Uczestnicy
        </Typography>
        <Typography>
          Liczba uczestników: {activity.participant_count}
        </Typography>
        <Typography color="text.secondary">
          Minimalna liczba uczestników: {activity.min_participants}
        </Typography>
        <Typography color="text.secondary">
          {missingToMinimum > 0
            ? `Brakuje ${missingToMinimum} osób do kompletu`
            : 'Komplet zebrany'}
        </Typography>
        <Typography color="text.secondary">
          Maksymalna liczba uczestników:{' '}
          {hasParticipantLimit ? activity.max_participants : 'Brak limitu'}
        </Typography>
        {hasParticipantLimit && (
          <>
            <Typography color="text.secondary">
              Wolne miejsca: {activity.available_slots ?? 'Brak danych'}
            </Typography>
            <Typography color="text.secondary">
              Lista rezerwowa: {activity.waitlist_count}
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  )
}

export default ActivityParticipantsInfo
