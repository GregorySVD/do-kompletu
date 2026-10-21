import { useEffect, useRef } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import 'dayjs/locale/pl'
import { Button } from '@mui/material'
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs'
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider'
import { useForm, useWatch } from 'react-hook-form'
import type { ActivityCategory } from '../../../../types/activity'
import type { ActivityFormValues } from '../../../../types/activityForm'
import { activityFormSchema } from '../../../../validation/activityFormSchema'
import ActivityBasicInfoSection from '../ActivityBasicInfoSection/ActivityBasicInfoSection'
import ActivityParticipantsPriceSection from '../ActivityParticipantsPriceSection/ActivityParticipantsPriceSection'
import ActivityScheduleLocationSection from '../ActivityScheduleLocationSection/ActivityScheduleLocationSection'
import './ActivityForm.css'

interface ActivityFormProps {
  categories: ActivityCategory[]
  initialValues?: ActivityFormValues
  disabled?: boolean
  submitLabel: string
  submittingLabel: string
  onSubmit: (values: ActivityFormValues) => void | Promise<void>
}

const defaultActivityFormValues: ActivityFormValues = {
  title: '',
  description: '',
  category_id: '',
  start_at: '',
  end_at: '',
  location_name: '',
  address: '',
  latitude: null,
  longitude: null,
  min_participants: 2,
  has_participant_limit: false,
  max_participants: null,
  price_type: 'FREE',
  price_amount: null,
}

function ActivityForm({
  categories,
  initialValues = defaultActivityFormValues,
  disabled = false,
  submitLabel,
  submittingLabel,
  onSubmit,
}: ActivityFormProps) {
  const {
    clearErrors,
    control,
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    setValue,
  } = useForm<ActivityFormValues>({
    resolver: zodResolver(activityFormSchema),
    defaultValues: initialValues,
  })

  const priceType = useWatch({ control, name: 'price_type' })
  const hasParticipantLimit = useWatch({
    control,
    name: 'has_participant_limit',
  })
  const maxParticipants = useWatch({ control, name: 'max_participants' })
  const startAt = useWatch({ control, name: 'start_at' })
  const latitude = useWatch({ control, name: 'latitude' })
  const longitude = useWatch({ control, name: 'longitude' })
  const formDisabled = disabled || isSubmitting
  const previousHasParticipantLimit = useRef(hasParticipantLimit)

  useEffect(() => {
    if (priceType === 'FREE') {
      setValue('price_amount', null)
      clearErrors('price_amount')
    }
  }, [clearErrors, priceType, setValue])

  useEffect(() => {
    if (
      !previousHasParticipantLimit.current &&
      hasParticipantLimit &&
      maxParticipants === null
    ) {
      setValue('max_participants', 10)
    } else if (previousHasParticipantLimit.current && !hasParticipantLimit) {
      if (maxParticipants !== null) {
        setValue('max_participants', null)
      }
      clearErrors('max_participants')
    }

    previousHasParticipantLimit.current = hasParticipantLimit
  }, [clearErrors, hasParticipantLimit, maxParticipants, setValue])

  function handleLocationChange(nextLatitude: number, nextLongitude: number) {
    setValue('latitude', nextLatitude, {
      shouldDirty: true,
      shouldTouch: true,
      shouldValidate: true,
    })
    setValue('longitude', nextLongitude, {
      shouldDirty: true,
      shouldTouch: true,
      shouldValidate: true,
    })
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="pl">
      <form
        className="activity-form"
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        <ActivityBasicInfoSection
          categories={categories}
          control={control}
          disabled={formDisabled}
          errors={errors}
          register={register}
        />

        <ActivityScheduleLocationSection
          control={control}
          disabled={formDisabled}
          errors={errors}
          latitude={latitude}
          longitude={longitude}
          onLocationChange={handleLocationChange}
          register={register}
          startAt={startAt}
        />

        <ActivityParticipantsPriceSection
          control={control}
          disabled={formDisabled}
          errors={errors}
          hasParticipantLimit={hasParticipantLimit}
          priceType={priceType}
        />

        <div className="activity-form__actions">
          <Button disabled={formDisabled} type="submit" variant="contained">
            {formDisabled ? submittingLabel : submitLabel}
          </Button>
        </div>
      </form>
    </LocalizationProvider>
  )
}

export default ActivityForm
