import dayjs, { type Dayjs } from 'dayjs'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import { useState } from 'react'
import type { Activity, ActivityDetails } from '../types/activity'

export type PriceFilter = 'ALL' | 'FREE' | 'PAID'
export type TimeFilter =
  'ALL' | 'TODAY' | 'TOMORROW' | 'NEXT_7_DAYS' | 'NEXT_30_DAYS'

dayjs.extend(utc)
dayjs.extend(timezone)

const WARSAW_TIME_ZONE = 'Europe/Warsaw'

type ActivityWithOptionalTags = Activity &
  Partial<Pick<ActivityDetails, 'tags'>>

interface UseActivityFiltersOptions<T extends ActivityWithOptionalTags> {
  activities: T[]
  searchQuery: string
  onSearchChange: (query: string) => void
}

function normalizeSearchText(value: string) {
  return value.normalize('NFC').toLowerCase()
}

function isWithinRange(value: Dayjs, start: Dayjs, end: Dayjs) {
  return !value.isBefore(start) && !value.isAfter(end)
}

export function matchesActivityTimeFilter(
  startAt: string,
  timeFilter: TimeFilter,
  now = dayjs().tz(WARSAW_TIME_ZONE),
) {
  if (timeFilter === 'ALL') {
    return true
  }

  const activityStart = dayjs(startAt).tz(WARSAW_TIME_ZONE)
  const warsawNow = now.tz(WARSAW_TIME_ZONE)

  if (!activityStart.isValid()) {
    return false
  }

  switch (timeFilter) {
    case 'TODAY':
      return isWithinRange(activityStart, warsawNow, warsawNow.endOf('day'))
    case 'TOMORROW': {
      const tomorrow = warsawNow.add(1, 'day')
      return isWithinRange(
        activityStart,
        tomorrow.startOf('day'),
        tomorrow.endOf('day'),
      )
    }
    case 'NEXT_7_DAYS':
      return isWithinRange(activityStart, warsawNow, warsawNow.add(7, 'day'))
    case 'NEXT_30_DAYS':
      return isWithinRange(activityStart, warsawNow, warsawNow.add(30, 'day'))
  }
}

export function useActivityFilters<T extends ActivityWithOptionalTags>({
  activities,
  searchQuery,
  onSearchChange,
}: UseActivityFiltersOptions<T>) {
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    null,
  )
  const [priceFilter, setPriceFilter] = useState<PriceFilter>('ALL')
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('ALL')
  const [availabilityOnly, setAvailabilityOnly] = useState(false)
  const normalizedSearchQuery = normalizeSearchText(searchQuery.trim())
  const filteredActivities = activities.filter((activity) => {
    const searchableValues = [
      activity.title,
      activity.location_name,
      activity.category.name,
      ...(activity.tags?.map((tag) => tag.name) ?? []),
    ]
    const matchesSearch = searchableValues.some((value) =>
      normalizeSearchText(value).includes(normalizedSearchQuery),
    )
    const matchesCategory =
      selectedCategoryId === null || activity.category.id === selectedCategoryId
    const matchesPrice =
      priceFilter === 'ALL' || activity.price_type === priceFilter
    const matchesTime = matchesActivityTimeFilter(activity.start_at, timeFilter)
    const hasAvailableSlots =
      activity.max_participants === null ||
      (activity.available_slots !== null && activity.available_slots > 0)

    return (
      matchesSearch &&
      matchesCategory &&
      matchesPrice &&
      matchesTime &&
      (!availabilityOnly || hasAvailableSlots)
    )
  })
  const hasActiveFilters =
    searchQuery.trim() !== '' ||
    selectedCategoryId !== null ||
    priceFilter !== 'ALL' ||
    timeFilter !== 'ALL' ||
    availabilityOnly

  function toggleCategory(categoryId: string) {
    setSelectedCategoryId((currentId) =>
      currentId === categoryId ? null : categoryId,
    )
  }

  function clearFilters() {
    onSearchChange('')
    setSelectedCategoryId(null)
    setPriceFilter('ALL')
    setTimeFilter('ALL')
    setAvailabilityOnly(false)
  }

  return {
    selectedCategoryId,
    priceFilter,
    timeFilter,
    availabilityOnly,
    filteredActivities,
    hasActiveFilters,
    toggleCategory,
    setPriceFilter,
    setTimeFilter,
    setAvailabilityOnly,
    clearFilters,
  }
}
