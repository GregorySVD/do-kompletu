import { z } from 'zod'
import { priceTypes } from '../types/activity'

const timezoneSuffixPattern = /(Z|[+-]\d{2}:\d{2})$/

function isTimezoneAwareIso(value: string) {
  return timezoneSuffixPattern.test(value) && !Number.isNaN(Date.parse(value))
}

export const activityFormSchema = z
  .object({
    title: z
      .string()
      .min(1, 'Tytuł jest wymagany')
      .min(3, 'Tytuł musi mieć co najmniej 3 znaki')
      .max(80, 'Tytuł może mieć maksymalnie 80 znaków'),
    description: z
      .string()
      .min(1, 'Opis jest wymagany')
      .min(10, 'Opis musi mieć co najmniej 10 znaków')
      .max(1000, 'Opis może mieć maksymalnie 1000 znaków'),
    category_id: z.string().min(1, 'Kategoria jest wymagana'),
    start_at: z
      .string()
      .min(1, 'Data rozpoczęcia jest wymagana')
      .refine(
        (value) => value === '' || isTimezoneAwareIso(value),
        'Data rozpoczęcia musi zawierać strefę czasową',
      ),
    end_at: z
      .string()
      .min(1, 'Data zakończenia jest wymagana')
      .refine(
        (value) => value === '' || isTimezoneAwareIso(value),
        'Data zakończenia musi zawierać strefę czasową',
      ),
    location_name: z
      .string()
      .min(1, 'Nazwa miejsca jest wymagana')
      .max(120, 'Nazwa miejsca może mieć maksymalnie 120 znaków'),
    address: z
      .string()
      .min(1, 'Adres jest wymagany')
      .max(300, 'Adres może mieć maksymalnie 300 znaków'),
    latitude: z.number().min(-90).max(90).nullable(),
    longitude: z.number().min(-180).max(180).nullable(),
    min_participants: z
      .number({ error: 'Minimalna liczba uczestników jest wymagana' })
      .int('Liczba uczestników musi być całkowita')
      .min(2, 'Minimalna liczba uczestników to 2')
      .max(100, 'Maksymalna liczba uczestników to 100'),
    has_participant_limit: z.boolean(),
    max_participants: z.number().nullable(),
    price_type: z.enum(priceTypes),
    price_amount: z.number().nullable(),
  })
  .superRefine((values, context) => {
    if (values.start_at && new Date(values.start_at) < new Date()) {
      context.addIssue({
        code: 'custom',
        path: ['start_at'],
        message: 'Data rozpoczęcia nie może być w przeszłości',
      })
    }

    if (
      values.start_at &&
      values.end_at &&
      new Date(values.end_at) <= new Date(values.start_at)
    ) {
      context.addIssue({
        code: 'custom',
        path: ['end_at'],
        message: 'Data zakończenia musi być późniejsza niż data rozpoczęcia',
      })
    }

    if (values.latitude === null || values.longitude === null) {
      context.addIssue({
        code: 'custom',
        path: ['latitude'],
        message: 'Wybierz lokalizację aktywności na mapie.',
      })
    }

    if (values.has_participant_limit && values.max_participants === null) {
      context.addIssue({
        code: 'custom',
        path: ['max_participants'],
        message: 'Maksymalna liczba uczestników jest wymagana',
      })
    }

    if (!values.has_participant_limit && values.max_participants !== null) {
      context.addIssue({
        code: 'custom',
        path: ['max_participants'],
        message: 'Brak limitu uczestników wymaga pustej wartości maksymalnej',
      })
    }

    if (values.max_participants !== null) {
      if (!Number.isInteger(values.max_participants)) {
        context.addIssue({
          code: 'custom',
          path: ['max_participants'],
          message: 'Liczba uczestników musi być całkowita',
        })
      } else if (values.max_participants < 2 || values.max_participants > 100) {
        context.addIssue({
          code: 'custom',
          path: ['max_participants'],
          message: 'Maksymalna liczba uczestników musi wynosić od 2 do 100',
        })
      } else if (values.max_participants < values.min_participants) {
        context.addIssue({
          code: 'custom',
          path: ['max_participants'],
          message:
            'Maksymalna liczba uczestników nie może być mniejsza od minimalnej',
        })
      }
    }

    if (values.price_type === 'FREE' && values.price_amount !== null) {
      context.addIssue({
        code: 'custom',
        path: ['price_amount'],
        message: 'Bezpłatna aktywność nie może mieć ustawionej ceny',
      })
    }

    if (values.price_type === 'PAID') {
      if (values.price_amount === null) {
        context.addIssue({
          code: 'custom',
          path: ['price_amount'],
          message: 'Cena jest wymagana dla płatnej aktywności',
        })
      } else if (values.price_amount <= 0) {
        context.addIssue({
          code: 'custom',
          path: ['price_amount'],
          message: 'Cena musi być większa od 0',
        })
      } else if (
        Number(values.price_amount.toFixed(2)) !== values.price_amount
      ) {
        context.addIssue({
          code: 'custom',
          path: ['price_amount'],
          message: 'Cena może mieć maksymalnie dwie cyfry po przecinku',
        })
      }
    }
  })
