import { Icon } from 'leaflet'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import type { ThemeMode } from './themeMode'

export const poznanMapCenter: [number, number] = [52.4064, 16.9252]

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

export const mapMarkerIcon = new Icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

export function getMapTileConfig(mode: ThemeMode) {
  return {
    attribution: cartoApiKey ? cartoAttribution : openStreetMapAttribution,
    url: mode === 'dark' ? darkTileUrl : lightTileUrl,
  }
}
