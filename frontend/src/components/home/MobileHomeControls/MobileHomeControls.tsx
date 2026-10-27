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
        className={`home-view-toggle home-view-toggle--${viewMode}`}
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
          <img
            className="home-view-toggle__icon"
            src="/icons/icons8-list-64.png"
            alt=""
            width="64"
            height="64"
          />
          Lista
        </ToggleButton>
        <ToggleButton value="map">
          <img
            className="home-view-toggle__icon"
            src="/icons/icons8-map-64.png"
            alt=""
            width="64"
            height="64"
          />
          Mapa
        </ToggleButton>
      </ToggleButtonGroup>

      {showFiltersButton && (
        <Button
          className="home-page__filters-button"
          aria-haspopup="dialog"
          startIcon={
            <img
              className="home-page__filters-icon"
              src="/icons/icons8-filter-64.png"
              alt=""
              width="64"
              height="64"
            />
          }
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
