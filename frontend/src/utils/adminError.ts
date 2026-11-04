import axios from 'axios'

export type AdminOperation =
  | 'load-users'
  | 'load-activities'
  | 'set-user-active'
  | 'cancel-activity'
  | 'delete-photo'

const defaultMessages: Record<AdminOperation, string> = {
  'load-users': 'Nie udało się pobrać listy użytkowników.',
  'load-activities': 'Nie udało się pobrać listy aktywności.',
  'set-user-active': 'Nie udało się zmienić statusu konta.',
  'cancel-activity': 'Nie udało się anulować aktywności.',
  'delete-photo': 'Nie udało się usunąć zdjęcia.',
}

export function getAdminErrorStatus(error: unknown) {
  return axios.isAxiosError(error) ? error.response?.status : undefined
}

export function getAdminErrorMessage(
  error: unknown,
  operation: AdminOperation,
) {
  if (!axios.isAxiosError(error)) {
    return defaultMessages[operation]
  }

  if (!error.response) {
    return 'Nie udało się połączyć z serwerem. Sprawdź połączenie i spróbuj ponownie.'
  }

  const { status } = error.response

  if (status === 401) {
    return 'Sesja wygasła lub jest nieprawidłowa.'
  }

  if (status === 403) {
    return 'Nie masz już uprawnień administratora.'
  }

  if (status === 404) {
    if (operation === 'set-user-active') {
      return 'Nie znaleziono tego użytkownika.'
    }

    if (operation === 'delete-photo') {
      return 'Nie znaleziono zdjęcia dla podanej aktywności.'
    }

    return 'Nie znaleziono tej aktywności.'
  }

  if (status === 409) {
    return operation === 'set-user-active'
      ? 'Administrator nie może dezaktywować własnego konta.'
      : 'Aktywność jest już anulowana albo została zakończona.'
  }

  if (status === 422) {
    return 'Przesłane dane są nieprawidłowe.'
  }

  if (status === 503) {
    return operation === 'delete-photo'
      ? 'Magazyn zdjęć jest chwilowo niedostępny.'
      : 'Usługa administracyjna jest chwilowo niedostępna.'
  }

  return defaultMessages[operation]
}
