import { useRef, useState } from 'react'

const geolocationOptions: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 15_000,
  maximumAge: 0,
}

function getGeolocationErrorMessage(error: GeolocationPositionError) {
  switch (error.code) {
    case error.PERMISSION_DENIED:
      return 'Brak zgody na dostęp do lokalizacji. Zezwól przeglądarce na dostęp i spróbuj ponownie.'
    case error.POSITION_UNAVAILABLE:
      return 'Nie udało się ustalić lokalizacji urządzenia.'
    case error.TIMEOUT:
      return 'Nie udało się pobrać lokalizacji w wymaganym czasie. Spróbuj ponownie.'
    default:
      return 'Nie udało się ustalić lokalizacji urządzenia.'
  }
}

export function useCurrentPosition() {
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isLocating, setIsLocating] = useState(false)
  const isLocatingRef = useRef(false)

  function resetError() {
    setErrorMessage(null)
  }

  function getCurrentPosition(): Promise<GeolocationPosition | null> {
    if (isLocatingRef.current) {
      return Promise.resolve(null)
    }

    resetError()

    if (!navigator.geolocation) {
      setErrorMessage('Ta przeglądarka nie obsługuje geolokalizacji.')
      return Promise.resolve(null)
    }

    isLocatingRef.current = true
    setIsLocating(true)

    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          isLocatingRef.current = false
          setIsLocating(false)
          resolve(position)
        },
        (error) => {
          isLocatingRef.current = false
          setIsLocating(false)
          setErrorMessage(getGeolocationErrorMessage(error))
          resolve(null)
        },
        geolocationOptions,
      )
    })
  }

  return { errorMessage, getCurrentPosition, isLocating, resetError }
}
