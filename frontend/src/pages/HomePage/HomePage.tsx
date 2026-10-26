import { useMediaQuery } from '@mui/material'
import { useMemo, useRef, useState } from 'react'
import ActivityCategoryBar from '../../components/home/ActivityCategoryBar/ActivityCategoryBar'
import ActivityListPanel from '../../components/home/ActivityListPanel/ActivityListPanel'
import HomeMapPanel from '../../components/home/HomeMapPanel/HomeMapPanel'
import MapVisibilityToggle from '../../components/home/MapVisibilityToggle/MapVisibilityToggle'
import MobileFiltersDrawer from '../../components/home/MobileFiltersDrawer/MobileFiltersDrawer'
import MobileHomeControls, {
  type ViewMode,
} from '../../components/home/MobileHomeControls/MobileHomeControls'
import BouncingLogo from '../../components/system/BouncingLogo/BouncingLogo'
import QueryStateMessage from '../../components/system/QueryStateMessage/QueryStateMessage'
import { useActivitiesQuery } from '../../hooks/queries/useActivitiesQuery'
import { useActivityCategoriesQuery } from '../../hooks/queries/useActivityCategoriesQuery'
import { useActivityFilters } from '../../hooks/useActivityFilters'
import { useActivityWheelRouting } from '../../hooks/useActivityWheelRouting'
import './HomePage.css'

interface HomePageProps {
  mode: 'light' | 'dark'
  searchQuery: string
  onSearchChange: (query: string) => void
}

function HomePage({ mode, searchQuery, onSearchChange }: HomePageProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('list')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [isDesktopMapVisible, setIsDesktopMapVisible] = useState(true)
  const activitiesListRef = useRef<HTMLDivElement>(null)
  const isWideDesktopLayout = useMediaQuery('(min-width: 75rem)')
  const isCompactFiltersLayout = useMediaQuery(
    '(min-width: 64rem) and (max-width: 74.99rem)',
  )
  const activitiesQuery = useActivitiesQuery()
  const categoriesQuery = useActivityCategoriesQuery()
  const {
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
  } = useActivityFilters({
    activities: activitiesQuery.data ?? [],
    searchQuery,
    onSearchChange,
  })

  useActivityWheelRouting({
    activitiesListRef,
    enabled: isWideDesktopLayout,
  })

  const isMapVisible = isWideDesktopLayout
    ? isDesktopMapVisible
    : viewMode === 'map'
  const categoryBarItems = useMemo(() => {
    const categoryCounts = new Map<string, number>()

    for (const activity of activitiesQuery.data ?? []) {
      categoryCounts.set(
        activity.category.id,
        (categoryCounts.get(activity.category.id) ?? 0) + 1,
      )
    }

    return (categoriesQuery.data ?? []).map((category) => ({
      ...category,
      count: categoryCounts.get(category.id) ?? 0,
    }))
  }, [activitiesQuery.data, categoriesQuery.data])
  const categoryFilterProps = {
    categories: categoryBarItems,
    selectedCategoryId,
    onToggleCategory: toggleCategory,
  }
  const baseFilterProps = {
    priceFilter,
    timeFilter,
    availabilityOnly,
    hasActiveFilters,
    onPriceFilterChange: setPriceFilter,
    onTimeFilterChange: setTimeFilter,
    onAvailabilityChange: setAvailabilityOnly,
    onClearFilters: clearFilters,
  }
  const listFilterProps = {
    ...baseFilterProps,
    ...(isCompactFiltersLayout && { categoryFilterProps }),
  }
  const mobileFilterProps = {
    ...baseFilterProps,
    categoryFilterProps,
  }
  const isInitialLoading =
    activitiesQuery.isPending || categoriesQuery.isPending
  const queryErrorMessage = activitiesQuery.isError
    ? 'Nie udało się pobrać aktywności.'
    : categoriesQuery.isError
      ? 'Nie udało się pobrać kategorii.'
      : null
  const queryErrorTitle = activitiesQuery.isError
    ? 'Nie możemy pobrać aktywności'
    : 'Nie możemy pobrać kategorii'
  const isRetrying = activitiesQuery.isFetching || categoriesQuery.isFetching

  function retryHomeData() {
    void Promise.all([activitiesQuery.refetch(), categoriesQuery.refetch()])
  }

  if (isInitialLoading) {
    return (
      <main className="home-page home-page--query-state">
        <QueryStateMessage message="Ładowanie aktywności..." isLoading />
      </main>
    )
  }

  if (queryErrorMessage) {
    return (
      <main className="home-page home-page--query-state">
        <BouncingLogo />
        <QueryStateMessage
          title={queryErrorTitle}
          message={queryErrorMessage}
          hint="Serwer może być chwilowo niedostępny. Spróbuj ponownie za moment."
          isRetrying={isRetrying}
          onRetry={retryHomeData}
        />
      </main>
    )
  }

  return (
    <main className="home-page">
      {isWideDesktopLayout && (
        <ActivityCategoryBar
          categories={categoryBarItems}
          selectedCategoryId={selectedCategoryId}
          onToggleCategory={toggleCategory}
        />
      )}

      <MobileHomeControls
        viewMode={viewMode}
        showFiltersButton={!isCompactFiltersLayout}
        onViewModeChange={setViewMode}
        onOpenFilters={() => setFiltersOpen(true)}
      />

      <div
        className={`home-workspace${isDesktopMapVisible ? '' : ' home-workspace--map-hidden'}`}
      >
        <ActivityListPanel
          activities={filteredActivities}
          filterProps={listFilterProps}
          isMobileHidden={viewMode === 'map'}
          scrollContainerRef={activitiesListRef}
        />

        <HomeMapPanel
          activities={filteredActivities}
          isDesktopHidden={!isDesktopMapVisible}
          isMobileHidden={viewMode === 'list'}
          isVisible={isMapVisible}
          mode={mode}
          onHideMap={() => setIsDesktopMapVisible(false)}
        />
      </div>

      {!isDesktopMapVisible && (
        <MapVisibilityToggle onShow={() => setIsDesktopMapVisible(true)} />
      )}

      {!isWideDesktopLayout && !isCompactFiltersLayout && (
        <MobileFiltersDrawer
          filterProps={mobileFilterProps}
          open={filtersOpen}
          onClose={() => setFiltersOpen(false)}
        />
      )}
    </main>
  )
}

export default HomePage
