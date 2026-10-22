import {
  Close,
  LocationOnOutlined,
  OpenInFullOutlined,
} from '@mui/icons-material'
import {
  Card,
  CardContent,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Typography,
  useTheme,
} from '@mui/material'
import { useEffect, useState, type KeyboardEvent } from 'react'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import type { ActivityDetails } from '../../../../types/activity'
import { getMapTileConfig, mapMarkerIcon } from '../../../../utils/mapConfig'
import 'leaflet/dist/leaflet.css'
import './ActivityLocationCard.css'

interface ActivityLocationCardProps {
  activity: ActivityDetails
}

function InteractiveMapSizeHandler() {
  const map = useMap()

  useEffect(() => {
    let secondFrameId = 0
    const firstFrameId = window.requestAnimationFrame(() => {
      map.invalidateSize()
      secondFrameId = window.requestAnimationFrame(() => map.invalidateSize())
    })

    return () => {
      window.cancelAnimationFrame(firstFrameId)
      window.cancelAnimationFrame(secondFrameId)
    }
  }, [map])

  return null
}

function ActivityLocationCard({ activity }: ActivityLocationCardProps) {
  const [isMapOpen, setIsMapOpen] = useState(false)
  const theme = useTheme()
  const mode = theme.palette.mode === 'dark' ? 'dark' : 'light'
  const tileConfig = getMapTileConfig(mode)
  const position: [number, number] = [activity.latitude, activity.longitude]
  const mapDialogTitleId = `activity-location-map-title-${activity.id}`

  const openMap = () => setIsMapOpen(true)
  const closeMap = () => setIsMapOpen(false)

  const handleMapPreviewKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openMap()
    }
  }

  return (
    <Card
      component="section"
      variant="outlined"
      className="activity-location-card"
    >
      <CardContent className="activity-location-card__content">
        <div className="activity-location-card__details">
          <span className="activity-location-card__icon">
            <LocationOnOutlined aria-hidden="true" />
          </span>
          <div>
            <Typography component="h2" variant="h6">
              Miejsce
            </Typography>
            <Typography className="activity-location-card__name">
              {activity.location_name}
            </Typography>
            {activity.address && (
              <Typography color="text.secondary">{activity.address}</Typography>
            )}
          </div>
        </div>

        <div
          className="activity-location-card__map-preview"
          role="button"
          tabIndex={0}
          aria-label={`Otwórz interaktywną mapę lokalizacji: ${activity.location_name}`}
          onClick={openMap}
          onKeyDown={handleMapPreviewKeyDown}
        >
          <div className="activity-location-card__map-frame" aria-hidden="true">
            <MapContainer
              key={activity.id}
              center={position}
              zoom={14}
              className="activity-location-card__map"
              attributionControl={false}
              boxZoom={false}
              doubleClickZoom={false}
              dragging={false}
              keyboard={false}
              scrollWheelZoom={false}
              touchZoom={false}
              zoomControl={false}
            >
              <TileLayer
                key={mode}
                attribution={tileConfig.attribution}
                maxZoom={20}
                url={tileConfig.url}
              />
              <Marker
                alt={`Lokalizacja: ${activity.location_name}`}
                icon={mapMarkerIcon}
                interactive={false}
                position={position}
                title={activity.location_name}
              />
            </MapContainer>
          </div>
          <span
            className="activity-location-card__map-attribution"
            aria-hidden="true"
          >
            © OpenStreetMap
          </span>
          <span className="activity-location-card__map-open-hint">
            <OpenInFullOutlined aria-hidden="true" fontSize="small" />
            Otwórz mapę
          </span>
        </div>
      </CardContent>

      <Dialog
        open={isMapOpen}
        onClose={closeMap}
        fullWidth
        maxWidth="md"
        aria-labelledby={mapDialogTitleId}
      >
        <DialogTitle
          id={mapDialogTitleId}
          className="activity-location-card__dialog-title"
        >
          <span>
            Lokalizacja wydarzenia
            <Typography component="span" color="text.secondary">
              {activity.location_name}
            </Typography>
          </span>
          <IconButton aria-label="Zamknij mapę" edge="end" onClick={closeMap}>
            <Close />
          </IconButton>
        </DialogTitle>
        <DialogContent
          dividers
          className="activity-location-card__dialog-content"
        >
          <MapContainer
            key={`${activity.id}-${mode}-interactive`}
            center={position}
            zoom={16}
            className="activity-location-card__interactive-map"
            scrollWheelZoom
          >
            <InteractiveMapSizeHandler />
            <TileLayer
              attribution={tileConfig.attribution}
              maxZoom={20}
              url={tileConfig.url}
            />
            <Marker
              alt={`Lokalizacja: ${activity.location_name}`}
              icon={mapMarkerIcon}
              position={position}
              title={activity.location_name}
            >
              <Popup>
                <strong>{activity.location_name}</strong>
                {activity.address && <span>{activity.address}</span>}
              </Popup>
            </Marker>
          </MapContainer>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

export default ActivityLocationCard
