import {
  FilterList,
  List as ListIcon,
  Map as MapIcon,
} from '@mui/icons-material'
import { Button, ToggleButton, ToggleButtonGroup } from '@mui/material'
import './MobileHomeControls.css'

export type ViewMode = 'list' | 'map'

interface MobileHomeControlsProps {
  viewMode: ViewMode
  showFiltersButton?: boolean
  onViewModeChange: (value: ViewMode) => void
  onOpenFilters: () => void
}

function MobileHomeControls({
  viewMode,
  showFiltersButton = true,
  onViewModeChange,
  onOpenFilters,
}: MobileHomeControlsProps) {
  return (
    <div className="home-page__mobile-tools">
      <ToggleButtonGroup
        className="home-view-toggle"
        aria-label="Widok strony głównej"
        exclusive
        size="small"
        value={viewMode}
        onChange={(_, value: ViewMode | null) => {
          if (value !== null) {
            onViewModeChange(value)
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

      {showFiltersButton && (
        <Button
          className="home-page__filters-button"
          aria-haspopup="dialog"
          startIcon={<FilterList />}
          variant="outlined"
          onClick={onOpenFilters}
        >
          Filtry
        </Button>
      )}
    </div>
  )
}

export default MobileHomeControls
