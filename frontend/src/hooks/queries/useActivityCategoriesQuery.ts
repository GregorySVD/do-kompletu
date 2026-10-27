import { useQuery } from '@tanstack/react-query'
import { getActivityCategories } from '../../api/activitiesApi'

const activityCategoriesQueryKey = ['activity-categories'] as const

export function useActivityCategoriesQuery(enabled = true) {
  return useQuery({
    queryKey: activityCategoriesQueryKey,
    queryFn: getActivityCategories,
    enabled,
    staleTime: 5 * 60_000,
    retry: 1,
  })
}
