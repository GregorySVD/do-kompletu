export type ActivityReturnPath = '/' | '/profile' | '/profile/activities'

interface ActivityNavigationState {
  activityReturnTo?: unknown
}

const allowedActivityReturnPaths: ReadonlySet<ActivityReturnPath> = new Set([
  '/',
  '/profile',
  '/profile/activities',
])

export function getActivityReturnPath(state: unknown): ActivityReturnPath {
  if (typeof state !== 'object' || state === null) {
    return '/'
  }

  const returnTo = (state as ActivityNavigationState).activityReturnTo

  return typeof returnTo === 'string' &&
    allowedActivityReturnPaths.has(returnTo as ActivityReturnPath)
    ? (returnTo as ActivityReturnPath)
    : '/'
}

export function getActivityReturnLabel(returnPath: ActivityReturnPath) {
  switch (returnPath) {
    case '/profile/activities':
      return 'Wróć do moich aktywności'
    case '/profile':
      return 'Wróć do profilu'
    default:
      return 'Wróć do aktywności'
  }
}
