export type ActivityStatus =
  'DRAFT' | 'PUBLISHED' | 'ONGOING' | 'ENDED' | 'CANCELLED'

export type PriceType = 'FREE' | 'PAID'

export interface ActivityCategory {
  id: string
  name: string
  slug: string
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

export interface ActivityPermissions {
  can_edit: boolean
  can_delete: boolean
  can_join: boolean
  can_leave: boolean
  can_confirm: boolean
  can_check_in: boolean
  can_view_gallery: boolean
  can_upload_photo: boolean
}

export interface ActivityDetails extends Activity {
  description: string
  organizer: ActivityOrganizer
  tags: ActivityTag[]
  confirmation_opens_at: string
  confirmation_deadline_at: string
  checkin_opens_at: string
  checkin_closes_at: string
  checkin_radius_m: number
  price_amount: number | null
  currency: string | null
  current_user_participation: null
  permissions: ActivityPermissions
}
