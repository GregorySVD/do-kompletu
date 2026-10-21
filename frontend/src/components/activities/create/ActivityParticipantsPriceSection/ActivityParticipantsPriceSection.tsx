import {
  Card,
  CardContent,
  FormControlLabel,
  InputAdornment,
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import { Controller } from 'react-hook-form'
import type { Control, FieldErrors } from 'react-hook-form'
import type { PriceType } from '../../../../types/activity'
import type { ActivityFormValues } from '../../../../types/activityForm'

interface ActivityParticipantsPriceSectionProps {
  control: Control<ActivityFormValues>
  disabled: boolean
  errors: FieldErrors<ActivityFormValues>
  hasParticipantLimit: boolean
  priceType: PriceType
}

function ActivityParticipantsPriceSection({
  control,
  disabled,
  errors,
  hasParticipantLimit,
  priceType,
}: ActivityParticipantsPriceSectionProps) {
  return (
    <Card component="section" variant="outlined">
      <CardContent>
        <Typography component="h2" variant="h6" gutterBottom>
          Uczestnicy i cena
        </Typography>

        <div className="activity-form__grid">
          <Controller
            name="min_participants"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Minimalna liczba uczestników"
                type="number"
                disabled={disabled}
                error={Boolean(errors.min_participants)}
                helperText={errors.min_participants?.message}
                onChange={(event) => field.onChange(Number(event.target.value))}
                slotProps={{
                  htmlInput: {
                    min: 2,
                    max: 100,
                    step: 1,
                    inputMode: 'numeric',
                  },
                }}
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
                    disabled={disabled}
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
                  disabled={disabled}
                  error={Boolean(errors.max_participants)}
                  helperText={errors.max_participants?.message}
                  onChange={(event) =>
                    field.onChange(
                      event.target.value === ''
                        ? null
                        : Number(event.target.value),
                    )
                  }
                  slotProps={{
                    htmlInput: {
                      min: 2,
                      max: 100,
                      step: 1,
                      inputMode: 'numeric',
                    },
                  }}
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
                disabled={disabled}
                aria-label="Rodzaj aktywności"
                onChange={(_, value: PriceType | null) => {
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
                  disabled={disabled}
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
                        <InputAdornment position="end">PLN</InputAdornment>
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
  )
}

export default ActivityParticipantsPriceSection
