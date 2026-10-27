import AuthPageLayout, {
  type AuthPageBenefit,
} from '../../components/auth/AuthPageLayout/AuthPageLayout'
import LoginForm from '../../components/auth/LoginForm/LoginForm'

const loginBenefits: readonly AuthPageBenefit[] = [
  { code: '01', text: 'Odkrywaj aktywności w swojej okolicy' },
  { code: '02', text: 'Kontroluj zapisy i ważne terminy' },
  { code: '03', text: 'Twórz własne wydarzenia dla innych' },
]

function LoginPage() {
  return (
    <AuthPageLayout
      pageTitleId="login-page-title"
      pageTitle="Zaloguj się"
      pageSubtitle="Wprowadź e-mail lub nazwę użytkownika i swoje hasło."
      formEyebrow="Dostęp do konta"
      welcomeEyebrow="Panel gracza"
      welcomeTitle="Wróć do swojej ekipy"
      welcomeText="Zaloguj się, aby dołączać do aktywności, zarządzać zapisami i nie przegapić kolejnego spotkania."
      benefits={loginBenefits}
    >
      <LoginForm />
    </AuthPageLayout>
  )
}

export default LoginPage
