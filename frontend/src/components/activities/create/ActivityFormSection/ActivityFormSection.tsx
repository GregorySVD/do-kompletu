import { useId, type ReactNode } from 'react'
import './ActivityFormSection.css'

interface ActivityFormSectionProps {
  children: ReactNode
  className?: string
  description: string
  iconSrc: string
  step: string
  title: string
}

function ActivityFormSection({
  children,
  className,
  description,
  iconSrc,
  step,
  title,
}: ActivityFormSectionProps) {
  const titleId = useId()

  return (
    <section
      className={['activity-form-section', className].filter(Boolean).join(' ')}
      aria-labelledby={titleId}
    >
      <header className="activity-form-section__header">
        <div className="activity-form-section__icon" aria-hidden="true">
          <img src={iconSrc} alt="" width="64" height="64" />
        </div>

        <div className="activity-form-section__heading">
          <span className="activity-form-section__step">Etap {step}</span>
          <h2 id={titleId} className="activity-form-section__title">
            {title}
          </h2>
          <p className="activity-form-section__description">{description}</p>
        </div>
      </header>

      <div className="activity-form-section__content">{children}</div>
    </section>
  )
}

export default ActivityFormSection
