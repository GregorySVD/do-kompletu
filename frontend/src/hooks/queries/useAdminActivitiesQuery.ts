import { useQuery } from '@tanstack/react-query'
import { getAdminActivities } from '../../api/adminApi'
import { useAuth } from '../../context/auth'
import type { AdminPaginationParams } from '../../types/admin'
import { getAdminActivitiesQueryKey } from './adminQueryKeys'

const defaultAdminListLimit = 20
const defaultAdminListOffset = 0

type AdminActivitiesQueryOptions = Partial<AdminPaginationParams>

export function useAdminActivitiesQuery({
  limit = defaultAdminListLimit,
  offset = defaultAdminListOffset,
}: AdminActivitiesQueryOptions = {}) {
  const { isLoading, user } = useAuth()
  const adminId = user?.id ?? 'unauthenticated'
  const canLoadAdminData = !isLoading && user !== null && user.is_admin === true

  return useQuery({
    queryKey: getAdminActivitiesQueryKey(adminId, limit, offset),
    queryFn: ({ signal }) => getAdminActivities({ limit, offset }, signal),
    enabled: canLoadAdminData,
    staleTime: 30_000,
    retry: false,
  })
}
