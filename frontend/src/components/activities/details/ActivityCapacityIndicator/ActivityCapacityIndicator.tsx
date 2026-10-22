import { Chip, LinearProgress, Typography } from '@mui/material'
import type { ActivityDetails } from '../../../../types/activity'
import './ActivityCapacityIndicator.css'

interface ActivityCapacityIndicatorProps {
  activity: ActivityDetails
}

type CapacityLevel = 'available' | 'critical' | 'full' | 'unlimited' | 'warning'

function ActivityCapacityIndicator({
  activity,
}: ActivityCapacityIndicatorProps) {
  const maximum = activity.max_participants

  if (maximum === null) {
    return (
      <div className="activity-capacity activity-capacity--unlimited">
        <div className="activity-capacity__heading">
          <Typography variant="body2" color="text.secondary">
            Zajętość
          </Typography>
          <Chip label="Bez limitu miejsc" size="small" variant="outlined" />
        </div>
        <Typography className="activity-capacity__summary">
          {activity.participant_count} zapisanych uczestników
        </Typography>
      </div>
    )
  }

  const availableSlots =
    activity.available_slots ??
    Math.max(maximum - activity.participant_count, 0)
  const occupiedPercentage = Math.min(
    maximum > 0 ? (activity.participant_count / maximum) * 100 : 100,
    100,
  )
  const availableRatio = maximum > 0 ? availableSlots / maximum : 0
  const isFull = availableSlots === 0
  let level: CapacityLevel = 'available'
  let label = 'Dostępne miejsca'

  if (isFull) {
    level = 'full'
    label = 'FULL'
  } else if (availableRatio <= 0.1) {
    level = 'critical'
    label = 'Ostatnie miejsca'
  } else if (availableRatio <= 0.2) {
    level = 'warning'
    label = 'Mało miejsc'
  }

  const chipColor =
    level === 'full'
      ? 'error'
      : level === 'critical' || level === 'warning'
        ? 'warning'
        : 'success'

  return (
    <div className={`activity-capacity activity-capacity--${level}`}>
      <div className="activity-capacity__heading">
        <Typography variant="body2" color="text.secondary">
          Zajętość
        </Typography>
        <Chip label={label} size="small" color={chipColor} variant="outlined" />
      </div>

      <LinearProgress
        className="activity-capacity__progress"
        variant="determinate"
        value={occupiedPercentage}
        aria-label={`Zajętych ${activity.participant_count} z ${maximum} miejsc`}
      />

      <div className="activity-capacity__legend">
        <Typography>
          <strong>{activity.participant_count}</strong> / {maximum} zajętych
        </Typography>
        <Typography color="text.secondary">
          {isFull ? 'Brak wolnych miejsc' : `${availableSlots} wolnych miejsc`}
        </Typography>
      </div>

      {isFull && activity.status === 'PUBLISHED' && (
        <Typography className="activity-capacity__waitlist-note">
          Kolejne zgłoszenia trafiają na listę rezerwową.
        </Typography>
      )}
    </div>
  )
}

export default ActivityCapacityIndicator
