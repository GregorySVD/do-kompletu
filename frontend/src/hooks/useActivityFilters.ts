import { useState } from 'react'
import type { Activity, ActivityDetails } from '../types/activity'

export type PriceFilter = 'ALL' | 'FREE' | 'PAID'

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

export function useActivityFilters<T extends ActivityWithOptionalTags>({
  activities,
  searchQuery,
  onSearchChange,
}: UseActivityFiltersOptions<T>) {
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    null,
  )
  const [priceFilter, setPriceFilter] = useState<PriceFilter>('ALL')
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
    const hasAvailableSlots =
      activity.max_participants === null ||
      (activity.available_slots !== null && activity.available_slots > 0)

    return (
      matchesSearch &&
      matchesCategory &&
      matchesPrice &&
      (!availabilityOnly || hasAvailableSlots)
    )
  })
  const hasActiveFilters =
    searchQuery.trim() !== '' ||
    selectedCategoryId !== null ||
    priceFilter !== 'ALL' ||
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
    setAvailabilityOnly(false)
  }

  return {
    selectedCategoryId,
    priceFilter,
    availabilityOnly,
    filteredActivities,
    hasActiveFilters,
    toggleCategory,
    setPriceFilter,
    setAvailabilityOnly,
    clearFilters,
  }
}
