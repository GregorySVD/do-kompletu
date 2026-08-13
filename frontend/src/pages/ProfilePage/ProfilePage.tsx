import { Avatar, Card, CardContent, Typography } from '@mui/material'
import { mockCurrentUser } from '../../data/mockCurrentUser'
import './ProfilePage.css'

function ProfilePage() {
  const avatarFallback = mockCurrentUser.display_name.charAt(0).toUpperCase()

  return (
    <main className="profile-page">
      <Typography component="h1" variant="h4">
        Twój profil
      </Typography>

      <Card variant="outlined" className="profile-card">
        <CardContent className="profile-card__content">
          <Avatar
            className="profile-card__avatar"
            src={mockCurrentUser.avatar_url ?? undefined}
            alt={mockCurrentUser.display_name}
          >
            {avatarFallback}
          </Avatar>

          <div>
            <Typography component="h2" variant="h5">
              {mockCurrentUser.display_name}
            </Typography>
            <Typography color="text.secondary">
              {mockCurrentUser.email}
            </Typography>
          </div>
        </CardContent>
      </Card>
    </main>
  )
}

export default ProfilePage
