import { Chip, type ChipProps } from '@mui/material'
import type { PriceType } from '../../types/activity'
import './ActivityPriceBadge.css'

interface ActivityPriceBadgeProps {
  priceType: PriceType
  priceAmount?: number | null
  currency?: string | null
  className?: string
  size?: ChipProps['size']
}

function getPriceLabel(
  priceType: PriceType,
  priceAmount?: number | null,
  currency?: string | null,
) {
  if (priceType === 'FREE') {
    return 'Bezpłatna'
  }

  if (priceAmount !== null && priceAmount !== undefined && currency) {
    return `${priceAmount} ${currency}`
  }

  return 'Płatna'
}

function ActivityPriceBadge({
  priceType,
  priceAmount,
  currency,
  className,
  size,
}: ActivityPriceBadgeProps) {
  const variant = priceType === 'FREE' ? 'free' : 'paid'
  const iconSrc =
    priceType === 'FREE'
      ? '/icons/icons8-confetti-64.png'
      : '/icons/icons8-money-64.png'

  return (
    <Chip
      className={[
        'activity-price-badge',
        `activity-price-badge--${variant}`,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      icon={
        <img
          className="activity-price-badge__image"
          src={iconSrc}
          alt=""
          width="64"
          height="64"
        />
      }
      label={getPriceLabel(priceType, priceAmount, currency)}
      size={size}
      variant="outlined"
    />
  )
}

export default ActivityPriceBadge
