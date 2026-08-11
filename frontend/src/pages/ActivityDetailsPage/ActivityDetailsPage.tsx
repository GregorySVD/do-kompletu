import { Button, Card, CardContent, Chip, Typography } from '@mui/material'
import { Link, useParams } from 'react-router-dom'
import { mockActivities } from '../../data/mockActivities'
import './ActivityDetailsPage.css'

const dateFormatter = new Intl.DateTimeFormat('pl-PL', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function ActivityDetailsPage() {
  const { activityId } = useParams()
  const activity = mockActivities.find((item) => item.id === activityId)

  if (!activity) {
    return (
      <main className="activity-details-page">
        <Button component={Link} to="/">
          Wróć do listy
        </Button>

        <Card variant="outlined" className="activity-details-page__not-found">
          <CardContent>
            <Typography component="h1" variant="h5" gutterBottom>
              Nie znaleziono aktywności
            </Typography>
            <Typography color="text.secondary">
              Aktywność o podanym identyfikatorze nie istnieje.
            </Typography>
          </CardContent>
        </Card>
      </main>
    )
  }

  const missingToMinimum = Math.max(
    activity.min_participants - activity.participant_count,
    0,
  )
  const hasParticipantLimit = activity.max_participants !== null

  return (
    <main className="activity-details-page">
      <Button component={Link} to="/">
        Wróć do listy
      </Button>

      <Card variant="outlined" className="activity-details-page__summary">
        <CardContent>
          <div className="activity-details-page__chips">
            <Chip label={activity.category.name} size="small" />
            <Chip
              label={
                activity.price_type === 'FREE'
                  ? 'Bezpłatna'
                  : `${activity.price_amount} ${activity.currency}`
              }
              size="small"
              color={activity.price_type === 'FREE' ? 'success' : 'default'}
              variant="outlined"
            />
          </div>

          <Typography component="h1" variant="h4" gutterBottom>
            {activity.title}
          </Typography>
          <Typography>{activity.description}</Typography>

          <div className="activity-details-page__action">
            <Button
              variant="contained"
              disabled={!activity.permissions.can_join}
            >
              Dołącz do aktywności
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="activity-details-page__grid">
        <Card component="section" variant="outlined">
          <CardContent>
            <Typography component="h2" variant="h6" gutterBottom>
              Termin
            </Typography>
            <Typography>
              Od: {dateFormatter.format(new Date(activity.start_at))}
            </Typography>
            <Typography>
              Do: {dateFormatter.format(new Date(activity.end_at))}
            </Typography>
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
                  Wolne miejsca: {activity.available_slots}
                </Typography>
                <Typography color="text.secondary">
                  Lista rezerwowa: {activity.waitlist_count}
                </Typography>
              </>
            )}
          </CardContent>
        </Card>

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
            <div className="activity-details-page__chips">
              {activity.tags.map((tag) => (
                <Chip key={tag.id} label={tag.name} size="small" />
              ))}
            </div>
          </CardContent>
        </Card>

        <Card component="section" variant="outlined">
          <CardContent>
            <Typography component="h2" variant="h6" gutterBottom>
              Potwierdzenie udziału
            </Typography>
            <Typography>
              Od:{' '}
              {dateFormatter.format(new Date(activity.confirmation_opens_at))}
            </Typography>
            <Typography>
              Do:{' '}
              {dateFormatter.format(
                new Date(activity.confirmation_deadline_at),
              )}
            </Typography>
          </CardContent>
        </Card>

        <Card component="section" variant="outlined">
          <CardContent>
            <Typography component="h2" variant="h6" gutterBottom>
              Check-in
            </Typography>
            <Typography>
              Od: {dateFormatter.format(new Date(activity.checkin_opens_at))}
            </Typography>
            <Typography>
              Do: {dateFormatter.format(new Date(activity.checkin_closes_at))}
            </Typography>
            <Typography color="text.secondary">
              Promień: {activity.checkin_radius_m} m
            </Typography>
          </CardContent>
        </Card>
      </div>
    </main>
  )
}

export default ActivityDetailsPage
