import { getActivityCategoryPresentation } from '../../../../config/activityCategoryPresentation'
import type { ActivityCategory } from '../../../../types/activity'
import './ActivityCategorySelector.css'

interface ActivityCategorySelectorProps {
  categories: ActivityCategory[]
  disabled: boolean
  error?: string
  onChange: (categoryId: string) => void
  value: string
}

function ActivityCategorySelector({
  categories,
  disabled,
  error,
  onChange,
  value,
}: ActivityCategorySelectorProps) {
  return (
    <div className="activity-category-selector">
      <div
        className="activity-category-selector__grid"
        role="radiogroup"
        aria-label="Kategoria aktywności"
        aria-describedby={
          error ? 'activity-category-selector-error' : undefined
        }
      >
        {categories.map((category) => {
          const presentation = getActivityCategoryPresentation(category.slug)
          const CategoryIcon = presentation.icon
          const isSelected = category.id === value

          return (
            <button
              key={category.id}
              className={`activity-category-selector__option activity-category-selector__option--${presentation.variant}${isSelected ? ' activity-category-selector__option--selected' : ''}`}
              type="button"
              role="radio"
              aria-checked={isSelected}
              disabled={disabled}
              onClick={() => onChange(category.id)}
            >
              <span
                className="activity-category-selector__icon"
                aria-hidden="true"
              >
                {presentation.pixelIconSrc ? (
                  <img
                    src={presentation.pixelIconSrc}
                    alt=""
                    width="32"
                    height="32"
                  />
                ) : (
                  <CategoryIcon />
                )}
              </span>
              <span className="activity-category-selector__name">
                {category.name}
              </span>
              <span
                className="activity-category-selector__state"
                aria-hidden="true"
              >
                {isSelected ? 'Wybrano' : 'Wybierz'}
              </span>
            </button>
          )
        })}
      </div>

      {error && (
        <p
          id="activity-category-selector-error"
          className="activity-category-selector__error"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  )
}

export default ActivityCategorySelector
