import { useQuery } from '@tanstack/react-query'
import {
  getMyActivities,
  type ActivityRelation,
  type ActivityScope,
} from '../../api/userActivitiesApi'
import { useAuth } from '../../context/auth'

const myActivitiesLimit = 100
const myActivitiesOffset = 0
const lifecycleRefetchIntervalMs = 45_000
export const myActivitiesQueryKey = ['my-activities'] as const

interface MyActivitiesQueryOptions {
  enableLifecyclePolling?: boolean
}

export function getMyActivitiesUserQueryKey(userId: string) {
  return [...myActivitiesQueryKey, userId] as const
}

export function getMyActivitiesQueryKey(
  userId: string | undefined,
  relation: ActivityRelation,
  scope?: ActivityScope,
) {
  return [...myActivitiesQueryKey, userId, relation, scope ?? 'all'] as const
}

export function useMyActivitiesQuery(
  relation: ActivityRelation,
  scope?: ActivityScope,
  { enableLifecyclePolling = false }: MyActivitiesQueryOptions = {},
) {
  const { isLoading, user } = useAuth()
  const canLoadPrivateActivities = !isLoading && Boolean(user?.id)

  return useQuery({
    queryKey: getMyActivitiesQueryKey(user?.id, relation, scope),
    queryFn: () =>
      getMyActivities({
        relation,
        scope,
        limit: myActivitiesLimit,
        offset: myActivitiesOffset,
      }),
    enabled: canLoadPrivateActivities,
    staleTime: 60_000,
    retry: 1,
    refetchInterval:
      canLoadPrivateActivities && enableLifecyclePolling
        ? lifecycleRefetchIntervalMs
        : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })
}
