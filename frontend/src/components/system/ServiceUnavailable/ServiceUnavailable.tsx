import { CloudOffOutlined, Refresh } from '@mui/icons-material'
import { Button, CircularProgress, Typography } from '@mui/material'
import './ServiceUnavailable.css'

interface ServiceUnavailableProps {
  isRetrying: boolean
  onRetry: () => void
}

function ServiceUnavailable({ isRetrying, onRetry }: ServiceUnavailableProps) {
  return (
    <main className="service-unavailable">
      <section
        className="service-unavailable__card"
        aria-labelledby="service-unavailable-title"
      >
        <div className="service-unavailable__icon" aria-hidden="true">
          <CloudOffOutlined fontSize="inherit" />
        </div>

        <Typography id="service-unavailable-title" component="h1" variant="h4">
          Chwilowo nie możemy połączyć się z serwerem
        </Typography>

        <Typography className="service-unavailable__description">
          Przepraszamy, DoKompletu jest obecnie niedostępne. Spróbuj ponownie za
          chwilę.
        </Typography>

        <Typography className="service-unavailable__support" variant="body2">
          Jeżeli problem będzie się powtarzał, spróbuj ponownie później.
        </Typography>

        <Button
          className="service-unavailable__retry"
          disabled={isRetrying}
          size="large"
          startIcon={
            isRetrying ? (
              <CircularProgress
                className="service-unavailable__retry-spinner"
                aria-hidden="true"
                size="1.25rem"
              />
            ) : (
              <Refresh />
            )
          }
          variant="contained"
          onClick={onRetry}
        >
          {isRetrying ? 'Łączenie...' : 'Spróbuj ponownie'}
        </Button>
      </section>
    </main>
  )
}

export default ServiceUnavailable
