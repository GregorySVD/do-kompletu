import {
  FilterList,
  List as ListIcon,
  Map as MapIcon,
  MapOutlined,
} from '@mui/icons-material'
import {
  Button,
  Chip,
  Drawer,
  FormControlLabel,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useMediaQuery,
} from '@mui/material'
import { useEffect, useRef, useState } from 'react'
import ActivityCard from '../../components/ActivityCard/ActivityCard'
import ActivityMap from '../../components/ActivityMap/ActivityMap'
import { mockActivities } from '../../data/mockActivities'
import { mockCategories } from '../../data/mockCategories'
import './HomePage.css'

type PriceFilter = 'ALL' | 'FREE' | 'PAID'
type ViewMode = 'list' | 'map'

interface HomePageProps {
  mode: 'light' | 'dark'
  searchQuery: string
  onSearchChange: (query: string) => void
}

interface ActivityFiltersProps {
  titleId: string
  selectedCategoryId: string | null
  priceFilter: PriceFilter
  availabilityOnly: boolean
  hasActiveFilters: boolean
  onToggleCategory: (categoryId: string) => void
  onPriceFilterChange: (value: PriceFilter) => void
  onAvailabilityChange: (value: boolean) => void
  onClearFilters: () => void
}

function normalizeSearchText(value: string) {
  return value.normalize('NFC').toLowerCase()
}

function ActivityFilters({
  titleId,
  selectedCategoryId,
  priceFilter,
  availabilityOnly,
  hasActiveFilters,
  onToggleCategory,
  onPriceFilterChange,
  onAvailabilityChange,
  onClearFilters,
}: ActivityFiltersProps) {
  return (
    <>
      <div className="filters__heading">
        <Typography id={titleId} component="h2" variant="h6">
          Filtry
        </Typography>

        <Button
          disabled={!hasActiveFilters}
          size="small"
          onClick={onClearFilters}
        >
          Wyczyść filtry
        </Button>
      </div>

      <div className="filters__group">
        <Typography component="h3" variant="subtitle1">
          Kategorie
        </Typography>

        <div className="categories__list">
          {mockCategories.map((category) => {
            const isSelected = selectedCategoryId === category.id

            return (
              <Chip
                key={category.id}
                label={category.name}
                color={isSelected ? 'primary' : 'default'}
                size="small"
                variant={isSelected ? 'filled' : 'outlined'}
                onClick={() => onToggleCategory(category.id)}
              />
            )
          })}
        </div>
      </div>

      <div className="filters__controls">
        <div className="filters__group">
          <Typography component="h3" variant="subtitle1">
            Cena
          </Typography>

          <ToggleButtonGroup
            aria-label="Rodzaj ceny"
            exclusive
            size="small"
            value={priceFilter}
            onChange={(_, value: PriceFilter | null) => {
              if (value !== null) {
                onPriceFilterChange(value)
              }
            }}
          >
            <ToggleButton value="ALL">Wszystkie</ToggleButton>
            <ToggleButton value="FREE">Bezpłatne</ToggleButton>
            <ToggleButton value="PAID">Płatne</ToggleButton>
          </ToggleButtonGroup>
        </div>

        <FormControlLabel
          className="filters__availability"
          control={
            <Switch
              checked={availabilityOnly}
              onChange={(event) => onAvailabilityChange(event.target.checked)}
            />
          }
          label="Tylko aktywności z dostępnymi miejscami"
        />
      </div>
    </>
  )
}

function HomePage({ mode, searchQuery, onSearchChange }: HomePageProps) {
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    null,
  )
  const [priceFilter, setPriceFilter] = useState<PriceFilter>('ALL')
  const [availabilityOnly, setAvailabilityOnly] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('list')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [isDesktopMapVisible, setIsDesktopMapVisible] = useState(true)
  const activitiesListRef = useRef<HTMLDivElement>(null)
  const isDesktopLayout = useMediaQuery('(min-width: 64rem)')

  useEffect(() => {
    if (!isDesktopLayout) {
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
  }, [isDesktopLayout])

  const normalizedSearchQuery = normalizeSearchText(searchQuery.trim())
  const filteredActivities = mockActivities.filter((activity) => {
    const searchableValues = [
      activity.title,
      activity.location_name,
      activity.category.name,
      ...activity.tags.map((tag) => tag.name),
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
  const isMapVisible = isDesktopLayout
    ? isDesktopMapVisible
    : viewMode === 'map'
  const shouldRenderMap = !isDesktopLayout || isDesktopMapVisible
  const filterProps = {
    selectedCategoryId,
    priceFilter,
    availabilityOnly,
    hasActiveFilters,
    onToggleCategory: toggleCategory,
    onPriceFilterChange: setPriceFilter,
    onAvailabilityChange: setAvailabilityOnly,
    onClearFilters: clearFilters,
  }

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

  return (
    <main className="home-page">
      <div className="home-page__mobile-tools">
        <ToggleButtonGroup
          className="home-view-toggle"
          aria-label="Widok strony głównej"
          exclusive
          size="small"
          value={viewMode}
          onChange={(_, value: ViewMode | null) => {
            if (value !== null) {
              setViewMode(value)
            }
          }}
        >
          <ToggleButton value="list">
            <ListIcon aria-hidden="true" fontSize="small" />
            Lista
          </ToggleButton>
          <ToggleButton value="map">
            <MapIcon aria-hidden="true" fontSize="small" />
            Mapa
          </ToggleButton>
        </ToggleButtonGroup>

        <Button
          className="home-page__filters-button"
          aria-haspopup="dialog"
          startIcon={<FilterList />}
          variant="outlined"
          onClick={() => setFiltersOpen(true)}
        >
          Filtry
        </Button>
      </div>

      <div
        className={`home-workspace${isDesktopMapVisible ? '' : ' home-workspace--map-hidden'}`}
      >
        <section
          className={`activities${viewMode === 'map' ? ' activities--mobile-hidden' : ''}`}
          aria-labelledby="activities-title"
        >
          <div className="activities__heading">
            <div>
              <Typography id="activities-title" component="h1" variant="h5">
                Aktywności w Twojej okolicy
              </Typography>
              <Typography color="text.secondary">
                Znajdź aktywność i dołącz do innych
              </Typography>
            </div>

            <Typography className="activities__count" color="text.secondary">
              {filteredActivities.length} aktywności
            </Typography>
          </div>

          <section
            className="filters filters--desktop"
            aria-labelledby="desktop-filters-title"
          >
            <ActivityFilters titleId="desktop-filters-title" {...filterProps} />
          </section>

          <div ref={activitiesListRef} className="activities__scroll">
            <div className="activities__list">
              {filteredActivities.length > 0 ? (
                filteredActivities.map((activity) => (
                  <ActivityCard key={activity.id} activity={activity} />
                ))
              ) : (
                <div className="activities__empty">
                  <Typography component="h2" variant="h6">
                    Nie znaleziono aktywności
                  </Typography>
                  <Typography color="text.secondary">
                    Spróbuj zmienić wyszukiwaną frazę lub wybrane filtry.
                  </Typography>
                  <Button variant="outlined" onClick={clearFilters}>
                    Wyczyść filtry
                  </Button>
                </div>
              )}
            </div>
          </div>
        </section>

        {shouldRenderMap && (
          <div
            className={`home-map-panel${viewMode === 'list' ? ' home-map-panel--mobile-hidden' : ''}`}
          >
            <ActivityMap
              activities={filteredActivities}
              isVisible={isMapVisible}
              mode={mode}
            />
          </div>
        )}
      </div>

      <Button
        className="home-page__map-toggle"
        startIcon={<MapOutlined />}
        variant="contained"
        onClick={() => setIsDesktopMapVisible((isVisible) => !isVisible)}
      >
        {isDesktopMapVisible ? 'Ukryj mapę' : 'Pokaż mapę'}
      </Button>

      <Drawer
        anchor="bottom"
        open={filtersOpen}
        slotProps={{
          paper: {
            'aria-labelledby': 'mobile-filters-title',
            'aria-modal': true,
            className: 'filters-drawer__paper',
            role: 'dialog',
          },
        }}
        onClose={() => setFiltersOpen(false)}
      >
        <div className="filters-drawer__handle" aria-hidden="true" />
        <div className="filters-drawer__content">
          <ActivityFilters titleId="mobile-filters-title" {...filterProps} />
        </div>
        <div className="filters-drawer__actions">
          <Button
            fullWidth
            size="large"
            variant="contained"
            onClick={() => setFiltersOpen(false)}
          >
            Pokaż wyniki
          </Button>
        </div>
      </Drawer>
    </main>
  )
}

export default HomePage
