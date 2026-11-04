import { useMutation, useQueryClient } from '@tanstack/react-query'
import { setAdminUserActive } from '../../api/adminApi'
import { useAuth } from '../../context/auth'
import { getAdminUsersBaseQueryKey } from '../queries/adminQueryKeys'

interface SetAdminUserActiveVariables {
  userId: string
  isActive: boolean
}

export function useSetAdminUserActiveMutation() {
  const queryClient = useQueryClient()
  const { refreshUser, user } = useAuth()

  return useMutation({
    mutationFn: ({ userId, isActive }: SetAdminUserActiveVariables) =>
      setAdminUserActive(userId, { is_active: isActive }),
    onMutate: () => ({ adminId: user?.id }),
    onSuccess: async (updatedUser, _variables, mutationContext) => {
      const adminId = mutationContext?.adminId

      if (!adminId) {
        return
      }

      const refreshCurrentUser = updatedUser.id === adminId

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: getAdminUsersBaseQueryKey(adminId),
        }),
        refreshCurrentUser ? refreshUser() : Promise.resolve(),
      ])
    },
  })
}
