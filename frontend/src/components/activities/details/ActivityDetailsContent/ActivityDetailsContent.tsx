import type { ActivityDetails } from '../../../../types/activity'
import ActivityDetailsSummary from '../ActivityDetailsSummary/ActivityDetailsSummary'
import ActivityLifecycleInfo from '../ActivityLifecycleInfo/ActivityLifecycleInfo'
import ActivityOrganizerInfo from '../ActivityOrganizerInfo/ActivityOrganizerInfo'
import ActivityParticipantsInfo from '../ActivityParticipantsInfo/ActivityParticipantsInfo'
import ActivityScheduleLocation from '../ActivityScheduleLocation/ActivityScheduleLocation'
import './ActivityDetailsContent.css'

interface ActivityDetailsContentProps {
  activity: ActivityDetails
}

function ActivityDetailsContent({ activity }: ActivityDetailsContentProps) {
  return (
    <>
      <ActivityDetailsSummary activity={activity} />

      <div className="activity-details-content__grid">
        <ActivityScheduleLocation activity={activity} />
        <ActivityParticipantsInfo activity={activity} />
        <ActivityOrganizerInfo activity={activity} />
        <ActivityLifecycleInfo activity={activity} />
      </div>
    </>
  )
}

export default ActivityDetailsContent
