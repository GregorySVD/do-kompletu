import {
  CheckCircleRounded,
  RadioButtonUncheckedRounded,
} from '@mui/icons-material'
import { useId } from 'react'
import ActivityCategoryBadge from '../../../ActivityCategoryBadge/ActivityCategoryBadge'
import type { ActivityCategory, PriceType } from '../../../../types/activity'
import type { ActivityFormValues } from '../../../../types/activityForm'
import './ActivityFormSummary.css'

interface ActivityFormSummaryProps {
  categories: ActivityCategory[]
  completedFieldCount: number
  requiredFieldCount: number
  values: ActivityFormValues
}

interface SummaryChecklistItem {
  complete: boolean
  label: string
}

const activityDateFormatter = new Intl.DateTimeFormat('pl-PL', {
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  month: 'short',
  year: 'numeric',
})

function isValidDate(value: string) {
  return value !== '' && !Number.isNaN(Date.parse(value))
}

function formatDate(value: string) {
  if (!isValidDate(value)) {
    return 'Nie ustawiono'
  }

  return activityDateFormatter.format(new Date(value))
}

function formatPrice(priceType: PriceType, priceAmount: number | null) {
  if (priceType === 'FREE') {
    return 'Bezpłatna'
  }

  if (priceAmount === null || priceAmount <= 0) {
    return 'Cena do uzupełnienia'
  }

  return `${priceAmount.toLocaleString('pl-PL', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} PLN`
}

function getCompletionPercentage(completed: number, required: number) {
  if (required <= 0) {
    return 0
  }

  return Math.min(100, Math.max(0, Math.round((completed / required) * 100)))
}

function ActivityFormSummary({
  categories,
  completedFieldCount,
  requiredFieldCount,
  values,
}: ActivityFormSummaryProps) {
  const titleId = useId()
  const selectedCategory = categories.find(
    (category) => category.id === values.category_id,
  )
  const completionPercentage = getCompletionPercentage(
    completedFieldCount,
    requiredFieldCount,
  )
  const hasValidSchedule =
    isValidDate(values.start_at) &&
    isValidDate(values.end_at) &&
    new Date(values.end_at) > new Date(values.start_at)
  const hasValidParticipants =
    values.min_participants >= 2 &&
    (!values.has_participant_limit ||
      (values.max_participants !== null &&
        values.max_participants >= values.min_participants)) &&
    (values.price_type === 'FREE' ||
      (values.price_amount !== null && values.price_amount > 0))
  const checklist: SummaryChecklistItem[] = [
    {
      label: 'Podstawowe informacje',
      complete:
        values.title.trim().length >= 3 &&
        values.description.trim().length >= 10 &&
        values.category_id !== '',
    },
    { label: 'Termin aktywności', complete: hasValidSchedule },
    {
      label: 'Miejsce i punkt na mapie',
      complete:
        values.location_name.trim() !== '' &&
        values.address.trim() !== '' &&
        values.latitude !== null &&
        values.longitude !== null,
    },
    { label: 'Uczestnicy i koszt', complete: hasValidParticipants },
  ]
  const participantLimit = values.has_participant_limit
    ? `maks. ${values.max_participants ?? '?'} os.`
    : 'bez limitu'

  return (
    <aside className="activity-form-summary" aria-labelledby={titleId}>
      <div className="activity-form-summary__header">
        <span className="activity-form-summary__eyebrow">Podgląd na żywo</span>
        <h2 id={titleId} className="activity-form-summary__title">
          Twoja aktywność
        </h2>
        <p className="activity-form-summary__hint">
          Tak najważniejsze informacje zobaczą uczestnicy.
        </p>
      </div>

      <div className="activity-form-summary__progress">
        <div className="activity-form-summary__progress-copy">
          <span>Kompletność formularza</span>
          <strong>{completionPercentage}%</strong>
        </div>
        <div
          className="activity-form-summary__progress-track"
          role="progressbar"
          aria-label="Kompletność formularza"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={completionPercentage}
        >
          <span style={{ width: `${completionPercentage}%` }} />
        </div>
        <span className="activity-form-summary__progress-count">
          {completedFieldCount} z {requiredFieldCount} wymaganych pól
        </span>
      </div>

      <div className="activity-form-summary__preview">
        <div className="activity-form-summary__category">
          {selectedCategory ? (
            <ActivityCategoryBadge category={selectedCategory} size="small" />
          ) : (
            <span className="activity-form-summary__placeholder-badge">
              Wybierz kategorię
            </span>
          )}
        </div>

        <h3 className="activity-form-summary__activity-title">
          {values.title.trim() || 'Tytuł Twojej aktywności'}
        </h3>

        <dl className="activity-form-summary__details">
          <div>
            <dt>
              <img
                src="/icons/icons8-schedule-64.png"
                alt=""
                width="64"
                height="64"
                aria-hidden="true"
              />
              Termin
            </dt>
            <dd>
              <span>{formatDate(values.start_at)}</span>
              <span className="activity-form-summary__detail-separator">→</span>
              <span>{formatDate(values.end_at)}</span>
            </dd>
          </div>

          <div>
            <dt>
              <img
                src="/icons/icons8-place-64.png"
                alt=""
                width="64"
                height="64"
                aria-hidden="true"
              />
              Miejsce
            </dt>
            <dd>
              {values.location_name.trim() || 'Nie wybrano miejsca'}
              {values.address.trim() && <small>{values.address.trim()}</small>}
            </dd>
          </div>

          <div>
            <dt>
              <img
                src="/icons/icons8-avatar-64.png"
                alt=""
                width="64"
                height="64"
                aria-hidden="true"
              />
              Uczestnicy
            </dt>
            <dd>
              minimum {values.min_participants} os. · {participantLimit}
            </dd>
          </div>

          <div>
            <dt>
              <img
                src="/icons/icons8-money-64.png"
                alt=""
                width="64"
                height="64"
                aria-hidden="true"
              />
              Koszt
            </dt>
            <dd>{formatPrice(values.price_type, values.price_amount)}</dd>
          </div>
        </dl>
      </div>

      <ul
        className="activity-form-summary__checklist"
        aria-label="Etapy formularza"
      >
        {checklist.map((item) => {
          const StatusIcon = item.complete
            ? CheckCircleRounded
            : RadioButtonUncheckedRounded

          return (
            <li
              key={item.label}
              className={
                item.complete
                  ? 'activity-form-summary__checklist-item activity-form-summary__checklist-item--complete'
                  : 'activity-form-summary__checklist-item'
              }
            >
              <StatusIcon aria-hidden="true" />
              <span>{item.label}</span>
            </li>
          )
        })}
      </ul>
    </aside>
  )
}

export default ActivityFormSummary
