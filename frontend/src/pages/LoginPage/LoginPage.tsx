import { Typography } from '@mui/material'
import LoginForm from '../../components/auth/LoginForm/LoginForm'
import BackButton from '../../components/navigation/BackButton/BackButton'
import './LoginPage.css'

function LoginPage() {
  return (
    <main className="login-page">
      <section className="login-page__panel" aria-labelledby="login-page-title">
        <div className="login-page__welcome">
          <span className="login-page__eyebrow">Panel gracza</span>

          <div className="login-page__brand-mark" aria-hidden="true">
            <img src="/favicon.png" alt="" width="1254" height="1254" />
          </div>

          <div className="login-page__welcome-copy">
            <Typography component="h2" className="login-page__welcome-title">
              Wróć do swojej ekipy
            </Typography>
            <Typography className="login-page__welcome-text">
              Zaloguj się, aby dołączać do aktywności, zarządzać zapisami i nie
              przegapić kolejnego spotkania.
            </Typography>
          </div>

          <ul className="login-page__benefits" aria-label="Możliwości konta">
            <li>
              <span aria-hidden="true">01</span>
              Odkrywaj aktywności w swojej okolicy
            </li>
            <li>
              <span aria-hidden="true">02</span>
              Kontroluj zapisy i ważne terminy
            </li>
            <li>
              <span aria-hidden="true">03</span>
              Twórz własne wydarzenia dla innych
            </li>
          </ul>
        </div>

        <div className="login-page__form-column">
          <div className="login-page__heading">
            <span className="login-page__form-step">Dostęp do konta</span>
            <Typography
              id="login-page-title"
              component="h1"
              className="login-page__title"
            >
              Zaloguj się
            </Typography>
            <Typography className="login-page__subtitle">
              Wprowadź e-mail lub nazwę użytkownika i swoje hasło.
            </Typography>
          </div>

          <LoginForm />
        </div>
      </section>

      <div className="login-page__back-container">
        <BackButton className="login-page__back" to="/">
          Wróć do aktywności
        </BackButton>
      </div>
    </main>
  )
}

export default LoginPage
