import { DivIcon } from 'leaflet'
import { useEffect } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
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
import { Link } from 'react-router-dom'
import {
  getActivityCategoryPresentation,
  type ActivityCategoryVisualVariant,
} from '../../config/activityCategoryPresentation'
import type { Activity } from '../../types/activity'
import { getMapTileConfig, poznanMapCenter } from '../../utils/mapConfig'
import 'leaflet/dist/leaflet.css'
import './ActivityMap.css'

interface ActivityMapProps {
  activities: Activity[]
  mode: 'light' | 'dark'
  isVisible?: boolean
  userLocation?: UserMapLocation | null
}

export interface UserMapLocation {
  latitude: number
  longitude: number
  accuracyM: number
}

const dateFormatter = new Intl.DateTimeFormat('pl-PL', {
  dateStyle: 'medium',
  timeStyle: 'short',
  hour12: false,
})

const categoryMarkerIconCache = new Map<
  ActivityCategoryVisualVariant,
  DivIcon
>()

function getActivityCategoryMarkerIcon(categorySlug: string) {
  const presentation = getActivityCategoryPresentation(categorySlug)
  const cachedIcon = categoryMarkerIconCache.get(presentation.variant)

  if (cachedIcon) {
    return cachedIcon
  }

  const CategoryIcon = presentation.icon
  const markerIcon = new DivIcon({
    className: `activity-map__category-marker activity-map__category-marker--${presentation.variant}`,
    html: renderToStaticMarkup(
      <span className="activity-map__category-marker-visual" aria-hidden="true">
        {presentation.pixelIconSrc ? (
          <img
            className="activity-map__category-marker-pixel-icon"
            src={presentation.pixelIconSrc}
            alt=""
            width="32"
            height="32"
          />
        ) : (
          <CategoryIcon className="activity-map__category-marker-icon" />
        )}
      </span>,
    ),
    iconSize: [46, 46],
    iconAnchor: [23, 23],
    popupAnchor: [0, -27],
  })

  categoryMarkerIconCache.set(presentation.variant, markerIcon)

  return markerIcon
}

function MapResizeHandler({ isVisible }: { isVisible: boolean }) {
  const map = useMap()

  useEffect(() => {
    if (!isVisible) {
      return
    }

    let secondFrameId = 0
    const firstFrameId = window.requestAnimationFrame(() => {
      map.invalidateSize()
      secondFrameId = window.requestAnimationFrame(() => map.invalidateSize())
    })

    return () => {
      window.cancelAnimationFrame(firstFrameId)
      window.cancelAnimationFrame(secondFrameId)
    }
  }, [isVisible, map])

  return null
}

function UserLocationLayer({ location }: { location: UserMapLocation }) {
  const map = useMap()
  const position: [number, number] = [location.latitude, location.longitude]

  useEffect(() => {
    map.flyTo([location.latitude, location.longitude], 15)
  }, [location, map])

  return (
    <>
      <Circle
        center={position}
        className="activity-map__user-accuracy"
        interactive={false}
        radius={location.accuracyM}
      />
      <Pane
        className="activity-map__user-marker-pane"
        name="user-location-marker"
      >
        <CircleMarker
          center={position}
          className="activity-map__user-marker"
          radius={9}
        >
          <Popup className="activity-map__user-popup-container">
            <div className="activity-map__user-popup">
              <strong>Twoja lokalizacja</strong>
              <span>Dokładność: około {Math.round(location.accuracyM)} m</span>
            </div>
          </Popup>
        </CircleMarker>
      </Pane>
    </>
  )
}

function ActivityMap({
  activities,
  mode,
  isVisible = true,
  userLocation = null,
}: ActivityMapProps) {
  const tileConfig = getMapTileConfig(mode)

  return (
    <aside className="activity-map" aria-label="Mapa aktywności">
      <MapContainer
        center={poznanMapCenter}
        zoom={12}
        className="activity-map__map"
        scrollWheelZoom
      >
        <MapResizeHandler isVisible={isVisible} />
        <TileLayer
          attribution={tileConfig.attribution}
          maxZoom={20}
          url={tileConfig.url}
        />

        {userLocation !== null && <UserLocationLayer location={userLocation} />}

        {activities.map((activity) => {
          const missingToMinimum = Math.max(
            activity.min_participants - activity.participant_count,
            0,
          )
          const hasParticipantLimit = activity.max_participants !== null
          const markerLabel = `${activity.title} — ${activity.category.name}`

          return (
            <Marker
              key={activity.id}
              alt={markerLabel}
              position={[activity.latitude, activity.longitude]}
              icon={getActivityCategoryMarkerIcon(activity.category.slug)}
              title={markerLabel}
            >
              <Popup>
                <div className="activity-map__popup">
                  <h2>{activity.title}</h2>
                  <p>{activity.category.name}</p>
                  <p>{activity.location_name}</p>
                  <p>{dateFormatter.format(new Date(activity.start_at))}</p>
                  <p>
                    {hasParticipantLimit
                      ? `${activity.participant_count} / ${activity.max_participants} uczestników`
                      : `${activity.participant_count} uczestników`}
                  </p>
                  <p>
                    {missingToMinimum > 0
                      ? `Brakuje ${missingToMinimum} osób do kompletu`
                      : 'Komplet zebrany'}
                  </p>
                  <p>
                    {hasParticipantLimit
                      ? activity.available_slots !== null &&
                        activity.available_slots > 0
                        ? `${activity.available_slots} wolnych miejsc`
                        : 'Brak wolnych miejsc'
                      : 'Bez limitu miejsc'}
                  </p>
                  <Link
                    className="activity-map__details-link"
                    to={`/activities/${activity.id}`}
                  >
                    Zobacz szczegóły
                  </Link>
                </div>
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>
    </aside>
  )
}

export default ActivityMap
