import { Button } from '@mui/material'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import './BackButton.css'

interface BackButtonProps {
  children?: ReactNode
  className?: string
  to: string
}

function BackButton({
  children = 'Wróć do aktywności',
  className,
  to,
}: BackButtonProps) {
  return (
    <Button
      className={['minecraft-back-button', className].filter(Boolean).join(' ')}
      component={Link}
      startIcon={
        <span className="minecraft-back-button__icon" aria-hidden="true">
          <img src="/icons/icons8-back-64.png" alt="" width="64" height="64" />
        </span>
      }
      to={to}
    >
      {children}
    </Button>
  )
}

export default BackButton
