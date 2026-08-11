import { useState } from 'react'
import {
  Button,
  Chip,
  FormControlLabel,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import ActivityCard from '../../components/ActivityCard/ActivityCard'
import ActivityMap from '../../components/ActivityMap/ActivityMap'
import { mockActivities } from '../../data/mockActivities'
import { mockCategories } from '../../data/mockCategories'
import './HomePage.css'

type PriceFilter = 'ALL' | 'FREE' | 'PAID'

interface HomePageProps {
  mode: 'light' | 'dark'
  searchQuery: string
  onSearchChange: (query: string) => void
}

function normalizeSearchText(value: string) {
  return value.normalize('NFC').toLowerCase()
}

function HomePage({ mode, searchQuery, onSearchChange }: HomePageProps) {
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    null,
  )
  const [priceFilter, setPriceFilter] = useState<PriceFilter>('ALL')
  const [availabilityOnly, setAvailabilityOnly] = useState(false)

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
      <section className="filters" aria-labelledby="filters-title">
        <div className="filters__heading">
          <Typography id="filters-title" component="h2" variant="h6">
            Filtry
          </Typography>

          {hasActiveFilters && (
            <Button size="small" onClick={clearFilters}>
              Wyczyść filtry
            </Button>
          )}
        </div>

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
                variant={isSelected ? 'filled' : 'outlined'}
                onClick={() => toggleCategory(category.id)}
              />
            )
          })}
        </div>

        <div className="filters__controls">
          <ToggleButtonGroup
            aria-label="Rodzaj ceny"
            exclusive
            size="small"
            value={priceFilter}
            onChange={(_, value: PriceFilter | null) => {
              if (value !== null) {
                setPriceFilter(value)
              }
            }}
          >
            <ToggleButton value="ALL">Wszystkie</ToggleButton>
            <ToggleButton value="FREE">Bezpłatne</ToggleButton>
            <ToggleButton value="PAID">Płatne</ToggleButton>
          </ToggleButtonGroup>

          <FormControlLabel
            control={
              <Switch
                checked={availabilityOnly}
                onChange={(event) => setAvailabilityOnly(event.target.checked)}
              />
            }
            label="Tylko aktywności z dostępnymi miejscami"
          />
        </div>
      </section>

      <div className="home-layout">
        <section className="activities" aria-labelledby="activities-title">
          <div className="activities__heading">
            <div>
              <Typography id="activities-title" component="h1" variant="h5">
                Aktywności w Twojej okolicy
              </Typography>
              <Typography color="text.secondary">
                Znajdź aktywność i dołącz do innych
              </Typography>
            </div>

            <Typography color="text.secondary">
              {filteredActivities.length} aktywności
            </Typography>
          </div>

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
        </section>

        <ActivityMap activities={filteredActivities} mode={mode} />
      </div>
    </main>
  )
}

export default HomePage
