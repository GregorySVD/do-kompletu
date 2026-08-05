export type PriceType = 'free' | 'paid'

export interface Activity {
  id: number
  title: string
  category: string
  start_at: string
  location_name: string
  price_type: PriceType
  max_participants: number
  participant_count: number
}
