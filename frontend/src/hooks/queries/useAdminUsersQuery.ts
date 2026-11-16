import { useQuery } from '@tanstack/react-query'
import { getAdminUsers } from '../../api/adminApi'
import { useAuth } from '../../context/auth'
import type { AdminPaginationParams } from '../../types/admin'
import { getAdminUsersQueryKey } from './adminQueryKeys'

const defaultAdminListLimit = 20
const defaultAdminListOffset = 0

type AdminUsersQueryOptions = Partial<AdminPaginationParams>

export function useAdminUsersQuery({
  limit = defaultAdminListLimit,
  offset = defaultAdminListOffset,
}: AdminUsersQueryOptions = {}) {
  const { isLoading, user } = useAuth()
  const adminId = user?.id ?? 'unauthenticated'
  const canLoadAdminData = !isLoading && user !== null && user.is_admin === true

  return useQuery({
    queryKey: getAdminUsersQueryKey(adminId, limit, offset),
    queryFn: ({ signal }) => getAdminUsers({ limit, offset }, signal),
    enabled: canLoadAdminData,
    staleTime: 30_000,
    retry: false,
  })
}
