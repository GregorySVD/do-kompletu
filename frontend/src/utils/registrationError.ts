import axios from 'axios'
import type { RegisterFormValues } from '../types/auth'

interface RegistrationErrorResponse {
  detail?: string
}

export interface RegistrationErrorMessage {
  field?: keyof Pick<RegisterFormValues, 'display_name' | 'email'>
  message: string
}

export function getRegistrationErrorMessage(
  error: unknown,
): RegistrationErrorMessage {
  if (!axios.isAxiosError<RegistrationErrorResponse>(error)) {
    return { message: 'Nie udało się utworzyć konta. Spróbuj ponownie.' }
  }

  const errorDetail = error.response?.data.detail

  if (
    error.response?.status === 409 &&
    errorDetail === 'Username is already taken'
  ) {
    return {
      field: 'display_name',
      message: 'Ta nazwa użytkownika jest już zajęta.',
    }
  }

  if (
    error.response?.status === 409 &&
    errorDetail === 'Email address is already registered'
  ) {
    return {
      field: 'email',
      message: 'Konto z tym adresem e-mail już istnieje.',
    }
  }

  if (!error.response) {
    return { message: 'Nie udało się połączyć z serwerem.' }
  }

  if (error.response.status === 422) {
    return { message: 'Sprawdź poprawność danych formularza.' }
  }

  return { message: 'Nie udało się utworzyć konta. Spróbuj ponownie.' }
}
