import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { cancelActivity } from '../../api/activitiesApi'
import { useAuth } from '../../context/auth'
import { getActivityDetailsQueryKey } from '../queries/useActivityDetailsQuery'
import { activitiesQueryKey } from '../queries/useActivitiesQuery'
import { getMyActivitiesUserQueryKey } from '../queries/useMyActivitiesQuery'

export function useCancelActivityMutation() {
  const queryClient = useQueryClient()
  const { user } = useAuth()

  return useMutation({
    mutationFn: cancelActivity,
    onMutate: () => ({ userId: user?.id }),
    onSuccess: async (activity, _activityId, mutationContext) => {
      const userId = mutationContext?.userId

      queryClient.setQueryData(
        getActivityDetailsQueryKey(activity.id, userId),
        activity,
      )

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: activitiesQueryKey,
          exact: true,
        }),
        userId
          ? queryClient.invalidateQueries({
              queryKey: getMyActivitiesUserQueryKey(userId),
            })
          : Promise.resolve(),
      ])
    },
    onError: (error, activityId, mutationContext) => {
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        void queryClient.invalidateQueries({
          queryKey: getActivityDetailsQueryKey(
            activityId,
            mutationContext?.userId,
          ),
        })
      }
    },
  })
}
