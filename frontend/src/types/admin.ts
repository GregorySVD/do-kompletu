import type { ActivityOrganizer, ActivityStatus } from './activity'

export interface AdminPaginationParams {
  limit: number
  offset: number
}

export interface AdminUser {
  id: string
  email: string
  display_name: string
  is_active: boolean
  is_admin: boolean
  points_total: number
  created_at: string
}

export interface SetAdminUserActivePayload {
  is_active: boolean
}

export interface AdminActivity {
  id: string
  title: string
  organizer: ActivityOrganizer
  status: ActivityStatus
  start_at: string
  end_at: string
  cancelled_at: string | null
  participant_count: number
  waitlist_count: number
  created_at: string
}
