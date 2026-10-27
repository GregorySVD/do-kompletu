import { z } from 'zod'
import type { LoginFormValues, RegisterFormValues } from '../types/auth'

export const loginFormSchema = z.object({
  identifier: z
    .string()
    .trim()
    .min(1, 'Wprowadź e-mail lub nazwę użytkownika.')
    .max(320, 'E-mail lub nazwa użytkownika może mieć maksymalnie 320 znaków'),
  password: z
    .string()
    .min(1, 'Hasło jest wymagane.')
    .max(128, 'Hasło może mieć maksymalnie 128 znaków.'),
})

export const registerFormSchema = z
  .object({
    display_name: z
      .string()
      .trim()
      .min(1, 'Nazwa użytkownika jest wymagana.')
      .min(3, 'Nazwa użytkownika musi mieć co najmniej 3 znaki.')
      .max(80, 'Nazwa użytkownika może mieć maksymalnie 80 znaków.'),
    email: z
      .string()
      .trim()
      .min(1, 'Adres e-mail jest wymagany.')
      .email('Podaj poprawny adres e-mail.'),
    password: z
      .string()
      .min(1, 'Hasło jest wymagane.')
      .min(8, 'Hasło musi mieć co najmniej 8 znaków.')
      .max(128, 'Hasło może mieć maksymalnie 128 znaków.'),
    confirm_password: z.string().min(1, 'Powtórzenie hasła jest wymagane.'),
  })
  .superRefine((values, context) => {
    if (
      values.confirm_password.length > 0 &&
      values.confirm_password !== values.password
    ) {
      context.addIssue({
        code: 'custom',
        path: ['confirm_password'],
        message: 'Hasła muszą być identyczne.',
      })
    }
  })

export const loginFormDefaultValues: LoginFormValues = {
  identifier: '',
  password: '',
}

export const registerFormDefaultValues: RegisterFormValues = {
  display_name: '',
  email: '',
  password: '',
  confirm_password: '',
}
