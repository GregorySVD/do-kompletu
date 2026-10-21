import axios from 'axios'

interface ActivityParticipantActionErrorResponse {
  detail?: unknown
}

const defaultMessage = 'Nie udało się wykonać operacji. Spróbuj ponownie.'
const networkMessage = 'Nie udało się połączyć z serwerem. Spróbuj ponownie.'

const conflictMessages: Record<string, string> = {
  'Already joined this activity': 'Jesteś już zapisany na tę aktywność.',
  'Attendance outcome is final':
    'Twojego zakończonego udziału nie można już zmienić.',
  'Activity has started': 'Nie można już dołączyć — aktywność się rozpoczęła.',
  'Activity has ended': 'Aktywność już się zakończyła.',
  'Activity is cancelled': 'Aktywność została anulowana.',
  'Organizer cannot join or leave their own activity':
    'Organizator nie może dołączyć do własnej aktywności.',
  'Not participating in this activity': 'Nie jesteś zapisany na tę aktywność.',
  'Checked-in participants cannot leave':
    'Po wykonaniu check-inu nie można zrezygnować.',
  'Confirmation window has closed': 'Termin potwierdzenia udziału już minął.',
  'Participation has expired': 'Twój udział w tej aktywności wygasł.',
}

const confirmConflictMessages: Record<string, string> = {
  'Participation has expired': 'Rezerwacja udziału wygasła.',
  'Organizer cannot confirm their own activity':
    'Organizator nie może potwierdzać udziału we własnej aktywności.',
  'Not participating in this activity': 'Nie jesteś zapisany na tę aktywność.',
  'Already confirmed attendance': 'Udział został już potwierdzony.',
  'Attendance outcome is final': 'Twój udział został już rozliczony.',
  'Already checked in': 'Check-in został już wykonany.',
  'Activity is cancelled': 'Aktywność została anulowana.',
  'Activity has ended': 'Aktywność już się zakończyła.',
  'Confirmation window has not opened':
    'Okno potwierdzania udziału nie jest jeszcze otwarte.',
  'Confirmation window has closed': 'Termin potwierdzenia udziału już minął.',
}

const checkInConflictMessages: Record<string, string> = {
  'Participation has expired': 'Twój udział w tej aktywności wygasł.',
  'Organizer cannot check in to their own activity':
    'Organizator nie wykonuje check-inu we własnej aktywności.',
  'Attendance outcome is final': 'Twój udział został już rozliczony.',
  'Not participating in this activity': 'Nie jesteś zapisany na tę aktywność.',
  'Attendance must be confirmed before check-in':
    'Najpierw potwierdź udział w aktywności.',
  'Already checked in': 'Check-in został już wykonany.',
  'Activity is cancelled': 'Aktywność została anulowana.',
  'Activity has ended': 'Aktywność już się zakończyła.',
  'Check-in window has not opened': 'Check-in nie jest jeszcze dostępny.',
  'Check-in window has closed': 'Okno check-inu zostało zamknięte.',
  'Location accuracy is insufficient for check-in':
    'Dokładność lokalizacji jest zbyt niska. Przejdź w miejsce z lepszym sygnałem GPS i spróbuj ponownie.',
  'Outside check-in radius':
    'Znajdujesz się zbyt daleko od miejsca aktywności, aby wykonać check-in.',
}

export function getActivityParticipantActionErrorMessage(error: unknown) {
  if (!axios.isAxiosError<ActivityParticipantActionErrorResponse>(error)) {
    return defaultMessage
  }

  if (!error.response) {
    return networkMessage
  }

  const status = error.response.status
  const detail = error.response.data.detail

  if (status === 401) {
    return 'Sesja wygasła lub jest nieprawidłowa.'
  }

  if (status === 404) {
    return 'Ta aktywność nie istnieje.'
  }

  if (status === 409 && typeof detail === 'string') {
    return conflictMessages[detail] ?? defaultMessage
  }

  return defaultMessage
}

export function getConfirmActivityErrorMessage(error: unknown) {
  if (!axios.isAxiosError<ActivityParticipantActionErrorResponse>(error)) {
    return defaultMessage
  }

  if (!error.response) {
    return networkMessage
  }

  const { status } = error.response
  const detail = error.response.data.detail

  if (status === 401) {
    return 'Sesja wygasła lub jest nieprawidłowa.'
  }

  if (status === 404) {
    return 'Ta aktywność nie istnieje.'
  }

  if (status === 409 && typeof detail === 'string') {
    return confirmConflictMessages[detail] ?? defaultMessage
  }

  return defaultMessage
}

export function getCheckInActivityErrorMessage(error: unknown) {
  if (!axios.isAxiosError<ActivityParticipantActionErrorResponse>(error)) {
    return defaultMessage
  }

  if (!error.response) {
    return networkMessage
  }

  const { status } = error.response
  const detail = error.response.data.detail

  if (status === 401) {
    return 'Sesja wygasła lub jest nieprawidłowa.'
  }

  if (status === 404) {
    return 'Ta aktywność nie istnieje.'
  }

  if (status === 409 && typeof detail === 'string') {
    return checkInConflictMessages[detail] ?? defaultMessage
  }

  if (status === 422) {
    return 'Nie udało się zweryfikować lokalizacji. Spróbuj pobrać ją ponownie.'
  }

  if (status === 503) {
    return 'Usługa weryfikacji lokalizacji jest chwilowo niedostępna. Spróbuj ponownie później.'
  }

  return defaultMessage
}
