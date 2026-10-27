import { useEffect, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  AlternateEmailRounded,
  CheckCircleRounded,
  ErrorOutlineRounded,
  HowToRegRounded,
  LockOutlined,
  PersonAddAltOutlined,
  RadioButtonUncheckedRounded,
} from '@mui/icons-material'
import {
  Alert,
  Card,
  CardContent,
  Link as MuiLink,
  Typography,
} from '@mui/material'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../../context/auth'
import type { RegisterFormValues } from '../../../types/auth'
import { getRegistrationErrorMessage } from '../../../utils/registrationError'
import {
  registerFormDefaultValues,
  registerFormSchema,
} from '../../../validation/authFormSchemas'
import AuthPrimaryButton from '../AuthPrimaryButton/AuthPrimaryButton'
import AuthTextField from '../AuthTextField/AuthTextField'
import '../AuthForm/AuthForm.css'

type RequirementState = 'invalid' | 'pending' | 'valid'

interface PasswordRequirementProps {
  label: string
  state: RequirementState
}

function PasswordRequirement({ label, state }: PasswordRequirementProps) {
  const RequirementIcon =
    state === 'valid'
      ? CheckCircleRounded
      : state === 'invalid'
        ? ErrorOutlineRounded
        : RadioButtonUncheckedRounded

  return (
    <li className={`auth-form__requirement auth-form__requirement--${state}`}>
      <RequirementIcon aria-hidden="true" />
      <span>{label}</span>
    </li>
  )
}

function RegisterForm() {
  const [apiError, setApiError] = useState<string | null>(null)
  const { register: registerUser } = useAuth()
  const navigate = useNavigate()
  const {
    control,
    register,
    handleSubmit,
    setError,
    trigger,
    formState: { errors, isSubmitting, isValid },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerFormSchema),
    defaultValues: registerFormDefaultValues,
    mode: 'onChange',
    reValidateMode: 'onChange',
  })

  const password = useWatch({ control, name: 'password' })
  const confirmedPassword = useWatch({ control, name: 'confirm_password' })
  const isPasswordLengthValid = password.length >= 8 && password.length <= 128
  const doPasswordsMatch =
    confirmedPassword.length > 0 && confirmedPassword === password

  useEffect(() => {
    if (confirmedPassword.length > 0) {
      void trigger('confirm_password')
    }
  }, [confirmedPassword.length, password, trigger])

  async function submitForm(values: RegisterFormValues) {
    setApiError(null)

    try {
      await registerUser(values)
      navigate('/register/success', { replace: true })
    } catch (error) {
      const registrationError = getRegistrationErrorMessage(error)

      if (registrationError.field) {
        setError(
          registrationError.field,
          { type: 'server', message: registrationError.message },
          { shouldFocus: true },
        )
        return
      }

      setApiError(registrationError.message)
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
          onChange={() => {
            if (apiError !== null) {
              setApiError(null)
            }
          }}
          onSubmit={handleSubmit(submitForm)}
        >
          <AuthTextField
            label="Nazwa użytkownika"
            autoComplete="nickname"
            disabled={isSubmitting}
            errorMessage={errors.display_name?.message}
            registration={register('display_name')}
            startIcon={<PersonAddAltOutlined aria-hidden="true" />}
          />

          <AuthTextField
            label="Adres e-mail"
            type="email"
            autoComplete="email"
            disabled={isSubmitting}
            errorMessage={errors.email?.message}
            registration={register('email')}
            startIcon={<AlternateEmailRounded aria-hidden="true" />}
          />

          <AuthTextField
            label="Hasło"
            type="password"
            autoComplete="new-password"
            disabled={isSubmitting}
            errorMessage={errors.password?.message}
            registration={register('password')}
            startIcon={<LockOutlined aria-hidden="true" />}
          />

          <AuthTextField
            label="Powtórz hasło"
            type="password"
            autoComplete="new-password"
            disabled={isSubmitting}
            errorMessage={errors.confirm_password?.message}
            registration={register('confirm_password')}
            startIcon={<LockOutlined aria-hidden="true" />}
          />

          <div
            className="auth-form__requirements"
            aria-live="polite"
            aria-label="Wymagania hasła"
          >
            <span className="auth-form__requirements-title">
              Walidacja hasła
            </span>
            <ul>
              <PasswordRequirement
                label="Hasło ma od 8 do 128 znaków"
                state={
                  password.length === 0
                    ? 'pending'
                    : isPasswordLengthValid
                      ? 'valid'
                      : 'invalid'
                }
              />
              <PasswordRequirement
                label="Oba hasła są identyczne"
                state={
                  confirmedPassword.length === 0
                    ? 'pending'
                    : doPasswordsMatch
                      ? 'valid'
                      : 'invalid'
                }
              />
            </ul>
          </div>

          <AuthPrimaryButton
            type="submit"
            disabled={isSubmitting || !isValid}
            startIcon={<HowToRegRounded aria-hidden="true" />}
          >
            {isSubmitting ? 'Tworzenie konta...' : 'Utwórz konto'}
          </AuthPrimaryButton>

          <Typography className="auth-form__navigation">
            <span>Masz już konto?</span>
            <MuiLink
              className="auth-form__secondary-link"
              component={Link}
              to="/login"
            >
              Zaloguj się
            </MuiLink>
          </Typography>
        </form>
      </CardContent>
    </Card>
  )
}

export default RegisterForm
