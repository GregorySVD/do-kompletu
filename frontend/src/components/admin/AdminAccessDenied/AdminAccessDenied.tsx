import { LockOutlined } from '@mui/icons-material'
import { Typography } from '@mui/material'
import BackButton from '../../navigation/BackButton/BackButton'
import './AdminAccessDenied.css'

interface AdminAccessDeniedProps {
  message?: string
}

function AdminAccessDenied({
  message = 'Twoje konto nie ma aktywnych uprawnień administratora.',
}: AdminAccessDeniedProps) {
  return (
    <main className="admin-access-denied">
      <section
        className="admin-access-denied__panel"
        aria-labelledby="admin-access-denied-title"
      >
        <span className="admin-access-denied__icon" aria-hidden="true">
          <LockOutlined />
        </span>
        <p className="admin-access-denied__eyebrow">SYSTEM // 403</p>
        <Typography id="admin-access-denied-title" component="h1" variant="h3">
          Dostęp administracyjny zablokowany
        </Typography>
        <Typography color="text.secondary">{message}</Typography>
        <BackButton to="/">Wróć do aktywności</BackButton>
      </section>
    </main>
  )
}

export default AdminAccessDenied
