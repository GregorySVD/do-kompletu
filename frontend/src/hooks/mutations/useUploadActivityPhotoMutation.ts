import { useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadActivityPhoto } from '../../api/activitiesApi'
import { useAuth } from '../../context/auth'
import { getActivityPhotosQueryKey } from '../queries/useActivityPhotosQuery'

interface UploadActivityPhotoVariables {
  activityId: string
  file: File
}

export function useUploadActivityPhotoMutation() {
  const queryClient = useQueryClient()
  const { user } = useAuth()

  return useMutation({
    gcTime: 0,
    mutationFn: ({ activityId, file }: UploadActivityPhotoVariables) =>
      uploadActivityPhoto(activityId, file),
    onMutate: () => ({ userId: user?.id }),
    onSuccess: async (_photo, { activityId }, mutationContext) => {
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
