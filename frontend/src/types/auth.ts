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

export interface UserProfile {
  id: string
  display_name: string
  email: string
  avatar_url: string | null
}
