import { useQuery } from '@tanstack/react-query'
import { getActivityById } from '../../api/activitiesApi'
import { useAuth } from '../../context/auth'

const lifecycleRefetchIntervalMs = 45_000

interface ActivityDetailsQueryOptions {
  enableLifecyclePolling?: boolean
}

export function getActivityDetailsQueryKey(
  activityId: string,
  userId?: string,
) {
  return ['activity-details', userId ?? 'anonymous', activityId] as const
}

export function useActivityDetailsQuery(
  activityId: string,
  { enableLifecyclePolling = false }: ActivityDetailsQueryOptions = {},
) {
  const { isLoading, user } = useAuth()
  const canLoadActivity = activityId !== '' && !isLoading
  const canPollLifecycle =
    canLoadActivity && user !== null && enableLifecyclePolling

  return useQuery({
    queryKey: getActivityDetailsQueryKey(activityId, user?.id),
    queryFn: () => getActivityById(activityId),
    enabled: canLoadActivity,
    staleTime: 60_000,
    retry: false,
    refetchInterval: canPollLifecycle ? lifecycleRefetchIntervalMs : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })
}
