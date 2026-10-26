import {
  Alert,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Typography,
  useTheme,
} from '@mui/material'
import { Icon } from 'leaflet'
import { useEffect, useMemo, useState, type KeyboardEvent } from 'react'
import {
  Circle,
  CircleMarker,
  MapContainer,
  Marker,
  Pane,
  Popup,
  TileLayer,
  useMap,
} from 'react-leaflet'
import { useCurrentPosition } from '../../../../hooks/useCurrentPosition'
import type { ActivityDetails } from '../../../../types/activity'
import { getMapTileConfig } from '../../../../utils/mapConfig'
import 'leaflet/dist/leaflet.css'
import './ActivityLocationCard.css'

interface ActivityLocationCardProps {
  activity: ActivityDetails
}

interface UserMapLocation {
  accuracyM: number
  latitude: number
  longitude: number
}

const activityLocationMarkerIcon = new Icon({
  iconUrl: '/icons/icons8-place-64.png',
  iconSize: [48, 48],
  iconAnchor: [24, 45],
  popupAnchor: [0, -42],
  className: 'activity-location-card__marker',
})

interface InteractiveMapControllerProps {
  activityPosition: [number, number]
  userLocation: UserMapLocation | null
}

function InteractiveMapController({
  activityPosition,
  userLocation,
}: InteractiveMapControllerProps) {
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

  useEffect(() => {
    if (userLocation === null) {
      map.setView(activityPosition, 16)
      return
    }

    map.fitBounds(
      [activityPosition, [userLocation.latitude, userLocation.longitude]],
      {
        maxZoom: 16,
        padding: [48, 48],
      },
    )
  }, [activityPosition, map, userLocation])

  return null
}

function UserLocationLayer({ location }: { location: UserMapLocation }) {
  const position: [number, number] = [location.latitude, location.longitude]

  return (
    <>
      <Circle
        center={position}
        className="activity-location-card__user-accuracy"
        interactive={false}
        radius={location.accuracyM}
      />
      <Pane name="activity-location-user-marker" style={{ zIndex: 650 }}>
        <CircleMarker
          center={position}
          className="activity-location-card__user-marker"
          radius={9}
        >
          <Popup>
            <strong>Twoja lokalizacja</strong>
            <span>Dokładność: około {Math.round(location.accuracyM)} m</span>
          </Popup>
        </CircleMarker>
      </Pane>
    </>
  )
}

function ActivityLocationCard({ activity }: ActivityLocationCardProps) {
  const [isMapOpen, setIsMapOpen] = useState(false)
  const [userLocation, setUserLocation] = useState<UserMapLocation | null>(null)
  const { errorMessage, getCurrentPosition, isLocating, resetError } =
    useCurrentPosition()
  const theme = useTheme()
  const mode = theme.palette.mode === 'dark' ? 'dark' : 'light'
  const tileConfig = getMapTileConfig(mode)
  const position = useMemo<[number, number]>(
    () => [activity.latitude, activity.longitude],
    [activity.latitude, activity.longitude],
  )
  const mapDialogTitleId = `activity-location-map-title-${activity.id}`

  const openMap = () => {
    resetError()
    setIsMapOpen(true)
  }

  const closeMap = () => {
    setIsMapOpen(false)
    setUserLocation(null)
    resetError()
  }

  async function updateUserLocation() {
    const currentPosition = await getCurrentPosition()

    if (currentPosition === null) {
      return
    }

    setUserLocation({
      accuracyM: currentPosition.coords.accuracy,
      latitude: currentPosition.coords.latitude,
      longitude: currentPosition.coords.longitude,
    })
  }

  function toggleUserLocation() {
    if (userLocation !== null) {
      setUserLocation(null)
      resetError()
      return
    }

    void updateUserLocation()
  }

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
            <img
              src="/icons/icons8-map-64.png"
              alt=""
              width="64"
              height="64"
              aria-hidden="true"
            />
          </span>
          <div className="activity-location-card__copy">
            <Typography
              className="activity-location-card__title"
              component="h2"
              variant="h5"
            >
              Miejsce
            </Typography>
            <Typography className="activity-location-card__name">
              {activity.location_name}
            </Typography>
            {activity.address && (
              <Typography
                className="activity-location-card__address"
                color="text.secondary"
              >
                {activity.address}
              </Typography>
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
                icon={activityLocationMarkerIcon}
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
            <img
              className="activity-location-card__map-open-icon"
              src="/icons/icons8-enlarge-64.png"
              alt=""
              width="64"
              height="64"
              aria-hidden="true"
            />
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
        className="activity-location-card__dialog"
        slotProps={{
          backdrop: {
            className: 'activity-location-card__dialog-backdrop',
          },
          paper: {
            className: 'activity-location-card__dialog-paper',
          },
        }}
      >
        <DialogTitle
          id={mapDialogTitleId}
          className="activity-location-card__dialog-title"
        >
          <span className="activity-location-card__dialog-heading">
            <img
              className="activity-location-card__dialog-icon"
              src="/icons/icons8-map-64.png"
              alt=""
              width="64"
              height="64"
              aria-hidden="true"
            />
            <span className="activity-location-card__dialog-title-copy">
              <span className="activity-location-card__dialog-title-text">
                Mapa aktywności
              </span>
              <Typography
                className="activity-location-card__dialog-location"
                component="span"
                color="text.secondary"
              >
                {activity.location_name}
              </Typography>
            </span>
          </span>
          <IconButton
            className="activity-location-card__dialog-close"
            aria-label="Zamknij mapę"
            edge="end"
            onClick={closeMap}
          >
            <span aria-hidden="true">×</span>
          </IconButton>
        </DialogTitle>
        <DialogContent
          dividers
          className="activity-location-card__dialog-content"
        >
          <div className="activity-location-card__location-control">
            <Button
              className="activity-location-card__location-button"
              disabled={isLocating}
              variant={userLocation === null ? 'contained' : 'outlined'}
              onClick={toggleUserLocation}
              startIcon={
                <img
                  className="activity-location-card__location-button-icon"
                  src="/icons/icons8-navigation-64.png"
                  alt=""
                  width="64"
                  height="64"
                  aria-hidden="true"
                />
              }
            >
              {isLocating
                ? 'Pobieranie lokalizacji...'
                : userLocation === null
                  ? 'Pokaż moją lokalizację'
                  : 'Ukryj moją lokalizację'}
            </Button>

            {errorMessage !== null && (
              <Alert
                className="activity-location-card__location-error"
                severity="error"
              >
                {errorMessage}
              </Alert>
            )}
          </div>

          <MapContainer
            key={`${activity.id}-${mode}-interactive`}
            center={position}
            zoom={16}
            className="activity-location-card__interactive-map"
            scrollWheelZoom
          >
            <InteractiveMapController
              activityPosition={position}
              userLocation={userLocation}
            />
            <TileLayer
              attribution={tileConfig.attribution}
              maxZoom={20}
              url={tileConfig.url}
            />
            <Marker
              alt={`Lokalizacja: ${activity.location_name}`}
              icon={activityLocationMarkerIcon}
              position={position}
              title={activity.location_name}
            >
              <Popup>
                <strong>{activity.location_name}</strong>
                {activity.address && <span>{activity.address}</span>}
              </Popup>
            </Marker>
            {userLocation !== null && (
              <UserLocationLayer location={userLocation} />
            )}
          </MapContainer>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

export default ActivityLocationCard
