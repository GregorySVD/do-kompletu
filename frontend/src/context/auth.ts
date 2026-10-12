import { createContext, useContext } from 'react'
import type {
  LoginFormValues,
  RegisterFormValues,
  UserProfile,
} from '../types/auth'

export interface AuthContextValue {
  user: UserProfile | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (values: LoginFormValues) => Promise<void>
  register: (values: RegisterFormValues) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
)

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }

  return context
}
