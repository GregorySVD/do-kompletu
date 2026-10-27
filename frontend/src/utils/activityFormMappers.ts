import type { ActivityDetails, CreateActivityPayload } from '../types/activity'
import type { ActivityFormValues } from '../types/activityForm'

export const activityFormDefaultValues: ActivityFormValues = {
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

export function mapActivityToFormValues(
  activity: ActivityDetails,
): ActivityFormValues {
  return {
    title: activity.title,
    description: activity.description,
    category_id: activity.category.id,
    start_at: activity.start_at,
    end_at: activity.end_at,
    location_name: activity.location_name,
    address: activity.address,
    latitude: activity.latitude,
    longitude: activity.longitude,
    min_participants: activity.min_participants,
    has_participant_limit: activity.max_participants !== null,
    max_participants: activity.max_participants,
    price_type: activity.price_type,
    price_amount: activity.price_amount,
  }
}

export function mapActivityFormValuesToPayload(
  values: ActivityFormValues,
): CreateActivityPayload | null {
  if (values.latitude === null || values.longitude === null) {
    return null
  }

  return {
    title: values.title.trim(),
    description: values.description.trim(),
    category_id: values.category_id,
    start_at: values.start_at,
    end_at: values.end_at,
    location_name: values.location_name.trim(),
    address: values.address.trim(),
    latitude: values.latitude,
    longitude: values.longitude,
    min_participants: values.min_participants,
    has_participant_limit: values.has_participant_limit,
    max_participants: values.max_participants,
    price_type: values.price_type,
    price_amount: values.price_amount,
  }
}
