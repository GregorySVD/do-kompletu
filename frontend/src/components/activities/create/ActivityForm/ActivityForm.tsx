import { useEffect, useRef } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import 'dayjs/locale/pl'
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs'
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider'
import { useForm, useWatch } from 'react-hook-form'
import type { ActivityCategory } from '../../../../types/activity'
import type { ActivityFormValues } from '../../../../types/activityForm'
import { activityFormDefaultValues } from '../../../../utils/activityFormMappers'
import { activityFormSchema } from '../../../../validation/activityFormSchema'
import ActivityBasicInfoSection from '../ActivityBasicInfoSection/ActivityBasicInfoSection'
import ActivityFormSubmitBar from '../ActivityFormSubmitBar/ActivityFormSubmitBar'
import ActivityFormSummary from '../ActivityFormSummary/ActivityFormSummary'
import ActivityLocationSection from '../ActivityLocationSection/ActivityLocationSection'
import ActivityParticipantsPriceSection from '../ActivityParticipantsPriceSection/ActivityParticipantsPriceSection'
import ActivityScheduleSection from '../ActivityScheduleSection/ActivityScheduleSection'
import './ActivityForm.css'

interface ActivityFormProps {
  categories: ActivityCategory[]
  initialValues?: ActivityFormValues
  disabled?: boolean
  submitLabel: string
  submitIconSrc?: string
  submittingLabel: string
  onSubmit: (values: ActivityFormValues) => void | Promise<void>
}

const requiredFormElementCount = 10

function isValidDate(value: string) {
  return value !== '' && !Number.isNaN(Date.parse(value))
}

function getCompletedFormElementCount(values: ActivityFormValues) {
  const participantSettingsAreValid =
    Number.isInteger(values.min_participants) &&
    values.min_participants >= 2 &&
    values.min_participants <= 100 &&
    (!values.has_participant_limit ||
      (values.max_participants !== null &&
        Number.isInteger(values.max_participants) &&
        values.max_participants >= values.min_participants &&
        values.max_participants <= 100))
  const priceSettingsAreValid =
    values.price_type === 'FREE' ||
    (values.price_amount !== null && values.price_amount > 0)
  const checks = [
    values.title.trim().length >= 3,
    values.description.trim().length >= 10,
    values.category_id !== '',
    isValidDate(values.start_at),
    isValidDate(values.end_at) &&
      new Date(values.end_at) > new Date(values.start_at),
    values.location_name.trim().length > 0,
    values.address.trim().length > 0,
    values.latitude !== null && values.longitude !== null,
    participantSettingsAreValid,
    priceSettingsAreValid,
  ]

  return checks.filter(Boolean).length
}

function ActivityForm({
  categories,
  initialValues = activityFormDefaultValues,
  disabled = false,
  submitLabel,
  submitIconSrc = '/icons/icons8-add-64.png',
  submittingLabel,
  onSubmit,
}: ActivityFormProps) {
  const {
    clearErrors,
    control,
    formState: { errors, isSubmitting, isValid },
    handleSubmit,
    register,
    setValue,
    trigger,
  } = useForm<ActivityFormValues>({
    resolver: zodResolver(activityFormSchema),
    defaultValues: initialValues,
    mode: 'onChange',
    reValidateMode: 'onChange',
  })

  const watchedValues = useWatch({ control })
  const values: ActivityFormValues = {
    ...initialValues,
    ...watchedValues,
  }
  const priceType = useWatch({ control, name: 'price_type' })
  const hasParticipantLimit = useWatch({
    control,
    name: 'has_participant_limit',
  })
  const maxParticipants = useWatch({ control, name: 'max_participants' })
  const startAt = useWatch({ control, name: 'start_at' })
  const endAt = useWatch({ control, name: 'end_at' })
  const minParticipants = useWatch({ control, name: 'min_participants' })
  const latitude = useWatch({ control, name: 'latitude' })
  const longitude = useWatch({ control, name: 'longitude' })
  const formDisabled = disabled || isSubmitting
  const completedFieldCount = getCompletedFormElementCount(values)
  const previousHasParticipantLimit = useRef(hasParticipantLimit)

  useEffect(() => {
    if (priceType === 'FREE') {
      setValue('price_amount', null)
      clearErrors('price_amount')
    }
  }, [clearErrors, priceType, setValue])

  useEffect(() => {
    if (endAt) {
      void trigger('end_at')
    }
  }, [endAt, startAt, trigger])

  useEffect(() => {
    if (hasParticipantLimit && maxParticipants !== null) {
      void trigger('max_participants')
    }
  }, [hasParticipantLimit, maxParticipants, minParticipants, trigger])

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
        <div className="activity-form__layout">
          <div className="activity-form__sections">
            <ActivityBasicInfoSection
              categories={categories}
              control={control}
              disabled={formDisabled}
              errors={errors}
              register={register}
            />

            <ActivityScheduleSection
              control={control}
              disabled={formDisabled}
              errors={errors}
            />

            <ActivityLocationSection
              disabled={formDisabled}
              errors={errors}
              latitude={latitude}
              longitude={longitude}
              onLocationChange={handleLocationChange}
              register={register}
            />

            <ActivityParticipantsPriceSection
              control={control}
              disabled={formDisabled}
              errors={errors}
              hasParticipantLimit={hasParticipantLimit}
              priceType={priceType}
            />
          </div>

          <ActivityFormSummary
            categories={categories}
            completedFieldCount={completedFieldCount}
            requiredFieldCount={requiredFormElementCount}
            values={values}
          />
        </div>

        <ActivityFormSubmitBar
          completedFieldCount={completedFieldCount}
          disabled={formDisabled || !isValid}
          isSubmitting={formDisabled}
          requiredFieldCount={requiredFormElementCount}
          submitIconSrc={submitIconSrc}
          submitLabel={submitLabel}
          submittingLabel={submittingLabel}
        />
      </form>
    </LocalizationProvider>
  )
}

export default ActivityForm
