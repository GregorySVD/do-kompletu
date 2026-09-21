export interface LoginFormValues {
  email: string
  password: string
}

export interface RegisterFormValues {
  display_name: string
  email: string
  password: string
  confirm_password: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
}

export interface AccessTokenResponse {
  access_token: string
  token_type: 'bearer'
}

export interface UserProfile {
  id: string
  email: string
  display_name: string
  avatar_url: string | null
  points_total: number
  is_active: boolean
  created_at: string
}
