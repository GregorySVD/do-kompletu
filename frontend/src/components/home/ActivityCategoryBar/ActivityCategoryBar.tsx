import { getActivityCategoryPresentation } from '../../../config/activityCategoryPresentation'
import type { ActivityCategory } from '../../../types/activity'
import './ActivityCategoryBar.css'

export interface ActivityCategoryBarItem extends ActivityCategory {
  count: number
}

interface ActivityCategoryBarProps {
  categories: ActivityCategoryBarItem[]
  selectedCategoryId: string | null
  onToggleCategory: (categoryId: string) => void
}

function ActivityCategoryBar({
  categories,
  selectedCategoryId,
  onToggleCategory,
}: ActivityCategoryBarProps) {
  return (
    <nav className="activity-category-bar" aria-label="Kategorie aktywności">
      <div className="activity-category-bar__scroller">
        <div className="activity-category-bar__list">
          {categories.map((category) => {
            const isSelected = selectedCategoryId === category.id
            const presentation = getActivityCategoryPresentation(category.slug)
            const CategoryIcon = presentation.icon

            return (
              <button
                key={category.id}
                className={`activity-category-bar__item activity-category-bar__item--${presentation.variant}${isSelected ? ' activity-category-bar__item--selected' : ''}`}
                type="button"
                aria-label={`${category.name}, ${category.count} aktywności`}
                aria-pressed={isSelected}
                onClick={() => onToggleCategory(category.id)}
              >
                <span className="activity-category-bar__icon-wrap">
                  <CategoryIcon
                    className="activity-category-bar__icon"
                    aria-hidden="true"
                  />
                  <span className="activity-category-bar__badge">
                    {category.count}
                  </span>
                </span>
                <span className="activity-category-bar__name">
                  {category.name}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </nav>
  )
}

export default ActivityCategoryBar
