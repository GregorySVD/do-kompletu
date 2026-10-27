import { TextField } from '@mui/material'
import type { FieldErrors, UseFormRegister } from 'react-hook-form'
import type { ActivityFormValues } from '../../../../types/activityForm'
import ActivityFormSection from '../ActivityFormSection/ActivityFormSection'
import ActivityLocationPicker from '../ActivityLocationPicker/ActivityLocationPicker'

interface ActivityLocationSectionProps {
  disabled: boolean
  errors: FieldErrors<ActivityFormValues>
  latitude: number | null
  longitude: number | null
  onLocationChange: (latitude: number, longitude: number) => void
  register: UseFormRegister<ActivityFormValues>
}

function ActivityLocationSection({
  disabled,
  errors,
  latitude,
  longitude,
  onLocationChange,
  register,
}: ActivityLocationSectionProps) {
  const locationError = errors.latitude?.message ?? errors.longitude?.message

  return (
    <ActivityFormSection
      step="03"
      title="Miejsce spotkania"
      description="Nazwij miejsce, podaj czytelny adres i zaznacz dokładny punkt na mapie."
      iconSrc="/icons/icons8-place-64.png"
    >
      <div className="activity-form__grid">
        <TextField
          className="activity-form__field"
          label="Nazwa miejsca"
          placeholder="Np. Biblioteka Raczyńskich"
          disabled={disabled}
          error={Boolean(errors.location_name)}
          helperText={
            errors.location_name?.message ??
            'Krótka nazwa widoczna na karcie aktywności.'
          }
          {...register('location_name')}
        />

        <TextField
          className="activity-form__field"
          label="Adres"
          placeholder="Np. pl. Wolności 19, Poznań"
          disabled={disabled}
          error={Boolean(errors.address)}
          helperText={
            errors.address?.message ?? 'Podaj ulicę, numer oraz miejscowość.'
          }
          {...register('address')}
        />
      </div>

      <div className="activity-form__map-field">
        <ActivityLocationPicker
          disabled={disabled}
          error={locationError}
          latitude={latitude}
          longitude={longitude}
          onLocationChange={onLocationChange}
        />
      </div>
    </ActivityFormSection>
  )
}

export default ActivityLocationSection
