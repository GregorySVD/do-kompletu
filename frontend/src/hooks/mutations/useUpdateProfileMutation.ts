import { useMutation } from '@tanstack/react-query'
import { updateCurrentUser } from '../../api/authApi'
import { useAuth } from '../../context/auth'

export function useUpdateProfileMutation() {
  const { syncUserProfile } = useAuth()

  return useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: syncUserProfile,
  })
}
