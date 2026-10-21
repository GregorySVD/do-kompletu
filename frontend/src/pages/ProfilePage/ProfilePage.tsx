import { useState } from 'react'
import {
  Alert,
  Avatar,
  Button,
  Card,
  CardContent,
  Typography,
} from '@mui/material'
import { Link } from 'react-router-dom'
import EditProfileDialog from '../../components/profile/EditProfileDialog/EditProfileDialog'
import { useAuth } from '../../context/auth'
import './ProfilePage.css'

function ProfilePage() {
  const { user } = useAuth()
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
            <div className="profile-card__actions">
              <Button variant="contained" onClick={openEditDialog}>
                Edytuj profil
              </Button>
              <Button
                component={Link}
                to="/profile/activities"
                variant="outlined"
              >
                Moje aktywności
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

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
