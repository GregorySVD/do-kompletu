import { Typography } from '@mui/material'
import UserAvatar from '../../../UserAvatar/UserAvatar'
import type { ActivityDetails } from '../../../../types/activity'
import './ActivityOrganizerCard.css'

interface ActivityOrganizerCardProps {
  activity: ActivityDetails
}

function ActivityOrganizerCard({ activity }: ActivityOrganizerCardProps) {
  const { organizer } = activity

  return (
    <section
      className="activity-organizer-card"
      aria-labelledby="activity-organizer-title"
    >
      <div className="activity-organizer-card__content">
        <Typography
          id="activity-organizer-title"
          className="activity-organizer-card__title"
          component="h2"
          variant="h5"
        >
          Organizator
        </Typography>
        <div className="activity-organizer-card__profile">
          <UserAvatar
            className="activity-organizer-card__avatar"
            avatarUrl={organizer.avatar_url}
            displayName={organizer.display_name}
          />
          <div className="activity-organizer-card__profile-copy">
            <Typography className="activity-organizer-card__name">
              {organizer.display_name}
            </Typography>
            <Typography
              className="activity-organizer-card__role"
              variant="body2"
              color="text.secondary"
            >
              Organizator aktywności
            </Typography>
          </div>
        </div>
      </div>
    </section>
  )
}

export default ActivityOrganizerCard
