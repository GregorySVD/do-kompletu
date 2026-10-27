import { Typography } from '@mui/material'
import type { ReactNode } from 'react'
import BackButton from '../../navigation/BackButton/BackButton'
import './AuthPageLayout.css'

export interface AuthPageBenefit {
  code: string
  text: string
}

interface AuthPageLayoutProps {
  benefits: readonly AuthPageBenefit[]
  children: ReactNode
  formEyebrow: string
  pageSubtitle: string
  pageTitle: string
  pageTitleId: string
  welcomeEyebrow: string
  welcomeText: string
  welcomeTitle: string
}

function AuthPageLayout({
  benefits,
  children,
  formEyebrow,
  pageSubtitle,
  pageTitle,
  pageTitleId,
  welcomeEyebrow,
  welcomeText,
  welcomeTitle,
}: AuthPageLayoutProps) {
  return (
    <main className="auth-page">
      <section className="auth-page__panel" aria-labelledby={pageTitleId}>
        <div className="auth-page__welcome">
          <span className="auth-page__eyebrow">{welcomeEyebrow}</span>

          <div className="auth-page__brand-mark" aria-hidden="true">
            <img src="/favicon.png" alt="" width="1254" height="1254" />
          </div>

          <div className="auth-page__welcome-copy">
            <Typography component="h2" className="auth-page__welcome-title">
              {welcomeTitle}
            </Typography>
            <Typography className="auth-page__welcome-text">
              {welcomeText}
            </Typography>
          </div>

          <ul className="auth-page__benefits" aria-label="Możliwości konta">
            {benefits.map((benefit) => (
              <li key={benefit.code}>
                <span aria-hidden="true">{benefit.code}</span>
                {benefit.text}
              </li>
            ))}
          </ul>
        </div>

        <div className="auth-page__form-column">
          <div className="auth-page__heading">
            <span className="auth-page__form-step">{formEyebrow}</span>
            <Typography
              id={pageTitleId}
              component="h1"
              className="auth-page__title"
            >
              {pageTitle}
            </Typography>
            <Typography className="auth-page__subtitle">
              {pageSubtitle}
            </Typography>
          </div>

          {children}
        </div>
      </section>

      <div className="auth-page__back-container">
        <BackButton className="auth-page__back" to="/">
          Wróć do aktywności
        </BackButton>
      </div>
    </main>
  )
}

export default AuthPageLayout
