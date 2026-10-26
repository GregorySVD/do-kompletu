import BouncingLogo from '../BouncingLogo/BouncingLogo'
import QueryStateMessage from '../QueryStateMessage/QueryStateMessage'
import './ServiceUnavailable.css'

interface ServiceUnavailableProps {
  isRetrying: boolean
  onRetry: () => void
}

function ServiceUnavailable({ isRetrying, onRetry }: ServiceUnavailableProps) {
  return (
    <main className="service-unavailable">
      <BouncingLogo />
      <QueryStateMessage
        title="Serwer chwilowo nie odpowiada"
        message="Nie możemy teraz potwierdzić Twojej sesji ani pobrać danych."
        hint="Twoje dane są bezpieczne. Spróbuj połączyć się ponownie za chwilę."
        isRetrying={isRetrying}
        retryingLabel="Łączenie..."
        onRetry={onRetry}
      />
    </main>
  )
}

export default ServiceUnavailable
