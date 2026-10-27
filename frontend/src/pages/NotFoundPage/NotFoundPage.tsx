import BackButton from '../../components/navigation/BackButton/BackButton'
import './NotFoundPage.css'

function NotFoundPage() {
  return (
    <main className="not-found-page">
      <section
        className="not-found-panel"
        aria-labelledby="not-found-page-title"
      >
        <div className="not-found-panel__visual" aria-hidden="true">
          <span className="not-found-panel__signal">SYSTEM // LOST</span>
          <strong>404</strong>
          <div className="not-found-panel__coordinates">
            <span>X: ????</span>
            <span>Y: ????</span>
          </div>
        </div>

        <div className="not-found-panel__content">
          <p className="not-found-panel__eyebrow">Błąd nawigacji // 404</p>
          <h1 id="not-found-page-title">Ta ścieżka prowadzi donikąd</h1>
          <p className="not-found-panel__message">
            Podany adres nie prowadzi do istniejącej strony. Być może widok
            został przeniesiony albo w adresie pojawił się błąd.
          </p>

          <div className="not-found-panel__status" role="status">
            <span aria-hidden="true" />
            Połączenie z aktywnościami nadal działa
          </div>

          <BackButton className="not-found-panel__back" to="/">
            Wróć do aktywności
          </BackButton>
        </div>
      </section>
    </main>
  )
}

export default NotFoundPage
