import axios from 'axios'

export function getCreateActivityErrorMessage(error: unknown) {
  if (!axios.isAxiosError(error)) {
    return 'Nie udało się utworzyć aktywności. Spróbuj ponownie.'
  }

  if (!error.response) {
    return 'Nie udało się połączyć z serwerem. Spróbuj ponownie.'
  }

  if (error.response.status === 401) {
    return 'Sesja wygasła lub jest nieprawidłowa. Zaloguj się ponownie.'
  }

  if (error.response.status === 422) {
    return 'Nie udało się utworzyć aktywności. Sprawdź poprawność danych.'
  }

  return 'Nie udało się utworzyć aktywności. Spróbuj ponownie.'
}
