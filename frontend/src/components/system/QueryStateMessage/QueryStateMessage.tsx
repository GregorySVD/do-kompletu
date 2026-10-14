import { Button, CircularProgress, Typography } from '@mui/material'
import './QueryStateMessage.css'

interface QueryStateMessageProps {
  message: string
  isLoading?: boolean
  isRetrying?: boolean
  onRetry?: () => void
}

function QueryStateMessage({
  message,
  isLoading = false,
  isRetrying = false,
  onRetry,
}: QueryStateMessageProps) {
  return (
    <section
      className="query-state-message"
      role={onRetry ? 'alert' : 'status'}
      aria-live="polite"
    >
      {(isLoading || isRetrying) && (
        <CircularProgress aria-hidden="true" size="2rem" />
      )}
      <Typography>{message}</Typography>
      {onRetry && (
        <Button disabled={isRetrying} variant="outlined" onClick={onRetry}>
          {isRetrying ? 'Ponawianie...' : 'Spróbuj ponownie'}
        </Button>
      )}
    </section>
  )
}

export default QueryStateMessage
