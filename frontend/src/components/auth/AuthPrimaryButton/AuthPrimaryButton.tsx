import { Button } from '@mui/material'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import './AuthPrimaryButton.css'

interface AuthPrimaryButtonProps {
  children: ReactNode
  disabled?: boolean
  startIcon?: ReactNode
  to?: string
  type?: 'button' | 'submit'
}

function AuthPrimaryButton({
  children,
  disabled = false,
  startIcon,
  to,
  type = 'button',
}: AuthPrimaryButtonProps) {
  const sharedProps = {
    children,
    className: 'auth-primary-button',
    disabled,
    size: 'large' as const,
    startIcon,
    variant: 'contained' as const,
  }

  if (to) {
    return <Button {...sharedProps} component={Link} to={to} />
  }

  return <Button {...sharedProps} type={type} />
}

export default AuthPrimaryButton
