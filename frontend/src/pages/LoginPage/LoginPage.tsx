import { Button, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import LoginForm from '../../components/auth/LoginForm/LoginForm'
import './LoginPage.css'

function LoginPage() {
  return (
    <main className="login-page">
      <div className="login-page__heading">
        <div>
          <Typography component="h1" variant="h4">
            Zaloguj się
          </Typography>
          <Typography color="text.secondary">
            Wprowadź dane swojego konta.
          </Typography>
        </div>

        <Button component={Link} to="/">
          Wróć do strony głównej
        </Button>
      </div>

      <LoginForm />
    </main>
  )
}

export default LoginPage
