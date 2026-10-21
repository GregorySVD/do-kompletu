import { Close, LocationDisabled, MyLocation } from '@mui/icons-material'
import { Alert, Button, IconButton, Tooltip } from '@mui/material'
import { useState } from 'react'
import { useCurrentPosition } from '../../../hooks/useCurrentPosition'
import type { Activity } from '../../../types/activity'
import ActivityMap, {
  type UserMapLocation,
} from '../../ActivityMap/ActivityMap'
import './HomeMapPanel.css'

interface HomeMapPanelProps {
  activities: Activity[]
  mode: 'light' | 'dark'
  isVisible: boolean
  isDesktopHidden: boolean
  isMobileHidden: boolean
  onHideMap: () => void
}

function HomeMapPanel({
  activities,
  mode,
  isVisible,
  isDesktopHidden,
  isMobileHidden,
  onHideMap,
}: HomeMapPanelProps) {
  const [userLocation, setUserLocation] = useState<UserMapLocation | null>(null)
  const { errorMessage, getCurrentPosition, isLocating, resetError } =
    useCurrentPosition()

  async function updateUserLocation() {
    const position = await getCurrentPosition()

    if (position === null) {
      return
    }

    setUserLocation({
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracyM: position.coords.accuracy,
    })
  }

  function hideUserLocation() {
    setUserLocation(null)
    resetError()
  }

  return (
    <div
      className={`home-map-panel${isMobileHidden ? ' home-map-panel--mobile-hidden' : ''}${isDesktopHidden ? ' home-map-panel--desktop-hidden' : ''}`}
    >
      <Tooltip placement="right" title="Schowaj mapę">
        <IconButton
          className="home-map-panel__close"
          aria-label="Schowaj mapę"
          onClick={onHideMap}
        >
          <Close aria-hidden="true" />
        </IconButton>
      </Tooltip>

      <div className="home-map-panel__location-control">
        <div className="home-map-panel__location-actions">
          <Button
            className="home-map-panel__location-button"
            disabled={isLocating}
            startIcon={<MyLocation aria-hidden="true" />}
            variant="contained"
            onClick={() => void updateUserLocation()}
          >
            {isLocating
              ? 'Pobieranie lokalizacji...'
              : userLocation === null
                ? 'Pokaż moją lokalizację'
                : 'Odśwież lokalizację'}
          </Button>

          {userLocation !== null && (
            <Button
              className="home-map-panel__location-button"
              disabled={isLocating}
              startIcon={<LocationDisabled aria-hidden="true" />}
              variant="outlined"
              onClick={hideUserLocation}
            >
              Ukryj moją lokalizację
            </Button>
          )}
        </div>

        {errorMessage !== null && (
          <Alert className="home-map-panel__location-error" severity="error">
            {errorMessage}
          </Alert>
        )}
      </div>

      <ActivityMap
        activities={activities}
        isVisible={isVisible}
        mode={mode}
        userLocation={userLocation}
      />
    </div>
  )
}

export default HomeMapPanel
