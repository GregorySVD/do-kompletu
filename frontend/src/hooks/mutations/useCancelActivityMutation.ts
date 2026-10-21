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
    onSuccess: async (activity) => {
      queryClient.setQueryData(
        getActivityDetailsQueryKey(activity.id),
        activity,
      )

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: activitiesQueryKey,
          exact: true,
        }),
        user?.id
          ? queryClient.invalidateQueries({
              queryKey: getMyActivitiesUserQueryKey(user.id),
            })
          : Promise.resolve(),
      ])
    },
    onError: (error, activityId) => {
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        void queryClient.invalidateQueries({
          queryKey: getActivityDetailsQueryKey(activityId),
        })
      }
    },
  })
}
