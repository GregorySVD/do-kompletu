import { MapOutlined } from '@mui/icons-material'
import { Button } from '@mui/material'
import './MapVisibilityToggle.css'

interface MapVisibilityToggleProps {
  isMapVisible: boolean
  onToggle: () => void
}

function MapVisibilityToggle({
  isMapVisible,
  onToggle,
}: MapVisibilityToggleProps) {
  return (
    <Button
      className={`home-page__map-toggle${
        isMapVisible ? '' : ' home-page__map-toggle--map-hidden'
      }`}
      aria-pressed={isMapVisible}
      startIcon={<MapOutlined />}
      variant="contained"
      onClick={onToggle}
    >
      {isMapVisible ? 'Ukryj mapę' : 'Pokaż mapę'}
    </Button>
  )
}

export default MapVisibilityToggle
