export type ActivityStatus = 'PUBLISHED' | 'ONGOING' | 'ENDED' | 'CANCELLED'

export type ActivityParticipationStatus =
  | 'WAITLISTED'
  | 'JOINED'
  | 'CONFIRMED'
  | 'CHECKED_IN'
  | 'COMPLETED'
  | 'NO_SHOW'
  | 'CONFIRMATION_EXPIRED'
  | 'WAITLIST_EXPIRED'

export const priceTypes = ['FREE', 'PAID'] as const
export type PriceType = (typeof priceTypes)[number]

export interface ActivityCategory {
  id: string
  name: string
  slug: string
}

export interface CreateActivityPayload {
  title: string
  description: string
  category_id: string
  start_at: string
  end_at: string
  location_name: string
  address: string
  latitude: number
  longitude: number
  min_participants: number
  has_participant_limit: boolean
  max_participants: number | null
  price_type: PriceType
  price_amount: number | null
}

export interface UpdateActivityPayload {
  title?: string
  description?: string
  category_id?: string
  start_at?: string
  end_at?: string
  location_name?: string
  address?: string
  latitude?: number
  longitude?: number
  min_participants?: number
  has_participant_limit?: boolean
  max_participants?: number | null
  price_type?: PriceType
  price_amount?: number | null
}

export interface CheckInActivityPayload {
  latitude: number
  longitude: number
  accuracy_m: number
}

export interface Activity {
  id: string
  title: string
  category: ActivityCategory
  start_at: string
  end_at: string
  location_name: string
  address: string
  latitude: number
  longitude: number
  distance_m: number | null
  price_type: PriceType
  min_participants: number
  max_participants: number | null
  participant_count: number
  checked_in_count: number
  waitlist_count: number
  available_slots: number | null
  status: ActivityStatus
}

export interface ActivityOrganizer {
  id: string
  display_name: string
  avatar_url: string | null
}

export interface ActivityTag {
  id: string
  name: string
  slug: string
}

export interface ActivityParticipation {
  status: ActivityParticipationStatus
  joined_at: string | null
  waitlisted_at: string | null
  waitlist_position: number | null
  effective_confirmation_deadline_at: string | null
  confirmation_expired_at: string | null
  waitlist_expired_at: string | null
  confirmed_at: string | null
  checked_in_at: string | null
  completed_at: string | null
  no_show_at: string | null
}

export interface ActivityPermissions {
  can_edit: boolean
  can_cancel: boolean
  can_finalize: boolean
  can_delete: boolean
  can_join: boolean
  can_leave: boolean
  can_confirm: boolean
  can_check_in: boolean
  can_view_gallery: boolean
  can_upload_photo: boolean
}

export interface ActivityDetails extends Activity {
  cancelled_at: string | null
  description: string
  organizer: ActivityOrganizer
  tags: ActivityTag[]
  confirmation_opens_at: string | null
  confirmation_deadline_at: string | null
  checkin_opens_at: string | null
  checkin_closes_at: string | null
  checkin_radius_m: number | null
  price_amount: number | null
  currency: string | null
  current_user_participation: ActivityParticipation | null
  permissions: ActivityPermissions
}
