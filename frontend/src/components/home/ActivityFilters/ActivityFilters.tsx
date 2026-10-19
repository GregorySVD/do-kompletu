import {
  Button,
  FormControlLabel,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import type { PriceFilter, TimeFilter } from '../../../hooks/useActivityFilters'
import ActivityCategoryBar, {
  type ActivityCategoryBarProps,
} from '../ActivityCategoryBar/ActivityCategoryBar'
import './ActivityFilters.css'

export type ActivityCategoryFilterProps = Omit<
  ActivityCategoryBarProps,
  'variant'
>

export interface ActivityFiltersProps {
  titleId: string
  categoryFilterProps?: ActivityCategoryFilterProps
  priceFilter: PriceFilter
  timeFilter: TimeFilter
  availabilityOnly: boolean
  hasActiveFilters: boolean
  onPriceFilterChange: (value: PriceFilter) => void
  onTimeFilterChange: (value: TimeFilter) => void
  onAvailabilityChange: (value: boolean) => void
  onClearFilters: () => void
}

export type ActivityFilterProps = Omit<ActivityFiltersProps, 'titleId'>

function ActivityFilters({
  titleId,
  categoryFilterProps,
  priceFilter,
  timeFilter,
  availabilityOnly,
  hasActiveFilters,
  onPriceFilterChange,
  onTimeFilterChange,
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

      <div className="filters__controls">
        {categoryFilterProps && (
          <div className="filters__group">
            <Typography component="h3" variant="subtitle1">
              Kategorie
            </Typography>

            <ActivityCategoryBar variant="compact" {...categoryFilterProps} />
          </div>
        )}

        <div className="filters__group">
          <Typography component="h3" variant="subtitle1">
            Cena
          </Typography>

          <ToggleButtonGroup
            className="filters__options"
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

        <div className="filters__group">
          <Typography component="h3" variant="subtitle1">
            Termin
          </Typography>

          <ToggleButtonGroup
            className="filters__options"
            aria-label="Termin aktywności"
            exclusive
            size="small"
            value={timeFilter}
            onChange={(_, value: TimeFilter | null) => {
              if (value !== null) {
                onTimeFilterChange(value)
              }
            }}
          >
            <ToggleButton value="ALL">Wszystkie terminy</ToggleButton>
            <ToggleButton value="TODAY">Dzisiaj</ToggleButton>
            <ToggleButton value="TOMORROW">Jutro</ToggleButton>
            <ToggleButton value="NEXT_7_DAYS">Najbliższe 7 dni</ToggleButton>
            <ToggleButton value="NEXT_30_DAYS">Najbliższe 30 dni</ToggleButton>
          </ToggleButtonGroup>
        </div>

        <div className="filters__group">
          <Typography component="h3" variant="subtitle1">
            Dostępność
          </Typography>

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
      </div>
    </>
  )
}

export default ActivityFilters
