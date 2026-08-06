import { Button, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import './NotFoundPage.css'

function NotFoundPage() {
  return (
    <main className="not-found-page">
      <Typography component="h1" variant="h4" gutterBottom>
        Nie znaleziono strony
      </Typography>
      <Typography color="text.secondary">
        Podany adres nie prowadzi do istniejącej strony.
      </Typography>
      <Button component={Link} to="/" variant="contained">
        Wróć do strony głównej
      </Button>
    </main>
  )
}

export default NotFoundPage
