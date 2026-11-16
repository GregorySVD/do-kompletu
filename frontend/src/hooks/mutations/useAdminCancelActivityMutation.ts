import { useMutation, useQueryClient } from '@tanstack/react-query'
import { cancelAdminActivity } from '../../api/adminApi'
import { useAuth } from '../../context/auth'
import { getAdminActivitiesBaseQueryKey } from '../queries/adminQueryKeys'
import { activitiesQueryKey } from '../queries/useActivitiesQuery'
import { getMyActivitiesUserQueryKey } from '../queries/useMyActivitiesQuery'

export function useAdminCancelActivityMutation() {
  const queryClient = useQueryClient()
  const { user } = useAuth()

  return useMutation({
    mutationFn: cancelAdminActivity,
    onMutate: () => ({ adminId: user?.id }),
    onSuccess: async (activity, _activityId, mutationContext) => {
      const adminId = mutationContext?.adminId

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: activitiesQueryKey,
          exact: true,
        }),
        queryClient.invalidateQueries({
          predicate: (query) =>
            query.queryKey[0] === 'activity-details' &&
            query.queryKey[2] === activity.id,
        }),
        adminId
          ? queryClient.invalidateQueries({
              queryKey: getAdminActivitiesBaseQueryKey(adminId),
            })
          : Promise.resolve(),
        adminId
          ? queryClient.invalidateQueries({
              queryKey: getMyActivitiesUserQueryKey(adminId),
            })
          : Promise.resolve(),
      ])
    },
  })
}
