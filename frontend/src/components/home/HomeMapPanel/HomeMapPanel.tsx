import type { Activity } from '../../../types/activity'
import ActivityMap from '../../ActivityMap/ActivityMap'
import './HomeMapPanel.css'

interface HomeMapPanelProps {
  activities: Activity[]
  mode: 'light' | 'dark'
  isVisible: boolean
  isMobileHidden: boolean
}

function HomeMapPanel({
  activities,
  mode,
  isVisible,
  isMobileHidden,
}: HomeMapPanelProps) {
  return (
    <div
      className={`home-map-panel${isMobileHidden ? ' home-map-panel--mobile-hidden' : ''}`}
    >
      <ActivityMap activities={activities} isVisible={isVisible} mode={mode} />
    </div>
  )
}

export default HomeMapPanel
