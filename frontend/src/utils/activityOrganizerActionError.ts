import axios from 'axios'

interface ActivityOrganizerActionErrorResponse {
  detail?: unknown
}

const conflictMessages: Record<string, string> = {
  'Activity is cancelled': 'Aktywność została już anulowana.',
  'Activity has ended': 'Zakończonej aktywności nie można anulować.',
  'Activity can only be finalized after it ends':
    'Aktywność można finalizować dopiero po jej zakończeniu.',
  'No unresolved attendance to finalize':
    'Nie ma już uczestnictw wymagających finalizacji.',
}

export function getActivityOrganizerActionErrorMessage(error: unknown) {
  if (!axios.isAxiosError<ActivityOrganizerActionErrorResponse>(error)) {
    return 'Nie udało się wykonać operacji. Spróbuj ponownie.'
  }

  const status = error.response?.status
  const detail = error.response?.data.detail

  if (status === 401) {
    return 'Sesja wygasła lub jest nieprawidłowa.'
  }

  if (status === 403) {
    return 'Nie masz uprawnień do wykonania tej operacji.'
  }

  if (status === 404) {
    return 'Ta aktywność już nie istnieje.'
  }

  if (status === 409 && typeof detail === 'string') {
    return conflictMessages[detail] ?? 'Nie można teraz wykonać tej operacji.'
  }

  return 'Nie udało się wykonać operacji. Spróbuj ponownie.'
}
