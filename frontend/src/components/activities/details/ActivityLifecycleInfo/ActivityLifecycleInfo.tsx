import { Card, CardContent, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'
import { formatDateTime } from '../../../../utils/dateFormat'

interface ActivityLifecycleInfoProps {
  activity: ActivityDetails
}

function ActivityLifecycleInfo({ activity }: ActivityLifecycleInfoProps) {
  const confirmationOpensAt = activity.confirmation_opens_at
  const confirmationDeadlineAt = activity.confirmation_deadline_at
  const checkInOpensAt = activity.checkin_opens_at
  const checkInClosesAt = activity.checkin_closes_at
  const checkInRadius = activity.checkin_radius_m
  const hasConfirmationWindow =
    confirmationOpensAt !== null && confirmationDeadlineAt !== null
  const hasCheckInWindow =
    checkInOpensAt !== null &&
    checkInClosesAt !== null &&
    checkInRadius !== null

  return (
    <>
      <Card component="section" variant="outlined">
        <CardContent>
          <Typography component="h2" variant="h6" gutterBottom>
            Potwierdzenie udziału
          </Typography>
          {hasConfirmationWindow ? (
            <>
              <Typography>Od: {formatDateTime(confirmationOpensAt)}</Typography>
              <Typography>
                Do: {formatDateTime(confirmationDeadlineAt)}
              </Typography>
            </>
          ) : (
            <Typography color="text.secondary">
              Potwierdzanie udziału nie jest jeszcze dostępne.
            </Typography>
          )}
        </CardContent>
      </Card>

      <Card component="section" variant="outlined">
        <CardContent>
          <Typography component="h2" variant="h6" gutterBottom>
            Check-in
          </Typography>
          {hasCheckInWindow ? (
            <>
              <Typography>Od: {formatDateTime(checkInOpensAt)}</Typography>
              <Typography>Do: {formatDateTime(checkInClosesAt)}</Typography>
              <Typography color="text.secondary">
                Promień: {checkInRadius} m
              </Typography>
            </>
          ) : (
            <Typography color="text.secondary">
              Check-in nie jest jeszcze dostępny.
            </Typography>
          )}
        </CardContent>
      </Card>
    </>
  )
}

export default ActivityLifecycleInfo
