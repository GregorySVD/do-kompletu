import { Button } from '@mui/material'
import './ActivityFormSubmitBar.css'

interface ActivityFormSubmitBarProps {
  completedFieldCount: number
  disabled: boolean
  isSubmitting: boolean
  requiredFieldCount: number
  submitIconSrc: string
  submitLabel: string
  submittingLabel: string
}

function ActivityFormSubmitBar({
  completedFieldCount,
  disabled,
  isSubmitting,
  requiredFieldCount,
  submitIconSrc,
  submitLabel,
  submittingLabel,
}: ActivityFormSubmitBarProps) {
  const isComplete = completedFieldCount === requiredFieldCount

  return (
    <footer className="activity-form-submit-bar">
      <div className="activity-form-submit-bar__status" aria-live="polite">
        <span className="activity-form-submit-bar__eyebrow">
          Gotowość formularza
        </span>
        <strong>
          {completedFieldCount} / {requiredFieldCount} elementów
        </strong>
        <span>
          {isComplete
            ? 'Wszystko gotowe — możesz opublikować aktywność.'
            : 'Uzupełnij brakujące informacje oznaczone w formularzu.'}
        </span>
      </div>

      <Button
        className="activity-form-submit-bar__button"
        disabled={disabled}
        type="submit"
        startIcon={
          <img
            src={submitIconSrc}
            alt=""
            width="64"
            height="64"
            aria-hidden="true"
          />
        }
      >
        {isSubmitting ? submittingLabel : submitLabel}
      </Button>
    </footer>
  )
}

export default ActivityFormSubmitBar
