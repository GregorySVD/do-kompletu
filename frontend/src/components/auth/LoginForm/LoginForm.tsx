import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  AccountCircleOutlined,
  LockOutlined,
  LoginRounded,
} from '@mui/icons-material'
import axios from 'axios'
import {
  Alert,
  Card,
  CardContent,
  Link as MuiLink,
  Typography,
} from '@mui/material'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../../context/auth'
import type { LoginFormValues } from '../../../types/auth'
import {
  loginFormDefaultValues,
  loginFormSchema,
} from '../../../validation/authFormSchemas'
import AuthPrimaryButton from '../AuthPrimaryButton/AuthPrimaryButton'
import AuthTextField from '../AuthTextField/AuthTextField'
import '../AuthForm/AuthForm.css'

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
    formState: { errors, isSubmitting, isValid },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginFormSchema),
    defaultValues: loginFormDefaultValues,
    mode: 'onChange',
    reValidateMode: 'onChange',
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
    <Card variant="outlined" className="auth-card">
      <CardContent className="auth-card__content">
        {apiError && (
          <Alert className="auth-form__error" severity="error">
            {apiError}
          </Alert>
        )}

        <form
          className="auth-form"
          noValidate
          onSubmit={handleSubmit(submitForm)}
        >
          <AuthTextField
            label="E-mail lub nazwa użytkownika"
            autoComplete="username"
            disabled={isSubmitting}
            errorMessage={errors.identifier?.message}
            registration={register('identifier')}
            startIcon={<AccountCircleOutlined aria-hidden="true" />}
          />

          <AuthTextField
            label="Hasło"
            type="password"
            autoComplete="current-password"
            disabled={isSubmitting}
            errorMessage={errors.password?.message}
            registration={register('password')}
            startIcon={<LockOutlined aria-hidden="true" />}
          />

          <AuthPrimaryButton
            type="submit"
            disabled={isSubmitting || !isValid}
            startIcon={<LoginRounded aria-hidden="true" />}
          >
            {isSubmitting ? 'Logowanie...' : 'Zaloguj się'}
          </AuthPrimaryButton>

          <Typography className="auth-form__navigation">
            <span>Nie masz jeszcze konta?</span>
            <MuiLink
              className="auth-form__secondary-link"
              component={Link}
              to="/register"
            >
              Utwórz konto
            </MuiLink>
          </Typography>
        </form>
      </CardContent>
    </Card>
  )
}

export default LoginForm
