export interface CreateActivityFormValues {
  title: string
  description: string
  category_id: string
  start_at: string
  end_at: string
  location_name: string
  address: string
  min_participants: number
  has_participant_limit: boolean
  max_participants: number | null
  price_type: 'FREE' | 'PAID'
  price_amount: number | null
}
