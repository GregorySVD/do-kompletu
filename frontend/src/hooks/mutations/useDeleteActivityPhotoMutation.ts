import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteActivityPhoto } from '../../api/activitiesApi'
import { useAuth } from '../../context/auth'
import { getActivityPhotosQueryKey } from '../queries/useActivityPhotosQuery'

interface DeleteActivityPhotoVariables {
  activityId: string
  photoId: string
}

export function useDeleteActivityPhotoMutation() {
  const queryClient = useQueryClient()
  const { user } = useAuth()

  return useMutation({
    mutationFn: ({ activityId, photoId }: DeleteActivityPhotoVariables) =>
      deleteActivityPhoto(activityId, photoId),
    onMutate: () => ({ userId: user?.id }),
    onSuccess: async (_result, { activityId }, mutationContext) => {
      const userId = mutationContext?.userId

      if (!userId) {
        return
      }

      await queryClient.invalidateQueries({
        queryKey: getActivityPhotosQueryKey(activityId, userId),
        exact: true,
      })
    },
  })
}
