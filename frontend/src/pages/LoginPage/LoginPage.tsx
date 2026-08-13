import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Link as MuiLink,
  TextField,
  Typography,
} from '@mui/material'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'
import type { LoginFormValues } from '../../types/auth'
import './LoginPage.css'

const loginSchema = z.object({
  email: z
    .string()
    .min(1, 'Adres e-mail jest wymagany')
    .email('Podaj poprawny adres e-mail'),
  password: z
    .string()
    .min(1, 'Hasło jest wymagane')
    .min(8, 'Hasło musi mieć co najmniej 8 znaków'),
})

const defaultValues: LoginFormValues = {
  email: '',
  password: '',
}

function LoginPage() {
  const [isSubmitted, setIsSubmitted] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues,
  })

  function submitForm() {
    setIsSubmitted(true)
  }

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

      {isSubmitted && (
        <Alert severity="success">
          Formularz jest poprawny. Logowanie zostanie uruchomione po integracji
          z API.
        </Alert>
      )}

      <Card variant="outlined" className="login-card">
        <CardContent>
          <form
            className="login-form"
            noValidate
            onSubmit={handleSubmit(submitForm)}
          >
            <TextField
              label="Adres e-mail"
              type="email"
              autoComplete="email"
              error={Boolean(errors.email)}
              helperText={errors.email?.message}
              {...register('email')}
            />

            <TextField
              label="Hasło"
              type="password"
              autoComplete="current-password"
              error={Boolean(errors.password)}
              helperText={errors.password?.message}
              {...register('password')}
            />

            <Button type="submit" variant="contained" size="large">
              Zaloguj się
            </Button>

            <Typography className="login-form__navigation">
              Nie masz konta?{' '}
              <MuiLink component={Link} to="/register">
                Zarejestruj się
              </MuiLink>
            </Typography>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}

export default LoginPage
