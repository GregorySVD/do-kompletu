import { useState } from 'react'
import { Add, Event, Explore } from '@mui/icons-material'
import axios from 'axios'
import {
  Alert,
  Avatar,
  Button,
  Card,
  CardContent,
  Typography,
} from '@mui/material'
import { Link } from 'react-router-dom'
import ActivityCard from '../../components/ActivityCard/ActivityCard'
import EditProfileDialog from '../../components/profile/EditProfileDialog/EditProfileDialog'
import QueryStateMessage from '../../components/system/QueryStateMessage/QueryStateMessage'
import { useAuth } from '../../context/auth'
import { useMyActivitiesQuery } from '../../hooks/queries/useMyActivitiesQuery'
import type { ActivityDetails } from '../../types/activity'
import './ProfilePage.css'

function getParticipationStatusLabel(activity: ActivityDetails) {
  switch (activity.current_user_participation?.status) {
    case 'JOINED':
      return 'Zapisany'
    case 'CONFIRMED':
      return 'Potwierdzony'
    case 'CHECKED_IN':
      return 'Check-in wykonany'
    default:
      return undefined
  }
}

function ProfilePage() {
  const { user } = useAuth()
  const upcomingActivitiesQuery = useMyActivitiesQuery('joined', 'upcoming')
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)

  if (!user) {
    return null
  }

  const avatarFallback = user.display_name.charAt(0).toUpperCase()

  function openEditDialog() {
    setShowSuccess(false)
    setIsEditDialogOpen(true)
  }

  function handleProfileUpdated() {
    setIsEditDialogOpen(false)
    setShowSuccess(true)
  }

  return (
    <main className="profile-page">
      <Typography component="h1" variant="h4">
        Twój profil
      </Typography>

      {showSuccess && (
        <Alert className="profile-page__success" severity="success">
          Profil został zaktualizowany.
        </Alert>
      )}

      <div className="profile-page__overview">
        <section aria-labelledby="profile-summary-title">
          <Card variant="outlined" className="profile-card">
            <CardContent className="profile-card__content">
              <Avatar
                className="profile-card__avatar"
                src={user.avatar_url ?? undefined}
                alt={user.display_name}
              >
                {avatarFallback}
              </Avatar>

              <div className="profile-card__details">
                <Typography
                  id="profile-summary-title"
                  component="h2"
                  variant="h5"
                >
                  {user.display_name}
                </Typography>
                <Typography color="text.secondary">{user.email}</Typography>
                <Typography variant="body2" color="text.secondary">
                  Punkty: {user.points_total}
                </Typography>
                <Button
                  className="profile-card__edit"
                  variant="contained"
                  onClick={openEditDialog}
                >
                  Edytuj profil
                </Button>
              </div>
            </CardContent>
          </Card>
        </section>

        <section
          className="profile-quick-actions"
          aria-labelledby="profile-quick-actions-title"
        >
          <Typography
            id="profile-quick-actions-title"
            component="h2"
            variant="h5"
          >
            Szybkie akcje
          </Typography>
          <div className="profile-quick-actions__list">
            <Button
              className="profile-quick-actions__button"
              component={Link}
              to="/"
              variant="outlined"
              startIcon={<Explore />}
            >
              Odkrywaj aktywności
            </Button>
            <Button
              className="profile-quick-actions__button"
              component={Link}
              to="/activities/new"
              variant="outlined"
              startIcon={<Add />}
            >
              Dodaj aktywność
            </Button>
            <Button
              className="profile-quick-actions__button"
              component={Link}
              to="/profile/activities"
              variant="outlined"
              startIcon={<Event />}
            >
              Moje aktywności
            </Button>
          </div>
        </section>
      </div>

      <section
        className="profile-upcoming"
        aria-labelledby="profile-upcoming-title"
      >
        <Typography id="profile-upcoming-title" component="h2" variant="h5">
          Twoje najbliższe aktywności
        </Typography>

        {upcomingActivitiesQuery.isPending && (
          <QueryStateMessage
            message="Ładowanie nadchodzących aktywności..."
            isLoading
          />
        )}

        {upcomingActivitiesQuery.isError &&
          (axios.isCancel(upcomingActivitiesQuery.error) ? (
            <QueryStateMessage
              message="Ładowanie nadchodzących aktywności..."
              isLoading
            />
          ) : (
            <QueryStateMessage
              message="Nie udało się pobrać nadchodzących aktywności."
              isRetrying={upcomingActivitiesQuery.isFetching}
              onRetry={() => void upcomingActivitiesQuery.refetch()}
            />
          ))}

        {upcomingActivitiesQuery.isSuccess &&
          (upcomingActivitiesQuery.data.length > 0 ? (
            <>
              <div className="profile-upcoming__list">
                {upcomingActivitiesQuery.data.slice(0, 3).map((activity) => (
                  <ActivityCard
                    key={activity.id}
                    activity={activity}
                    statusLabel={getParticipationStatusLabel(activity)}
                  />
                ))}
              </div>
              <Button
                className="profile-upcoming__all"
                component={Link}
                to="/profile/activities"
              >
                Zobacz wszystkie moje aktywności
              </Button>
            </>
          ) : (
            <div className="profile-upcoming__empty">
              <Typography color="text.secondary">
                Nie masz jeszcze nadchodzących aktywności.
              </Typography>
              <Button component={Link} to="/" variant="outlined">
                Znajdź aktywność
              </Button>
            </div>
          ))}
      </section>

      {isEditDialogOpen && (
        <EditProfileDialog
          user={user}
          onClose={() => setIsEditDialogOpen(false)}
          onUpdated={handleProfileUpdated}
        />
      )}
    </main>
  )
}

export default ProfilePage
