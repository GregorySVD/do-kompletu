import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import axios from 'axios'
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
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { useAuth } from '../../../context/auth'
import type { LoginFormValues } from '../../../types/auth'
import './LoginForm.css'

const loginSchema = z.object({
  identifier: z
    .string()
    .min(1, 'Wprowadź e-mail lub nazwę użytkownika.')
    .max(320, 'E-mail lub nazwa użytkownika może mieć maksymalnie 320 znaków'),
  password: z
    .string()
    .min(1, 'Hasło jest wymagane')
    .max(128, 'Hasło może mieć maksymalnie 128 znaków'),
})

const defaultValues: LoginFormValues = {
  identifier: '',
  password: '',
}

interface LoginLocationState {
  from?: {
    hash?: unknown
    pathname?: unknown
    search?: unknown
  }
}

function getSafePostLoginPath(state: unknown) {
  if (typeof state !== 'object' || state === null) {
    return '/'
  }

  const { from } = state as LoginLocationState

  if (typeof from !== 'object' || from === null) {
    return '/'
  }

  const { hash, pathname, search } = from

  if (
    typeof pathname !== 'string' ||
    !pathname.startsWith('/') ||
    pathname.startsWith('//') ||
    pathname.includes('\\') ||
    pathname === '/login'
  ) {
    return '/'
  }

  const safeSearch =
    typeof search === 'string' && (search === '' || search.startsWith('?'))
      ? search
      : ''
  const safeHash =
    typeof hash === 'string' && (hash === '' || hash.startsWith('#'))
      ? hash
      : ''

  return `${pathname}${safeSearch}${safeHash}`
}

function LoginForm() {
  const [apiError, setApiError] = useState<string | null>(null)
  const { login } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues,
  })

  async function submitForm(values: LoginFormValues) {
    setApiError(null)

    try {
      await login(values)
      navigate(getSafePostLoginPath(location.state), { replace: true })
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        setApiError('Nieprawidłowe dane logowania.')
      } else if (axios.isAxiosError(error) && !error.response) {
        setApiError('Nie udało się połączyć z serwerem.')
      } else {
        setApiError('Nie udało się zalogować. Spróbuj ponownie.')
      }
    }
  }

  return (
    <>
      {apiError && <Alert severity="error">{apiError}</Alert>}

      <Card variant="outlined" className="login-card">
        <CardContent>
          <form
            className="login-form"
            noValidate
            onSubmit={handleSubmit(submitForm)}
          >
            <TextField
              label="E-mail lub nazwa użytkownika"
              type="text"
              autoComplete="username"
              error={Boolean(errors.identifier)}
              helperText={errors.identifier?.message}
              {...register('identifier')}
            />

            <TextField
              label="Hasło"
              type="password"
              autoComplete="current-password"
              error={Boolean(errors.password)}
              helperText={errors.password?.message}
              {...register('password')}
            />

            <Button
              type="submit"
              variant="contained"
              size="large"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Logowanie...' : 'Zaloguj się'}
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
    </>
  )
}

export default LoginForm
