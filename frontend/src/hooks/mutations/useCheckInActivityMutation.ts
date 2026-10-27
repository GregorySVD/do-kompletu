import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { checkInActivity } from '../../api/activitiesApi'
import { useAuth } from '../../context/auth'
import type { CheckInActivityPayload } from '../../types/activity'
import { getActivityDetailsQueryKey } from '../queries/useActivityDetailsQuery'
import { activitiesQueryKey } from '../queries/useActivitiesQuery'
import { getMyActivitiesUserQueryKey } from '../queries/useMyActivitiesQuery'

interface CheckInActivityVariables {
  activityId: string
  payload: CheckInActivityPayload
}

export function useCheckInActivityMutation() {
  const queryClient = useQueryClient()
  const { user } = useAuth()

  return useMutation({
    gcTime: 0,
    mutationFn: ({ activityId, payload }: CheckInActivityVariables) =>
      checkInActivity(activityId, payload),
    onMutate: () => ({ userId: user?.id }),
    onSuccess: async (activity, _variables, mutationContext) => {
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
    onError: (error, { activityId }, mutationContext) => {
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        void queryClient.invalidateQueries({
          queryKey: getActivityDetailsQueryKey(
            activityId,
            mutationContext?.userId,
          ),
          exact: true,
        })
      }
    },
  })
}
