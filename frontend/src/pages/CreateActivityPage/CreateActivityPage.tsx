import { useEffect, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import dayjs from 'dayjs'
import 'dayjs/locale/pl'
import {
  Alert,
  Button,
  Card,
  CardContent,
  FormControlLabel,
  InputAdornment,
  MenuItem,
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs'
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker'
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider'
import { Controller, useForm, useWatch } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'
import { mockCategories } from '../../data/mockCategories'
import type { CreateActivityFormValues } from '../../types/createActivityForm'
import './CreateActivityPage.css'

const createActivitySchema = z
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
    start_at: z.string().min(1, 'Data rozpoczęcia jest wymagana'),
    end_at: z.string().min(1, 'Data zakończenia jest wymagana'),
    location_name: z.string().min(1, 'Nazwa miejsca jest wymagana'),
    address: z.string().min(1, 'Adres jest wymagany'),
    min_participants: z
      .number({ error: 'Minimalna liczba uczestników jest wymagana' })
      .int('Liczba uczestników musi być całkowita')
      .min(2, 'Minimalna liczba uczestników to 2')
      .max(100, 'Maksymalna liczba uczestników to 100'),
    has_participant_limit: z.boolean(),
    max_participants: z.number().nullable(),
    price_type: z.enum(['FREE', 'PAID']),
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

    if (values.has_participant_limit) {
      if (values.max_participants === null) {
        context.addIssue({
          code: 'custom',
          path: ['max_participants'],
          message: 'Maksymalna liczba uczestników jest wymagana',
        })
      } else if (!Number.isInteger(values.max_participants)) {
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

const defaultValues: CreateActivityFormValues = {
  title: '',
  description: '',
  category_id: '',
  start_at: '',
  end_at: '',
  location_name: '',
  address: '',
  min_participants: 2,
  has_participant_limit: false,
  max_participants: null,
  price_type: 'FREE',
  price_amount: null,
}

function CreateActivityPage() {
  const [isSubmitted, setIsSubmitted] = useState(false)

  const {
    control,
    register,
    handleSubmit,
    setValue,
    clearErrors,
    formState: { errors },
  } = useForm<CreateActivityFormValues>({
    resolver: zodResolver(createActivitySchema),
    defaultValues,
  })

  const priceType = useWatch({
    control,
    name: 'price_type',
  })
  const hasParticipantLimit = useWatch({
    control,
    name: 'has_participant_limit',
  })
  const startAt = useWatch({
    control,
    name: 'start_at',
  })

  useEffect(() => {
    if (priceType === 'FREE') {
      setValue('price_amount', null)
      clearErrors('price_amount')
    }
  }, [clearErrors, priceType, setValue])

  useEffect(() => {
    if (hasParticipantLimit) {
      setValue('max_participants', 10)
    } else {
      setValue('max_participants', null)
      clearErrors('max_participants')
    }
  }, [clearErrors, hasParticipantLimit, setValue])

  function submitForm() {
    setIsSubmitted(true)
  }

  return (
    <main className="create-activity-page">
      <div className="create-activity-page__heading">
        <div>
          <Typography component="h1" variant="h4">
            Dodaj aktywność
          </Typography>
          <Typography color="text.secondary">
            Uzupełnij podstawowe informacje o planowanej aktywności.
          </Typography>
        </div>

        <Button component={Link} to="/">
          Wróć do listy
        </Button>
      </div>

      {isSubmitted && (
        <Alert severity="success">
          Formularz jest poprawny. Zapis aktywności zostanie uruchomiony po
          integracji z backendem.
        </Alert>
      )}

      <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="pl">
        <form
          className="create-activity-form"
          onSubmit={handleSubmit(submitForm)}
          noValidate
        >
          <Card component="section" variant="outlined">
            <CardContent>
              <Typography component="h2" variant="h6" gutterBottom>
                Informacje podstawowe
              </Typography>

              <div className="create-activity-form__fields">
                <TextField
                  label="Tytuł"
                  error={Boolean(errors.title)}
                  helperText={errors.title?.message}
                  {...register('title')}
                />

                <TextField
                  label="Opis"
                  multiline
                  minRows={4}
                  error={Boolean(errors.description)}
                  helperText={errors.description?.message}
                  {...register('description')}
                />

                <Controller
                  name="category_id"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      select
                      label="Kategoria"
                      error={Boolean(errors.category_id)}
                      helperText={errors.category_id?.message}
                    >
                      {mockCategories.map((category) => (
                        <MenuItem key={category.id} value={category.id}>
                          {category.name}
                        </MenuItem>
                      ))}
                    </TextField>
                  )}
                />
              </div>
            </CardContent>
          </Card>

          <Card component="section" variant="outlined">
            <CardContent>
              <Typography component="h2" variant="h6" gutterBottom>
                Termin i miejsce
              </Typography>

              <div className="create-activity-form__grid">
                <Controller
                  name="start_at"
                  control={control}
                  render={({ field }) => (
                    <DateTimePicker
                      label="Data i godzina rozpoczęcia"
                      value={field.value ? dayjs(field.value) : null}
                      onChange={(value) =>
                        field.onChange(value ? value.toISOString() : '')
                      }
                      format="DD.MM.YYYY HH:mm"
                      ampm={false}
                      disablePast
                      slotProps={{
                        textField: {
                          error: Boolean(errors.start_at),
                          helperText: errors.start_at?.message,
                        },
                      }}
                    />
                  )}
                />

                <Controller
                  name="end_at"
                  control={control}
                  render={({ field }) => (
                    <DateTimePicker
                      label="Data i godzina zakończenia"
                      value={field.value ? dayjs(field.value) : null}
                      onChange={(value) =>
                        field.onChange(value ? value.toISOString() : '')
                      }
                      format="DD.MM.YYYY HH:mm"
                      ampm={false}
                      disablePast
                      minDateTime={startAt ? dayjs(startAt) : undefined}
                      slotProps={{
                        textField: {
                          error: Boolean(errors.end_at),
                          helperText: errors.end_at?.message,
                        },
                      }}
                    />
                  )}
                />

                <TextField
                  label="Nazwa miejsca"
                  error={Boolean(errors.location_name)}
                  helperText={errors.location_name?.message}
                  {...register('location_name')}
                />

                <TextField
                  label="Adres"
                  error={Boolean(errors.address)}
                  helperText={errors.address?.message}
                  {...register('address')}
                />
              </div>
            </CardContent>
          </Card>

          <Card component="section" variant="outlined">
            <CardContent>
              <Typography component="h2" variant="h6" gutterBottom>
                Uczestnicy i cena
              </Typography>

              <div className="create-activity-form__grid">
                <Controller
                  name="min_participants"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      label="Minimalna liczba uczestników"
                      type="number"
                      error={Boolean(errors.min_participants)}
                      helperText={errors.min_participants?.message}
                      onChange={(event) =>
                        field.onChange(Number(event.target.value))
                      }
                    />
                  )}
                />

                <Controller
                  name="has_participant_limit"
                  control={control}
                  render={({ field }) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.value}
                          onChange={(_, checked) => field.onChange(checked)}
                        />
                      }
                      label="Ogranicz liczbę uczestników"
                    />
                  )}
                />

                {hasParticipantLimit && (
                  <Controller
                    name="max_participants"
                    control={control}
                    render={({ field }) => (
                      <TextField
                        {...field}
                        value={field.value ?? ''}
                        label="Maksymalna liczba uczestników"
                        type="number"
                        error={Boolean(errors.max_participants)}
                        helperText={errors.max_participants?.message}
                        onChange={(event) =>
                          field.onChange(
                            event.target.value === ''
                              ? null
                              : Number(event.target.value),
                          )
                        }
                      />
                    )}
                  />
                )}

                <Controller
                  name="price_type"
                  control={control}
                  render={({ field }) => (
                    <ToggleButtonGroup
                      {...field}
                      exclusive
                      aria-label="Rodzaj aktywności"
                      onChange={(_, value: 'FREE' | 'PAID' | null) => {
                        if (value !== null) {
                          field.onChange(value)
                        }
                      }}
                    >
                      <ToggleButton value="FREE">Bezpłatna</ToggleButton>
                      <ToggleButton value="PAID">Płatna</ToggleButton>
                    </ToggleButtonGroup>
                  )}
                />

                {priceType === 'PAID' && (
                  <Controller
                    name="price_amount"
                    control={control}
                    render={({ field }) => (
                      <TextField
                        {...field}
                        value={field.value ?? ''}
                        label="Cena"
                        type="number"
                        error={Boolean(errors.price_amount)}
                        helperText={errors.price_amount?.message}
                        onChange={(event) =>
                          field.onChange(
                            event.target.value === ''
                              ? null
                              : Number(event.target.value),
                          )
                        }
                        slotProps={{
                          htmlInput: {
                            min: 0.01,
                            step: 0.01,
                            inputMode: 'decimal',
                          },
                          input: {
                            endAdornment: (
                              <InputAdornment position="end">
                                PLN
                              </InputAdornment>
                            ),
                          },
                        }}
                      />
                    )}
                  />
                )}
              </div>
            </CardContent>
          </Card>

          <div className="create-activity-form__actions">
            <Button type="submit" variant="contained">
              Utwórz aktywność
            </Button>
          </div>
        </form>
      </LocalizationProvider>
    </main>
  )
}

export default CreateActivityPage
