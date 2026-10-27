import {
  FormControlLabel,
  InputAdornment,
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material'
import { Controller } from 'react-hook-form'
import type { Control, FieldErrors } from 'react-hook-form'
import type { PriceType } from '../../../../types/activity'
import type { ActivityFormValues } from '../../../../types/activityForm'
import ActivityFormSection from '../ActivityFormSection/ActivityFormSection'

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
    <ActivityFormSection
      step="04"
      title="Uczestnicy i koszt"
      description="Ustal, ile osób potrzeba do organizacji spotkania i czy udział jest płatny."
      iconSrc="/icons/icons8-avatar-64.png"
    >
      <div className="activity-form__fields">
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
                helperText={
                  errors.min_participants?.message ??
                  'Tyle osób potrzeba, aby aktywność mogła się odbyć.'
                }
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
                className="activity-form__switch-card"
                control={
                  <Switch
                    checked={field.value}
                    disabled={disabled}
                    onChange={(_, checked) => field.onChange(checked)}
                  />
                }
                label={
                  <span>
                    <strong>Ustaw limit miejsc</strong>
                    <small>
                      Po zapełnieniu limitu kolejne osoby trafią na listę
                      rezerwową.
                    </small>
                  </span>
                }
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
        </div>

        <div className="activity-form__choice-field">
          <div>
            <span className="activity-form__choice-label">Koszt udziału</span>
            <span className="activity-form__choice-hint">
              Jeśli wybierzesz opcję płatną, podaj koszt dla jednej osoby.
            </span>
          </div>

          <div className="activity-form__price-row">
            <Controller
              name="price_type"
              control={control}
              render={({ field }) => (
                <ToggleButtonGroup
                  {...field}
                  className="activity-form__price-toggle"
                  exclusive
                  disabled={disabled}
                  aria-label="Koszt udziału"
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
        </div>
      </div>
    </ActivityFormSection>
  )
}

export default ActivityParticipantsPriceSection
