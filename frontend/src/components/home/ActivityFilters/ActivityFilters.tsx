import {
  Button,
  Chip,
  FormControlLabel,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import type { PriceFilter } from '../../../hooks/useActivityFilters'
import type { ActivityCategory } from '../../../types/activity'
import './ActivityFilters.css'

export interface ActivityFiltersProps {
  titleId: string
  categories: ActivityCategory[]
  selectedCategoryId: string | null
  priceFilter: PriceFilter
  availabilityOnly: boolean
  hasActiveFilters: boolean
  onToggleCategory: (categoryId: string) => void
  onPriceFilterChange: (value: PriceFilter) => void
  onAvailabilityChange: (value: boolean) => void
  onClearFilters: () => void
}

export type ActivityFilterProps = Omit<ActivityFiltersProps, 'titleId'>

function ActivityFilters({
  titleId,
  categories,
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
          {categories.map((category) => {
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

export default ActivityFilters
