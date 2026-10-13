import { useEffect, type RefObject } from 'react'

interface UseActivityWheelRoutingOptions {
  activitiesListRef: RefObject<HTMLDivElement | null>
  enabled: boolean
}

export function useActivityWheelRouting({
  activitiesListRef,
  enabled,
}: UseActivityWheelRoutingOptions) {
  useEffect(() => {
    if (!enabled) {
      return
    }

    function routeWheelToActivities(event: WheelEvent) {
      if (event.ctrlKey || event.deltaY === 0 || !activitiesListRef.current) {
        return
      }

      const target = event.target as HTMLElement | null

      if (target?.closest('.activity-map')) {
        return
      }

      event.preventDefault()
      activitiesListRef.current.scrollBy({ top: event.deltaY })
    }

    window.addEventListener('wheel', routeWheelToActivities, {
      passive: false,
    })

    return () => window.removeEventListener('wheel', routeWheelToActivities)
  }, [activitiesListRef, enabled])
}
