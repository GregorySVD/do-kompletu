import { MapOutlined } from '@mui/icons-material'
import { Button } from '@mui/material'
import './MapVisibilityToggle.css'

interface MapVisibilityToggleProps {
  onShow: () => void
}

function MapVisibilityToggle({ onShow }: MapVisibilityToggleProps) {
  return (
    <Button
      className="home-page__map-toggle"
      startIcon={<MapOutlined />}
      variant="contained"
      onClick={onShow}
    >
      Pokaż mapę
    </Button>
  )
}

export default MapVisibilityToggle
