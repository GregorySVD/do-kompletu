import dayjs from 'dayjs'
import { Card, CardContent, TextField, Typography } from '@mui/material'
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker'
import { Controller } from 'react-hook-form'
import type { Control, FieldErrors, UseFormRegister } from 'react-hook-form'
import type { ActivityFormValues } from '../../../../types/activityForm'
import ActivityLocationPicker from '../ActivityLocationPicker/ActivityLocationPicker'
import './ActivityScheduleLocationSection.css'

interface ActivityScheduleLocationSectionProps {
  control: Control<ActivityFormValues>
  disabled: boolean
  errors: FieldErrors<ActivityFormValues>
  latitude: number | null
  longitude: number | null
  onLocationChange: (latitude: number, longitude: number) => void
  register: UseFormRegister<ActivityFormValues>
  startAt: string
}

function ActivityScheduleLocationSection({
  control,
  disabled,
  errors,
  latitude,
  longitude,
  onLocationChange,
  register,
  startAt,
}: ActivityScheduleLocationSectionProps) {
  const locationError = errors.latitude?.message ?? errors.longitude?.message

  return (
    <Card component="section" variant="outlined">
      <CardContent>
        <Typography component="h2" variant="h6" gutterBottom>
          Termin i miejsce
        </Typography>

        <div className="activity-form__grid">
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
                disabled={disabled}
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
                disabled={disabled}
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
            disabled={disabled}
            error={Boolean(errors.location_name)}
            helperText={errors.location_name?.message}
            {...register('location_name')}
          />

          <TextField
            label="Adres"
            disabled={disabled}
            error={Boolean(errors.address)}
            helperText={errors.address?.message}
            {...register('address')}
          />
        </div>

        <div className="activity-schedule-location-section__map">
          <ActivityLocationPicker
            disabled={disabled}
            error={locationError}
            latitude={latitude}
            longitude={longitude}
            onLocationChange={onLocationChange}
          />
        </div>
      </CardContent>
    </Card>
  )
}

export default ActivityScheduleLocationSection
