import { useEffect } from 'react'
import { Button, useTheme } from '@mui/material'
import {
  MapContainer,
  Marker,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import { useCurrentPosition } from '../../../../hooks/useCurrentPosition'
import {
  getMapTileConfig,
  mapMarkerIcon,
  poznanMapCenter,
} from '../../../../utils/mapConfig'
import 'leaflet/dist/leaflet.css'
import './ActivityLocationPicker.css'

interface ActivityLocationPickerProps {
  disabled?: boolean
  error?: string
  latitude: number | null
  longitude: number | null
  onLocationChange: (latitude: number, longitude: number) => void
}

interface MapClickHandlerProps {
  disabled: boolean
  onLocationChange: (latitude: number, longitude: number) => void
}

function MapClickHandler({ disabled, onLocationChange }: MapClickHandlerProps) {
  useMapEvents({
    click(event) {
      if (!disabled) {
        onLocationChange(event.latlng.lat, event.latlng.lng)
      }
    },
  })

  return null
}

function SelectedLocationSync({
  latitude,
  longitude,
}: Pick<ActivityLocationPickerProps, 'latitude' | 'longitude'>) {
  const map = useMap()

  useEffect(() => {
    if (latitude !== null && longitude !== null) {
      map.setView([latitude, longitude], Math.max(map.getZoom(), 14), {
        animate: false,
      })
    }
  }, [latitude, longitude, map])

  return null
}

function ActivityLocationPicker({
  disabled = false,
  error,
  latitude,
  longitude,
  onLocationChange,
}: ActivityLocationPickerProps) {
  const theme = useTheme()
  const {
    errorMessage: geolocationError,
    getCurrentPosition,
    isLocating,
  } = useCurrentPosition()
  const mode = theme.palette.mode === 'dark' ? 'dark' : 'light'
  const tileConfig = getMapTileConfig(mode)
  const hasLocation = latitude !== null && longitude !== null
  const initialCenter: [number, number] = hasLocation
    ? [latitude, longitude]
    : poznanMapCenter

  async function handleUseDeviceLocation() {
    const position = await getCurrentPosition()

    if (position) {
      onLocationChange(position.coords.latitude, position.coords.longitude)
    }
  }

  return (
    <div className="activity-location-picker">
      <div className="activity-location-picker__heading">
        <div>
          <h3 className="activity-location-picker__title">
            Zaznacz punkt spotkania
          </h3>
          <p className="activity-location-picker__hint">
            Kliknij mapę albo użyj bieżącej lokalizacji urządzenia.
          </p>
        </div>

        <Button
          className="activity-location-picker__locate-button"
          disabled={disabled || isLocating}
          type="button"
          onClick={() => {
            void handleUseDeviceLocation()
          }}
          startIcon={
            <img
              src="/icons/icons8-navigation-64.png"
              alt=""
              width="64"
              height="64"
              aria-hidden="true"
            />
          }
        >
          {isLocating ? 'Ustalanie lokalizacji...' : 'Użyj mojej lokalizacji'}
        </Button>
      </div>

      <div
        className={`activity-location-picker__frame${error ? ' activity-location-picker__frame--error' : ''}${disabled ? ' activity-location-picker__frame--disabled' : ''}`}
      >
        <MapContainer
          center={initialCenter}
          zoom={12}
          className="activity-location-picker__map"
          scrollWheelZoom
        >
          <MapClickHandler
            disabled={disabled}
            onLocationChange={onLocationChange}
          />
          <SelectedLocationSync latitude={latitude} longitude={longitude} />
          <TileLayer
            key={mode}
            attribution={tileConfig.attribution}
            maxZoom={20}
            url={tileConfig.url}
          />
          {hasLocation && (
            <Marker icon={mapMarkerIcon} position={[latitude, longitude]} />
          )}
        </MapContainer>
      </div>

      {error && (
        <p className="activity-location-picker__error" role="alert">
          {error}
        </p>
      )}

      {geolocationError && (
        <p className="activity-location-picker__error" role="alert">
          {geolocationError}
        </p>
      )}

      {hasLocation && !error && (
        <div className="activity-location-picker__selection" role="status">
          <span>Wybrano lokalizację</span>
          <span className="activity-location-picker__coordinates">
            {latitude.toFixed(6)}, {longitude.toFixed(6)}
          </span>
        </div>
      )}
    </div>
  )
}

export default ActivityLocationPicker
