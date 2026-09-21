import { Avatar, Button, Card, CardContent, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/auth'
import './ProfilePage.css'

function ProfilePage() {
  const { user } = useAuth()

  if (!user) {
    return null
  }

  const avatarFallback = user.display_name.charAt(0).toUpperCase()

  return (
    <main className="profile-page">
      <Typography component="h1" variant="h4">
        Twój profil
      </Typography>

      <Card variant="outlined" className="profile-card">
        <CardContent className="profile-card__content">
          <Avatar
            className="profile-card__avatar"
            src={user.avatar_url ?? undefined}
            alt={user.display_name}
          >
            {avatarFallback}
          </Avatar>

          <div>
            <Typography component="h2" variant="h5">
              {user.display_name}
            </Typography>
            <Typography color="text.secondary">{user.email}</Typography>
            <Typography color="text.secondary">
              Punkty: {user.points_total}
            </Typography>
            <Button
              className="profile-card__activities-link"
              component={Link}
              to="/profile/activities"
              variant="outlined"
            >
              Moje aktywności
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  )
}

export default ProfilePage
