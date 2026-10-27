import type { ActivityDetails } from '../../../../types/activity'
import ActivityDetailsHero from '../ActivityDetailsHero/ActivityDetailsHero'
import ActivityLocationCard from '../ActivityLocationCard/ActivityLocationCard'
import ActivityOrganizerActions from '../ActivityOrganizerActions/ActivityOrganizerActions'
import ActivityOrganizerCard from '../ActivityOrganizerCard/ActivityOrganizerCard'
import ActivityParticipantActions from '../ActivityParticipantActions/ActivityParticipantActions'
import ActivityParticipantsCard from '../ActivityParticipantsCard/ActivityParticipantsCard'
import ActivityParticipationWindowsCard from '../ActivityParticipationWindowsCard/ActivityParticipationWindowsCard'
import ActivityScheduleCard from '../ActivityScheduleCard/ActivityScheduleCard'
import ActivityTagsCard from '../ActivityTagsCard/ActivityTagsCard'
import './ActivityDetailsContent.css'

interface ActivityDetailsContentProps {
  activity: ActivityDetails
}

function ActivityDetailsContent({ activity }: ActivityDetailsContentProps) {
  return (
    <>
      <ActivityDetailsHero activity={activity} />

      <div className="activity-details-content__layout">
        <div className="activity-details-content__actions">
          <ActivityParticipantActions activity={activity} />
          <ActivityOrganizerActions activity={activity} />
        </div>

        <div className="activity-details-content__main">
          <ActivityParticipantsCard activity={activity} />
          <ActivityScheduleCard activity={activity} />
          <ActivityParticipationWindowsCard activity={activity} />
        </div>

        <aside
          className="activity-details-content__sidebar"
          aria-label="Dodatkowe informacje o aktywności"
        >
          <ActivityLocationCard activity={activity} />
          <ActivityOrganizerCard activity={activity} />
          <ActivityTagsCard activity={activity} />
        </aside>
      </div>
    </>
  )
}

export default ActivityDetailsContent
