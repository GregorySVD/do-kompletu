import {
  Card,
  CardContent,
  MenuItem,
  TextField,
  Typography,
} from '@mui/material'
import { Controller } from 'react-hook-form'
import type { Control, FieldErrors, UseFormRegister } from 'react-hook-form'
import type { ActivityCategory } from '../../../../types/activity'
import type { ActivityFormValues } from '../../../../types/activityForm'

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
  return (
    <Card component="section" variant="outlined">
      <CardContent>
        <Typography component="h2" variant="h6" gutterBottom>
          Informacje podstawowe
        </Typography>

        <div className="activity-form__fields">
          <TextField
            label="Tytuł"
            disabled={disabled}
            error={Boolean(errors.title)}
            helperText={errors.title?.message}
            {...register('title')}
          />

          <TextField
            label="Opis"
            disabled={disabled}
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
                disabled={disabled}
                label="Kategoria"
                error={Boolean(errors.category_id)}
                helperText={errors.category_id?.message}
              >
                {categories.map((category) => (
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
  )
}

export default ActivityBasicInfoSection
