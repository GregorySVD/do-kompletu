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
  max_participants: number
  participant_count: number
  checked_in_count: number
  waitlist_count: number
  available_slots: number
  status: ActivityStatus
}
