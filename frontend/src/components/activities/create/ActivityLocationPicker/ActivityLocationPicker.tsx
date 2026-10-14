import { useTheme } from '@mui/material'
import { MapContainer, Marker, TileLayer, useMapEvents } from 'react-leaflet'
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

function ActivityLocationPicker({
  disabled = false,
  error,
  latitude,
  longitude,
  onLocationChange,
}: ActivityLocationPickerProps) {
  const theme = useTheme()
  const mode = theme.palette.mode === 'dark' ? 'dark' : 'light'
  const tileConfig = getMapTileConfig(mode)
  const hasLocation = latitude !== null && longitude !== null

  return (
    <div className="activity-location-picker">
      <div>
        <h3 className="activity-location-picker__title">
          Wskaż dokładne miejsce na mapie
        </h3>
        <p className="activity-location-picker__hint">
          Kliknij na mapie, aby ustawić lokalizację aktywności.
        </p>
      </div>

      <div
        className={`activity-location-picker__frame${error ? ' activity-location-picker__frame--error' : ''}${disabled ? ' activity-location-picker__frame--disabled' : ''}`}
      >
        <MapContainer
          center={poznanMapCenter}
          zoom={12}
          className="activity-location-picker__map"
          scrollWheelZoom
        >
          <MapClickHandler
            disabled={disabled}
            onLocationChange={onLocationChange}
          />
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
