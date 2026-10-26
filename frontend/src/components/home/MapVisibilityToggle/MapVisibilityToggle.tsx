import { Button } from '@mui/material'
import './MapVisibilityToggle.css'

interface MapVisibilityToggleProps {
  onShow: () => void
}

function MapVisibilityToggle({ onShow }: MapVisibilityToggleProps) {
  return (
    <Button
      className="home-page__map-toggle"
      startIcon={
        <img
          className="home-page__map-toggle-icon"
          src="/icons/icons8-map-64.png"
          alt=""
          width="64"
          height="64"
        />
      }
      variant="contained"
      onClick={onShow}
    >
      Pokaż mapę
    </Button>
  )
}

export default MapVisibilityToggle
