import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { updateActivity } from '../../api/activitiesApi'
import { useAuth } from '../../context/auth'
import type { UpdateActivityPayload } from '../../types/activity'
import { getActivityDetailsQueryKey } from '../queries/useActivityDetailsQuery'
import { activitiesQueryKey } from '../queries/useActivitiesQuery'
import { getMyActivitiesUserQueryKey } from '../queries/useMyActivitiesQuery'

interface UpdateActivityVariables {
  activityId: string
  payload: UpdateActivityPayload
}

export function useUpdateActivityMutation() {
  const queryClient = useQueryClient()
  const { user } = useAuth()

  return useMutation({
    mutationFn: ({ activityId, payload }: UpdateActivityVariables) =>
      updateActivity(activityId, payload),
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
      if (
        axios.isAxiosError(error) &&
        (error.response?.status === 403 || error.response?.status === 409)
      ) {
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
