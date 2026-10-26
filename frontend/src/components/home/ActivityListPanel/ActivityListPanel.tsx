import { Button, Typography } from '@mui/material'
import type { RefObject } from 'react'
import type { Activity } from '../../../types/activity'
import ActivityCard from '../../ActivityCard/ActivityCard'
import ActivityFilters, {
  type ActivityFilterProps,
} from '../ActivityFilters/ActivityFilters'
import './ActivityListPanel.css'

interface ActivityListPanelProps {
  activities: Activity[]
  filterProps: ActivityFilterProps
  isMobileHidden: boolean
  scrollContainerRef: RefObject<HTMLDivElement | null>
}

function ActivityListPanel({
  activities,
  filterProps,
  isMobileHidden,
  scrollContainerRef,
}: ActivityListPanelProps) {
  return (
    <section
      className={`activities${isMobileHidden ? ' activities--mobile-hidden' : ''}`}
      aria-labelledby="activities-title"
    >
      <div className="activities__heading">
        <div>
          <Typography id="activities-title" component="h1" variant="h5">
            Aktywności w Twojej okolicy
          </Typography>
          <Typography className="activities__subtitle" color="text.secondary">
            Znajdź aktywność i dołącz do innych
          </Typography>
        </div>

        <Typography className="activities__count" color="text.secondary">
          {activities.length} aktywności
        </Typography>
      </div>

      <section
        className="filters filters--desktop"
        aria-labelledby="desktop-filters-title"
      >
        <ActivityFilters titleId="desktop-filters-title" {...filterProps} />
      </section>

      <div ref={scrollContainerRef} className="activities__scroll">
        <div className="activities__list">
          {activities.length > 0 ? (
            activities.map((activity) => (
              <ActivityCard
                key={activity.id}
                activity={activity}
                emphasizeMetadata
              />
            ))
          ) : (
            <div className="activities__empty">
              <Typography component="h2" variant="h6">
                Nie znaleziono aktywności
              </Typography>
              <Typography color="text.secondary">
                Spróbuj zmienić wyszukiwaną frazę lub wybrane filtry.
              </Typography>
              <Button variant="outlined" onClick={filterProps.onClearFilters}>
                Wyczyść filtry
              </Button>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

export default ActivityListPanel
