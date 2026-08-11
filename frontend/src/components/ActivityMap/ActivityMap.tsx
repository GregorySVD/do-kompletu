import { Icon } from 'leaflet'
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet'
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
}

const poznanCenter: [number, number] = [52.4064, 16.9252]
const lightTileUrl =
  'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'
const darkTileUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
const tileAttribution =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attributions">CARTO</a>'

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

function ActivityMap({ activities, mode }: ActivityMapProps) {
  const tileUrl = mode === 'dark' ? darkTileUrl : lightTileUrl

  return (
    <aside className="activity-map" aria-label="Mapa aktywności">
      <MapContainer
        center={poznanCenter}
        zoom={12}
        className="activity-map__map"
      >
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
