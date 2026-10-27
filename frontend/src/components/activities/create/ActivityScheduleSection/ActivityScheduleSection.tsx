import dayjs from 'dayjs'
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker'
import { Controller, useWatch } from 'react-hook-form'
import type { Control, FieldErrors } from 'react-hook-form'
import type { ActivityFormValues } from '../../../../types/activityForm'
import ActivityFormSection from '../ActivityFormSection/ActivityFormSection'
import './ActivityScheduleSection.css'

interface ActivityScheduleSectionProps {
  control: Control<ActivityFormValues>
  disabled: boolean
  errors: FieldErrors<ActivityFormValues>
}

function formatDuration(startAt: string, endAt: string) {
  if (!startAt || !endAt) {
    return null
  }

  const start = dayjs(startAt)
  const end = dayjs(endAt)
  const durationMinutes = end.diff(start, 'minute')

  if (durationMinutes <= 0) {
    return null
  }

  const hours = Math.floor(durationMinutes / 60)
  const minutes = durationMinutes % 60

  if (hours === 0) {
    return `${minutes} min`
  }

  if (minutes === 0) {
    return `${hours} godz.`
  }

  return `${hours} godz. ${minutes} min`
}

function ActivityScheduleSection({
  control,
  disabled,
  errors,
}: ActivityScheduleSectionProps) {
  const startAt = useWatch({ control, name: 'start_at' })
  const endAt = useWatch({ control, name: 'end_at' })
  const duration = formatDuration(startAt, endAt)

  return (
    <ActivityFormSection
      step="02"
      title="Termin aktywności"
      description="Podaj godzinę rozpoczęcia i przewidywany koniec, aby uczestnicy mogli zaplanować swój czas."
      iconSrc="/icons/icons8-schedule-64.png"
    >
      <div className="activity-form__grid">
        <Controller
          name="start_at"
          control={control}
          render={({ field }) => (
            <DateTimePicker
              label="Rozpoczęcie"
              value={field.value ? dayjs(field.value) : null}
              onChange={(value) =>
                field.onChange(value ? value.toISOString() : '')
              }
              disabled={disabled}
              format="DD.MM.YYYY HH:mm"
              ampm={false}
              disablePast
              minutesStep={5}
              slotProps={{
                textField: {
                  className: 'activity-form__field',
                  error: Boolean(errors.start_at),
                  helperText:
                    errors.start_at?.message ??
                    'Kiedy uczestnicy powinni pojawić się na miejscu?',
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
              label="Przewidywane zakończenie"
              value={field.value ? dayjs(field.value) : null}
              onChange={(value) =>
                field.onChange(value ? value.toISOString() : '')
              }
              disabled={disabled}
              format="DD.MM.YYYY HH:mm"
              ampm={false}
              disablePast
              minDateTime={startAt ? dayjs(startAt) : undefined}
              minutesStep={5}
              slotProps={{
                textField: {
                  className: 'activity-form__field',
                  error: Boolean(errors.end_at),
                  helperText:
                    errors.end_at?.message ??
                    'Realistyczne oszacowanie ułatwia innym decyzję.',
                },
              }}
            />
          )}
        />
      </div>

      <div
        className={`activity-schedule-section__duration${duration ? ' activity-schedule-section__duration--ready' : ''}`}
        aria-live="polite"
      >
        <img
          src="/icons/icons8-finish-64.png"
          alt=""
          width="64"
          height="64"
          aria-hidden="true"
        />
        <span>
          <strong>Przewidywany czas trwania</strong>
          {duration ?? 'Pojawi się po wybraniu poprawnego terminu.'}
        </span>
      </div>
    </ActivityFormSection>
  )
}

export default ActivityScheduleSection
