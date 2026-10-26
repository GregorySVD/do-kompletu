import { Avatar, Typography } from '@mui/material'
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
          <Avatar
            className="activity-organizer-card__avatar"
            src={organizer.avatar_url ?? undefined}
            alt={organizer.display_name}
          >
            <img
              className="activity-organizer-card__avatar-fallback"
              src="/icons/icons8-avatar-64.png"
              alt=""
              width="64"
              height="64"
              aria-hidden="true"
            />
          </Avatar>
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
