import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { getActivityPhotos } from '../../api/activitiesApi'
import { useAuth } from '../../context/auth'

export function getActivityPhotosQueryKey(activityId: string, userId?: string) {
  return ['activity-photos', userId ?? 'anonymous', activityId] as const
}

export function useActivityPhotosQuery(
  activityId: string,
  canViewGallery: boolean,
) {
  const { isLoading, user } = useAuth()

  return useQuery({
    queryKey: getActivityPhotosQueryKey(activityId, user?.id),
    queryFn: () => getActivityPhotos(activityId),
    enabled: activityId !== '' && !isLoading && user !== null && canViewGallery,
    staleTime: 0,
    retry: (failureCount, error) => {
      if (
        axios.isAxiosError(error) &&
        (error.response?.status === 401 ||
          error.response?.status === 403 ||
          error.response?.status === 404)
      ) {
        return false
      }

      return failureCount < 1
    },
    refetchOnWindowFocus: true,
  })
}
