import { Refresh } from '@mui/icons-material'
import { Button, CircularProgress, Typography } from '@mui/material'
import './QueryStateMessage.css'

interface QueryStateMessageProps {
  hint?: string
  message: string
  isLoading?: boolean
  isRetrying?: boolean
  onRetry?: () => void
  retryLabel?: string
  retryingLabel?: string
  title?: string
}

function QueryStateMessage({
  hint,
  message,
  isLoading = false,
  isRetrying = false,
  onRetry,
  retryLabel = 'Spróbuj ponownie',
  retryingLabel = 'Ponawianie...',
  title = 'Połączenie przerwane',
}: QueryStateMessageProps) {
  const hasError = onRetry !== undefined
  const showLoadingIndicator = isLoading || isRetrying

  return (
    <section
      className={`query-state-message query-state-message--${hasError ? 'error' : 'loading'}`}
      role={hasError ? 'alert' : 'status'}
      aria-live="polite"
    >
      {hasError ? (
        <>
          <div className="query-state-message__visual" aria-hidden="true">
            <img
              src="/cat-server-notfound.gif"
              alt=""
              width="128"
              height="128"
            />
            <span>!</span>
          </div>

          <Typography className="query-state-message__eyebrow" component="p">
            Utracono połączenie
          </Typography>
          <Typography
            className="query-state-message__title"
            component="h1"
            variant="h4"
          >
            {title}
          </Typography>
        </>
      ) : showLoadingIndicator ? (
        <div className="query-state-message__loader" aria-hidden="true">
          <CircularProgress size="2rem" />
        </div>
      ) : null}

      <Typography className="query-state-message__message">
        {message}
      </Typography>

      {hint && (
        <Typography
          className="query-state-message__hint"
          color="text.secondary"
          variant="body2"
        >
          {hint}
        </Typography>
      )}

      {onRetry && (
        <Button
          className="query-state-message__retry"
          disabled={isRetrying}
          startIcon={
            isRetrying ? (
              <CircularProgress aria-hidden="true" size="1rem" />
            ) : (
              <Refresh />
            )
          }
          variant="contained"
          onClick={onRetry}
        >
          {isRetrying ? retryingLabel : retryLabel}
        </Button>
      )}
    </section>
  )
}

export default QueryStateMessage
