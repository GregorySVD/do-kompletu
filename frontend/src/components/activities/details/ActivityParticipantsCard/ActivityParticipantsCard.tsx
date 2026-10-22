import { GroupsOutlined, HourglassBottom } from '@mui/icons-material'
import { Card, CardContent, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'
import ActivityCapacityIndicator from '../ActivityCapacityIndicator/ActivityCapacityIndicator'
import './ActivityParticipantsCard.css'

interface ActivityParticipantsCardProps {
  activity: ActivityDetails
}

function ActivityParticipantsCard({ activity }: ActivityParticipantsCardProps) {
  const missingToMinimum = Math.max(
    activity.min_participants - activity.participant_count,
    0,
  )

  return (
    <Card
      component="section"
      variant="outlined"
      className="activity-participants-card"
    >
      <CardContent className="activity-participants-card__content">
        <div className="activity-participants-card__heading">
          <span className="activity-participants-card__heading-icon">
            <GroupsOutlined aria-hidden="true" />
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
          <div>
            <dt>Minimum</dt>
            <dd>{activity.min_participants} osób</dd>
          </div>
          <div>
            <dt>Status kompletu</dt>
            <dd>
              {missingToMinimum > 0
                ? `Brakuje ${missingToMinimum} osób`
                : 'Komplet zebrany'}
            </dd>
          </div>
          <div>
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
