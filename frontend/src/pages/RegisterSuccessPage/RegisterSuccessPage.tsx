import { LoginRounded } from '@mui/icons-material'
import AuthPageLayout, {
  type AuthPageBenefit,
} from '../../components/auth/AuthPageLayout/AuthPageLayout'
import AuthResultCard, {
  type AuthResultHighlight,
} from '../../components/auth/AuthResultCard/AuthResultCard'

const completedRegistrationSteps: readonly AuthPageBenefit[] = [
  { code: '01', text: 'Profil użytkownika został utworzony' },
  { code: '02', text: 'Logowanie do konta jest już dostępne' },
  { code: '03', text: 'Aktywności i nowe ekipy czekają' },
]

const accountHighlights: readonly AuthResultHighlight[] = [
  { code: 'OK', text: 'Twoje konto jest gotowe do użycia' },
  { code: '>>', text: 'Następny krok: zaloguj się podanymi danymi' },
]

function RegisterSuccessPage() {
  return (
    <AuthPageLayout
      pageTitleId="register-success-page-title"
      pageTitle="Konto gotowe!"
      pageSubtitle="Rejestracja zakończyła się powodzeniem. Jeszcze tylko logowanie."
      formEyebrow="Rejestracja zakończona"
      welcomeEyebrow="Profil odblokowany"
      welcomeTitle="Witaj w DoKompletu"
      welcomeText="Twój profil jest już częścią społeczności. Za chwilę możesz zacząć szukać swojej następnej ekipy."
      benefits={completedRegistrationSteps}
    >
      <AuthResultCard
        statusLabel="Status: sukces"
        title="Możesz już wejść do gry"
        description="Użyj nazwy użytkownika lub adresu e-mail oraz hasła podanego podczas rejestracji."
        iconSrc="/icons/icons8-confetti-64.png"
        highlights={accountHighlights}
        actionTo="/login"
        actionLabel="Przejdź do logowania"
        actionIcon={<LoginRounded aria-hidden="true" />}
        actionHint="Po zalogowaniu od razu przejdziesz do aktywności."
      />
    </AuthPageLayout>
  )
}

export default RegisterSuccessPage
