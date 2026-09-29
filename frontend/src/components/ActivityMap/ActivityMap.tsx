import { useEffect } from 'react'
import { Icon } from 'leaflet'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import { Link } from 'react-router-dom'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import type { Activity } from '../../types/activity'
import 'leaflet/dist/leaflet.css'
import './ActivityMap.css'

interface ActivityMapProps {
  activities: Activity[]
  mode: 'light' | 'dark'
  isVisible?: boolean
}

const poznanCenter: [number, number] = [52.4064, 16.9252]
const cartoApiKey = import.meta.env.VITE_CARTO_API_KEY?.trim()
const openStreetMapTileUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const openStreetMapAttribution =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const cartoAttribution = `${openStreetMapAttribution}, &copy; <a href="https://carto.com/attributions">CARTO</a>`
const lightTileUrl = cartoApiKey
  ? `https://basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png?key=${encodeURIComponent(cartoApiKey)}`
  : openStreetMapTileUrl
const darkTileUrl = cartoApiKey
  ? `https://basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key=${encodeURIComponent(cartoApiKey)}`
  : openStreetMapTileUrl
const tileAttribution = cartoApiKey
  ? cartoAttribution
  : openStreetMapAttribution

const activityMarkerIcon = new Icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

const dateFormatter = new Intl.DateTimeFormat('pl-PL', {
  dateStyle: 'medium',
  timeStyle: 'short',
  hour12: false,
})

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

function ActivityMap({ activities, mode, isVisible = true }: ActivityMapProps) {
  const tileUrl = mode === 'dark' ? darkTileUrl : lightTileUrl

  return (
    <aside className="activity-map" aria-label="Mapa aktywności">
      <MapContainer
        center={poznanCenter}
        zoom={12}
        className="activity-map__map"
        scrollWheelZoom
      >
        <MapResizeHandler isVisible={isVisible} />
        <TileLayer attribution={tileAttribution} maxZoom={20} url={tileUrl} />

        {activities.map((activity) => {
          const missingToMinimum = Math.max(
            activity.min_participants - activity.participant_count,
            0,
          )
          const hasParticipantLimit = activity.max_participants !== null

          return (
            <Marker
              key={activity.id}
              position={[activity.latitude, activity.longitude]}
              icon={activityMarkerIcon}
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
