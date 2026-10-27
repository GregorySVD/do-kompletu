import { Card, CardContent, Typography } from '@mui/material'
import { useId, type ReactNode } from 'react'
import AuthPrimaryButton from '../AuthPrimaryButton/AuthPrimaryButton'
import './AuthResultCard.css'

export interface AuthResultHighlight {
  code: string
  text: string
}

interface AuthResultCardProps {
  actionHint?: string
  actionIcon?: ReactNode
  actionLabel: string
  actionTo: string
  description: string
  highlights?: readonly AuthResultHighlight[]
  iconSrc: string
  statusLabel: string
  title: string
}

function AuthResultCard({
  actionHint,
  actionIcon,
  actionLabel,
  actionTo,
  description,
  highlights = [],
  iconSrc,
  statusLabel,
  title,
}: AuthResultCardProps) {
  const titleId = useId()

  return (
    <Card
      className="auth-result-card"
      component="section"
      variant="outlined"
      aria-labelledby={titleId}
    >
      <CardContent className="auth-result-card__content">
        <div className="auth-result-card__summary">
          <div className="auth-result-card__celebration" aria-hidden="true">
            <span className="auth-result-card__pixel auth-result-card__pixel--first" />
            <img src={iconSrc} alt="" width="64" height="64" />
            <span className="auth-result-card__pixel auth-result-card__pixel--second" />
          </div>

          <div className="auth-result-card__copy">
            <span
              className="auth-result-card__status"
              role="status"
              aria-live="polite"
            >
              {statusLabel}
            </span>
            <Typography
              id={titleId}
              component="h2"
              className="auth-result-card__title"
            >
              {title}
            </Typography>
            <Typography className="auth-result-card__description">
              {description}
            </Typography>
          </div>
        </div>

        {highlights.length > 0 && (
          <ul
            className="auth-result-card__highlights"
            aria-label="Podsumowanie"
          >
            {highlights.map((highlight) => (
              <li key={highlight.code}>
                <span aria-hidden="true">{highlight.code}</span>
                {highlight.text}
              </li>
            ))}
          </ul>
        )}

        <div className="auth-result-card__actions">
          <AuthPrimaryButton to={actionTo} startIcon={actionIcon}>
            {actionLabel}
          </AuthPrimaryButton>
          {actionHint && (
            <Typography className="auth-result-card__action-hint">
              {actionHint}
            </Typography>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default AuthResultCard
