import { TextField } from '@mui/material'
import { Controller, useWatch } from 'react-hook-form'
import type { Control, FieldErrors, UseFormRegister } from 'react-hook-form'
import type { ActivityCategory } from '../../../../types/activity'
import type { ActivityFormValues } from '../../../../types/activityForm'
import ActivityCategorySelector from '../ActivityCategorySelector/ActivityCategorySelector'
import ActivityFormSection from '../ActivityFormSection/ActivityFormSection'

interface ActivityBasicInfoSectionProps {
  categories: ActivityCategory[]
  control: Control<ActivityFormValues>
  disabled: boolean
  errors: FieldErrors<ActivityFormValues>
  register: UseFormRegister<ActivityFormValues>
}

function ActivityBasicInfoSection({
  categories,
  control,
  disabled,
  errors,
  register,
}: ActivityBasicInfoSectionProps) {
  const title = useWatch({ control, name: 'title' })
  const description = useWatch({ control, name: 'description' })

  return (
    <ActivityFormSection
      step="01"
      title="Podstawowe informacje"
      description="Powiedz krótko, co organizujesz i wybierz najlepiej pasującą kategorię."
      iconSrc="/icons/icons8-add-64.png"
    >
      <div className="activity-form__fields">
        <TextField
          className="activity-form__field"
          label="Tytuł aktywności"
          placeholder="Np. Wieczór z planszówkami"
          disabled={disabled}
          error={Boolean(errors.title)}
          helperText={errors.title?.message ?? `${title.length}/80 znaków`}
          slotProps={{ htmlInput: { maxLength: 80 } }}
          {...register('title')}
        />

        <TextField
          className="activity-form__field"
          label="Opis"
          placeholder="Napisz, czego mogą spodziewać się uczestnicy i czy powinni coś ze sobą zabrać."
          disabled={disabled}
          multiline
          minRows={5}
          error={Boolean(errors.description)}
          helperText={
            errors.description?.message ?? `${description.length}/1000 znaków`
          }
          slotProps={{ htmlInput: { maxLength: 1000 } }}
          {...register('description')}
        />

        <div className="activity-form__choice-field">
          <div>
            <span className="activity-form__choice-label">Kategoria</span>
            <span className="activity-form__choice-hint">
              Kolor i ikona pomogą wyróżnić aktywność na liście.
            </span>
          </div>

          <Controller
            name="category_id"
            control={control}
            render={({ field }) => (
              <ActivityCategorySelector
                categories={categories}
                disabled={disabled}
                error={errors.category_id?.message}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
        </div>
      </div>
    </ActivityFormSection>
  )
}

export default ActivityBasicInfoSection
