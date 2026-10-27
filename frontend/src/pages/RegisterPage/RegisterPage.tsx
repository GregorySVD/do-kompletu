import AuthPageLayout, {
  type AuthPageBenefit,
} from '../../components/auth/AuthPageLayout/AuthPageLayout'
import RegisterForm from '../../components/auth/RegisterForm/RegisterForm'

const registrationBenefits: readonly AuthPageBenefit[] = [
  { code: '01', text: 'Znajduj ludzi o podobnych zainteresowaniach' },
  { code: '02', text: 'Dołączaj do spotkań lub list rezerwowych' },
  { code: '03', text: 'Organizuj własne aktywności' },
]

function RegisterPage() {
  return (
    <AuthPageLayout
      pageTitleId="register-page-title"
      pageTitle="Utwórz konto"
      pageSubtitle="Podaj swoje dane. Poprawność formularza sprawdzamy od razu."
      formEyebrow="Nowy profil"
      welcomeEyebrow="Nowy gracz"
      welcomeTitle="Dołącz do społeczności"
      welcomeText="Załóż konto, odkrywaj aktywności w okolicy i buduj własną ekipę do wspólnego spędzania czasu."
      benefits={registrationBenefits}
    >
      <RegisterForm />
    </AuthPageLayout>
  )
}

export default RegisterPage
