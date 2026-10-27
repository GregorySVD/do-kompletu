import type { Activity } from '../types/activity'

type ActivityAvailabilityData = Pick<
  Activity,
  | 'available_slots'
  | 'max_participants'
  | 'min_participants'
  | 'participant_count'
  | 'status'
  | 'waitlist_count'
>

export type ActivityAvailabilityState =
  'available' | 'needs-minimum' | 'unavailable' | 'waitlist'

export interface ActivityAvailability {
  availableSlots: number | null
  isNearMinimum: boolean
  joinLabel: string
  missingToMinimum: number
  primaryMessage: string
  secondaryMessage: string
  state: ActivityAvailabilityState
}

function formatAvailablePlaces(count: number) {
  if (count === 1) {
    return '1 wolne miejsce'
  }

  const lastTwoDigits = count % 100
  const lastDigit = count % 10
  const usesPluralForm =
    lastDigit >= 2 &&
    lastDigit <= 4 &&
    (lastTwoDigits < 12 || lastTwoDigits > 14)

  return `${count} ${usesPluralForm ? 'wolne miejsca' : 'wolnych miejsc'}`
}

function formatPeople(count: number) {
  if (count === 1) {
    return '1 osoba'
  }

  const lastTwoDigits = count % 100
  const lastDigit = count % 10
  const usesPluralForm =
    lastDigit >= 2 &&
    lastDigit <= 4 &&
    (lastTwoDigits < 12 || lastTwoDigits > 14)

  return `${count} ${usesPluralForm ? 'osoby' : 'osób'}`
}

function getClosedRegistrationMessage(status: Activity['status']) {
  switch (status) {
    case 'CANCELLED':
      return 'Aktywność została anulowana.'
    case 'ONGOING':
      return 'Aktywność już trwa.'
    case 'ENDED':
      return 'Aktywność została zakończona.'
    default:
      return null
  }
}

export function getActivityAvailability(
  activity: ActivityAvailabilityData,
): ActivityAvailability {
  const missingToMinimum = Math.max(
    activity.min_participants - activity.participant_count,
    0,
  )
  const availableSlots =
    activity.max_participants === null
      ? null
      : (activity.available_slots ??
        Math.max(activity.max_participants - activity.participant_count, 0))
  const isFull = availableSlots === 0
  const isNearMinimum = missingToMinimum > 0 && missingToMinimum <= 2
  const closedRegistrationMessage = getClosedRegistrationMessage(
    activity.status,
  )

  if (closedRegistrationMessage !== null) {
    return {
      availableSlots,
      isNearMinimum: false,
      joinLabel: 'Zapisy zamknięte',
      missingToMinimum,
      primaryMessage: closedRegistrationMessage,
      secondaryMessage: 'Zapisy są zamknięte.',
      state: 'unavailable',
    }
  }

  if (isFull) {
    return {
      availableSlots,
      isNearMinimum: false,
      joinLabel: 'Dołącz do listy rezerwowej',
      missingToMinimum,
      primaryMessage:
        'Brak wolnych miejsc — możesz dołączyć do listy rezerwowej.',
      secondaryMessage:
        activity.waitlist_count > 0
          ? `Na liście rezerwowej: ${formatPeople(activity.waitlist_count)}`
          : 'Lista rezerwowa jest otwarta.',
      state: 'waitlist',
    }
  }

  const secondaryMessage =
    availableSlots === null
      ? 'Bez limitu miejsc'
      : formatAvailablePlaces(availableSlots)

  if (missingToMinimum > 0) {
    return {
      availableSlots,
      isNearMinimum,
      joinLabel: 'Dołącz do aktywności',
      missingToMinimum,
      primaryMessage: `Brakuje${isNearMinimum ? ' tylko' : ''} ${missingToMinimum} ${missingToMinimum === 1 ? 'osoby' : 'osób'} do osiągnięcia minimum.`,
      secondaryMessage,
      state: 'needs-minimum',
    }
  }

  return {
    availableSlots,
    isNearMinimum: false,
    joinLabel: 'Dołącz do aktywności',
    missingToMinimum,
    primaryMessage: 'Minimum osiągnięte — wciąż możesz dołączyć.',
    secondaryMessage,
    state: 'available',
  }
}
