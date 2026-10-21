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
    onError: (error, { activityId }) => {
      if (
        axios.isAxiosError(error) &&
        (error.response?.status === 403 || error.response?.status === 409)
      ) {
        void queryClient.invalidateQueries({
          queryKey: getActivityDetailsQueryKey(activityId),
        })
      }
    },
  })
}
