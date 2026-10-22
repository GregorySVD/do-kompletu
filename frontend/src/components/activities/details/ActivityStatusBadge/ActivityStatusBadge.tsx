import { Chip, type ChipProps } from '@mui/material'
import type { ActivityStatus } from '../../../../types/activity'

interface ActivityStatusBadgeProps {
  status: ActivityStatus
}

const statusPresentation: Record<
  ActivityStatus,
  { color: ChipProps['color']; label: string }
> = {
  PUBLISHED: { color: 'info', label: 'Zaplanowana' },
  ONGOING: { color: 'success', label: 'W trakcie' },
  ENDED: { color: 'default', label: 'Zakończona' },
  CANCELLED: { color: 'error', label: 'Anulowana' },
}

function ActivityStatusBadge({ status }: ActivityStatusBadgeProps) {
  const presentation = statusPresentation[status]

  return (
    <Chip
      label={presentation.label}
      color={presentation.color}
      variant="outlined"
    />
  )
}

export default ActivityStatusBadge
