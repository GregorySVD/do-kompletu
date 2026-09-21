import { Button, Card, CardContent, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import './RegisterSuccessPage.css'

function RegisterSuccessPage() {
  return (
    <main className="register-success-page">
      <Card variant="outlined" className="register-success-card">
        <CardContent className="register-success-card__content">
          <Typography component="h1" variant="h4">
            Brawo! Twoje konto zostało utworzone.
          </Typography>

          <Typography color="text.secondary">
            Teraz zaloguj się i zacznij w pełni korzystać z DoKompletu.
          </Typography>

          <div className="register-success-card__actions">
            <Button
              component={Link}
              to="/login"
              variant="contained"
              size="large"
            >
              Zaloguj się
            </Button>
            <Button component={Link} to="/">
              Wróć do strony głównej
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  )
}

export default RegisterSuccessPage
