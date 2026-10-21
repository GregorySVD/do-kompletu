import axios from 'axios'

interface UpdateActivityErrorResponse {
  detail?: unknown
}

const conflictMessages: Record<string, string> = {
  'Activity is cancelled': 'Anulowanej aktywności nie można edytować.',
  'Activity can only be edited before it starts':
    'Aktywność już się rozpoczęła i nie może być edytowana.',
  'Participant limit cannot be below current participant count':
    'Limit uczestników nie może być mniejszy niż liczba aktualnych uczestników.',
  'Cannot change schedule while participants are confirmed':
    'Nie można zmienić terminu, gdy są już potwierdzeni uczestnicy.',
  'Cannot change location after participants have checked in':
    'Nie można zmienić lokalizacji po wykonaniu check-in przez uczestnika.',
}

export function getUpdateActivityErrorMessage(error: unknown) {
  if (!axios.isAxiosError<UpdateActivityErrorResponse>(error)) {
    return 'Nie udało się zapisać zmian. Spróbuj ponownie.'
  }

  if (!error.response) {
    return 'Nie udało się połączyć z serwerem. Spróbuj ponownie.'
  }

  const { status } = error.response
  const detail = error.response.data.detail

  if (status === 401) {
    return 'Sesja wygasła lub jest nieprawidłowa.'
  }

  if (status === 403) {
    return 'Nie masz uprawnień do edycji tej aktywności.'
  }

  if (status === 404) {
    return 'Ta aktywność nie istnieje.'
  }

  if (status === 409 && typeof detail === 'string') {
    return (
      conflictMessages[detail] ??
      'Nie można teraz zapisać zmian w tej aktywności.'
    )
  }

  if (status === 422) {
    if (detail === 'start_at must remain strictly in the future') {
      return 'Data rozpoczęcia musi pozostać w przyszłości.'
    }

    return 'Nie udało się zapisać zmian. Sprawdź poprawność danych.'
  }

  return 'Nie udało się zapisać zmian. Spróbuj ponownie.'
}
