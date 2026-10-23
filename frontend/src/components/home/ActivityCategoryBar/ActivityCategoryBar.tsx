import { getActivityCategoryPresentation } from '../../../config/activityCategoryPresentation'
import type { ActivityCategory } from '../../../types/activity'
import './ActivityCategoryBar.css'

export interface ActivityCategoryBarItem extends ActivityCategory {
  count: number
}

export type ActivityCategoryBarVariant = 'bar' | 'compact'

export interface ActivityCategoryBarProps {
  categories: ActivityCategoryBarItem[]
  selectedCategoryId: string | null
  onToggleCategory: (categoryId: string) => void
  variant?: ActivityCategoryBarVariant
}

function ActivityCategoryBar({
  categories,
  selectedCategoryId,
  onToggleCategory,
  variant = 'bar',
}: ActivityCategoryBarProps) {
  return (
    <nav
      className={`activity-category-bar activity-category-bar--${variant}`}
      aria-label="Kategorie aktywności"
    >
      <div className="activity-category-bar__scroller">
        <div className="activity-category-bar__list">
          {categories.map((category) => {
            const isSelected = selectedCategoryId === category.id
            const isDimmed =
              variant === 'bar' && selectedCategoryId !== null && !isSelected
            const presentation = getActivityCategoryPresentation(category.slug)
            const CategoryIcon = presentation.icon

            return (
              <button
                key={category.id}
                className={`activity-category-bar__item activity-category-bar__item--${presentation.variant}${isSelected ? ' activity-category-bar__item--selected' : ''}${isDimmed ? ' activity-category-bar__item--dimmed' : ''}`}
                type="button"
                aria-label={`${category.name}, ${category.count} aktywności`}
                aria-pressed={isSelected}
                onClick={() => onToggleCategory(category.id)}
              >
                <span className="activity-category-bar__icon-wrap">
                  {presentation.pixelIconSrc ? (
                    <img
                      className="activity-category-bar__pixel-icon"
                      src={presentation.pixelIconSrc}
                      alt=""
                      width="32"
                      height="32"
                    />
                  ) : (
                    <CategoryIcon
                      className="activity-category-bar__icon"
                      aria-hidden="true"
                    />
                  )}
                </span>
                <span className="activity-category-bar__name">
                  {category.name}
                </span>
                <span className="activity-category-bar__badge">
                  {category.count}
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
