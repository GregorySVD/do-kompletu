import { useMutation } from '@tanstack/react-query'
import { createActivity } from '../../api/activitiesApi'

export function useCreateActivityMutation() {
  return useMutation({
    mutationFn: createActivity,
  })
}
