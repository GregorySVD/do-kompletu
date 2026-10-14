import { Close } from '@mui/icons-material'
import { IconButton, Tooltip } from '@mui/material'
import type { Activity } from '../../../types/activity'
import ActivityMap from '../../ActivityMap/ActivityMap'
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

      <ActivityMap activities={activities} isVisible={isVisible} mode={mode} />
    </div>
  )
}

export default HomeMapPanel
