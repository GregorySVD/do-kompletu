export const adminQueryKey = ['admin'] as const

export function getAdminIdentityQueryKey(adminId: string) {
  return [...adminQueryKey, adminId] as const
}

export function getAdminUsersBaseQueryKey(adminId: string) {
  return [...getAdminIdentityQueryKey(adminId), 'users'] as const
}

export function getAdminUsersQueryKey(
  adminId: string,
  limit: number,
  offset: number,
) {
  return [...getAdminUsersBaseQueryKey(adminId), limit, offset] as const
}

export function getAdminActivitiesBaseQueryKey(adminId: string) {
  return [...getAdminIdentityQueryKey(adminId), 'activities'] as const
}

export function getAdminActivitiesQueryKey(
  adminId: string,
  limit: number,
  offset: number,
) {
  return [...getAdminActivitiesBaseQueryKey(adminId), limit, offset] as const
}
