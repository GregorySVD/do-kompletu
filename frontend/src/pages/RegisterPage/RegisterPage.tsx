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
import type { RegisterFormValues } from '../../types/auth'
import './RegisterPage.css'

const registerSchema = z
  .object({
    display_name: z
      .string()
      .min(1, 'Nazwa użytkownika jest wymagana')
      .min(3, 'Nazwa użytkownika musi mieć co najmniej 3 znaki')
      .max(40, 'Nazwa użytkownika może mieć maksymalnie 40 znaków'),
    email: z
      .string()
      .min(1, 'Adres e-mail jest wymagany')
      .email('Podaj poprawny adres e-mail'),
    password: z
      .string()
      .min(1, 'Hasło jest wymagane')
      .min(8, 'Hasło musi mieć co najmniej 8 znaków'),
    confirm_password: z.string().min(1, 'Powtórzenie hasła jest wymagane'),
  })
  .superRefine((values, context) => {
    if (
      values.confirm_password &&
      values.confirm_password !== values.password
    ) {
      context.addIssue({
        code: 'custom',
        path: ['confirm_password'],
        message: 'Hasła muszą być identyczne',
      })
    }
  })

const defaultValues: RegisterFormValues = {
  display_name: '',
  email: '',
  password: '',
  confirm_password: '',
}

function RegisterPage() {
  const [isSubmitted, setIsSubmitted] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues,
  })

  function submitForm() {
    setIsSubmitted(true)
  }

  return (
    <main className="register-page">
      <div className="register-page__heading">
        <div>
          <Typography component="h1" variant="h4">
            Zarejestruj się
          </Typography>
          <Typography color="text.secondary">
            Utwórz konto, aby w przyszłości dołączać do aktywności.
          </Typography>
        </div>

        <Button component={Link} to="/">
          Wróć do strony głównej
        </Button>
      </div>

      {isSubmitted && (
        <Alert severity="success">
          Formularz jest poprawny. Rejestracja zostanie uruchomiona po
          integracji z API.
        </Alert>
      )}

      <Card variant="outlined" className="register-card">
        <CardContent>
          <form
            className="register-form"
            noValidate
            onSubmit={handleSubmit(submitForm)}
          >
            <TextField
              label="Nazwa użytkownika"
              autoComplete="nickname"
              error={Boolean(errors.display_name)}
              helperText={errors.display_name?.message}
              {...register('display_name')}
            />

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
              autoComplete="new-password"
              error={Boolean(errors.password)}
              helperText={errors.password?.message}
              {...register('password')}
            />

            <TextField
              label="Powtórz hasło"
              type="password"
              autoComplete="new-password"
              error={Boolean(errors.confirm_password)}
              helperText={errors.confirm_password?.message}
              {...register('confirm_password')}
            />

            <Button type="submit" variant="contained" size="large">
              Zarejestruj się
            </Button>

            <Typography className="register-form__navigation">
              Masz już konto?{' '}
              <MuiLink component={Link} to="/login">
                Zaloguj się
              </MuiLink>
            </Typography>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}

export default RegisterPage
