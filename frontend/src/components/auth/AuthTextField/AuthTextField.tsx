import { VisibilityOffOutlined, VisibilityOutlined } from '@mui/icons-material'
import { IconButton, InputAdornment, TextField } from '@mui/material'
import { useState, type ReactNode } from 'react'
import type { UseFormRegisterReturn } from 'react-hook-form'

interface AuthTextFieldProps {
  autoComplete: string
  disabled?: boolean
  errorMessage?: string
  label: string
  registration: UseFormRegisterReturn
  startIcon: ReactNode
  type?: 'email' | 'password' | 'text'
}

function AuthTextField({
  autoComplete,
  disabled = false,
  errorMessage,
  label,
  registration,
  startIcon,
  type = 'text',
}: AuthTextFieldProps) {
  const [isPasswordVisible, setIsPasswordVisible] = useState(false)
  const isPasswordField = type === 'password'
  const resolvedType = isPasswordField && isPasswordVisible ? 'text' : type

  return (
    <TextField
      className="auth-form__field"
      label={label}
      type={resolvedType}
      autoComplete={autoComplete}
      disabled={disabled}
      error={Boolean(errorMessage)}
      helperText={errorMessage}
      slotProps={{
        input: {
          startAdornment: (
            <InputAdornment position="start">{startIcon}</InputAdornment>
          ),
          endAdornment: isPasswordField ? (
            <InputAdornment position="end">
              <IconButton
                type="button"
                aria-label={isPasswordVisible ? 'Ukryj hasło' : 'Pokaż hasło'}
                edge="end"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => setIsPasswordVisible((isVisible) => !isVisible)}
              >
                {isPasswordVisible ? (
                  <VisibilityOffOutlined />
                ) : (
                  <VisibilityOutlined />
                )}
              </IconButton>
            </InputAdornment>
          ) : undefined,
        },
      }}
      {...registration}
    />
  )
}

export default AuthTextField
