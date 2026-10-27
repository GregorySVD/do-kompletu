import { HourglassBottom } from '@mui/icons-material'
import { Card, CardContent, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'
import { getActivityAvailability } from '../../../../utils/activityAvailability'
import ActivityCapacityIndicator from '../ActivityCapacityIndicator/ActivityCapacityIndicator'
import './ActivityParticipantsCard.css'

interface ActivityParticipantsCardProps {
  activity: ActivityDetails
}

function ActivityParticipantsCard({ activity }: ActivityParticipantsCardProps) {
  const availability = getActivityAvailability(activity)

  return (
    <Card
      component="section"
      variant="outlined"
      className="activity-participants-card"
    >
      <CardContent className="activity-participants-card__content">
        <div className="activity-participants-card__heading">
          <span className="activity-participants-card__heading-icon">
            <img
              src="/favicon.png"
              alt=""
              width="1254"
              height="1254"
              aria-hidden="true"
            />
          </span>
          <div>
            <Typography component="h2" variant="h5">
              Uczestnicy i miejsca
            </Typography>
            <Typography color="text.secondary">
              Aktualne zainteresowanie aktywnością
            </Typography>
          </div>
        </div>

        <ActivityCapacityIndicator activity={activity} />

        <dl className="activity-participants-card__metrics">
          <div className="activity-participants-card__metric activity-participants-card__metric--minimum">
            <dt>Minimum</dt>
            <dd>{activity.min_participants} osób</dd>
          </div>
          <div
            className={`activity-participants-card__metric activity-participants-card__metric--status activity-participants-card__metric--${availability.state}`}
          >
            <dt>Status zapisów</dt>
            <dd>{availability.primaryMessage}</dd>
          </div>
          <div className="activity-participants-card__metric activity-participants-card__metric--waitlist">
            <dt>
              <HourglassBottom aria-hidden="true" /> Lista rezerwowa
            </dt>
            <dd>{activity.waitlist_count} osób</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}

export default ActivityParticipantsCard
