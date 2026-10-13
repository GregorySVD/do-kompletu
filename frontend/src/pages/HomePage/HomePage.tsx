import { useMediaQuery } from '@mui/material'
import { useRef, useState } from 'react'
import ActivityListPanel from '../../components/home/ActivityListPanel/ActivityListPanel'
import HomeMapPanel from '../../components/home/HomeMapPanel/HomeMapPanel'
import MapVisibilityToggle from '../../components/home/MapVisibilityToggle/MapVisibilityToggle'
import MobileFiltersDrawer from '../../components/home/MobileFiltersDrawer/MobileFiltersDrawer'
import MobileHomeControls, {
  type ViewMode,
} from '../../components/home/MobileHomeControls/MobileHomeControls'
import { mockActivities } from '../../data/mockActivities'
import { mockCategories } from '../../data/mockCategories'
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
  const isDesktopLayout = useMediaQuery('(min-width: 64rem)')
  const {
    selectedCategoryId,
    priceFilter,
    availabilityOnly,
    filteredActivities,
    hasActiveFilters,
    toggleCategory,
    setPriceFilter,
    setAvailabilityOnly,
    clearFilters,
  } = useActivityFilters({
    activities: mockActivities,
    searchQuery,
    onSearchChange,
  })

  useActivityWheelRouting({
    activitiesListRef,
    enabled: isDesktopLayout,
  })

  const isMapVisible = isDesktopLayout
    ? isDesktopMapVisible
    : viewMode === 'map'
  const shouldRenderMap = !isDesktopLayout || isDesktopMapVisible
  const filterProps = {
    categories: mockCategories,
    selectedCategoryId,
    priceFilter,
    availabilityOnly,
    hasActiveFilters,
    onToggleCategory: toggleCategory,
    onPriceFilterChange: setPriceFilter,
    onAvailabilityChange: setAvailabilityOnly,
    onClearFilters: clearFilters,
  }

  return (
    <main className="home-page">
      <MobileHomeControls
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        onOpenFilters={() => setFiltersOpen(true)}
      />

      <div
        className={`home-workspace${isDesktopMapVisible ? '' : ' home-workspace--map-hidden'}`}
      >
        <ActivityListPanel
          activities={filteredActivities}
          filterProps={filterProps}
          isMobileHidden={viewMode === 'map'}
          scrollContainerRef={activitiesListRef}
        />

        {shouldRenderMap && (
          <HomeMapPanel
            activities={filteredActivities}
            isMobileHidden={viewMode === 'list'}
            isVisible={isMapVisible}
            mode={mode}
          />
        )}
      </div>

      <MapVisibilityToggle
        isMapVisible={isDesktopMapVisible}
        onToggle={() => setIsDesktopMapVisible((isVisible) => !isVisible)}
      />

      <MobileFiltersDrawer
        filterProps={filterProps}
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
      />
    </main>
  )
}

export default HomePage
