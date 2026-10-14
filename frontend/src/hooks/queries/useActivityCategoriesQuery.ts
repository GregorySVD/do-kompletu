import { useQuery } from '@tanstack/react-query'
import { getActivityCategories } from '../../api/activitiesApi'

const activityCategoriesQueryKey = ['activity-categories'] as const

export function useActivityCategoriesQuery() {
  return useQuery({
    queryKey: activityCategoriesQueryKey,
    queryFn: getActivityCategories,
    staleTime: 5 * 60_000,
    retry: 1,
  })
}
