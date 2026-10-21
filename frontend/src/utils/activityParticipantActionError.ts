import axios from 'axios'

interface ActivityParticipantActionErrorResponse {
  detail?: unknown
}

const defaultMessage = 'Nie udało się wykonać operacji. Spróbuj ponownie.'

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
}

export function getActivityParticipantActionErrorMessage(error: unknown) {
  if (!axios.isAxiosError<ActivityParticipantActionErrorResponse>(error)) {
    return defaultMessage
  }

  const status = error.response?.status
  const detail = error.response?.data.detail

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
