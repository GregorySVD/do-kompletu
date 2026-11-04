import axios from 'axios'

export type ActivityGalleryOperation = 'load' | 'upload' | 'delete'

const defaultMessages: Record<ActivityGalleryOperation, string> = {
  load: 'Nie udało się pobrać zdjęć.',
  upload: 'Nie udało się dodać zdjęcia. Spróbuj ponownie.',
  delete: 'Nie udało się usunąć zdjęcia. Spróbuj ponownie.',
}

const forbiddenMessages: Record<ActivityGalleryOperation, string> = {
  load: 'Galeria nie jest już dostępna.',
  upload: 'Nie możesz teraz dodawać zdjęć do tej galerii.',
  delete: 'Nie możesz już usunąć tego zdjęcia.',
}

const notFoundMessages: Record<ActivityGalleryOperation, string> = {
  load: 'Ta aktywność lub jej galeria nie jest już dostępna.',
  upload: 'Ta aktywność lub jej galeria nie jest już dostępna.',
  delete: 'To zdjęcie nie istnieje lub zostało już usunięte.',
}

export function getActivityGalleryErrorStatus(error: unknown) {
  return axios.isAxiosError(error) ? error.response?.status : undefined
}

export function getActivityGalleryErrorMessage(
  error: unknown,
  operation: ActivityGalleryOperation,
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
    return forbiddenMessages[operation]
  }

  if (status === 404) {
    return notFoundMessages[operation]
  }

  if (status === 409 && operation === 'upload') {
    return 'Osiągnięto limit 3 zdjęć dla tej aktywności.'
  }

  if (status === 413 && operation === 'upload') {
    return 'Zdjęcie jest za duże. Maksymalny rozmiar to 10 MB.'
  }

  if (status === 422 && operation === 'upload') {
    return 'Plik nie jest prawidłowym zdjęciem JPEG, PNG lub WebP.'
  }

  if (status === 503) {
    return 'Galeria jest chwilowo niedostępna. Spróbuj ponownie później.'
  }

  return defaultMessages[operation]
}
