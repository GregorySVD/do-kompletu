import './LoadingSkeleton.css'

export type LoadingSkeletonVariant =
  | 'route'
  | 'activity-list'
  | 'activity-details'
  | 'activity-form'
  | 'profile-section'

interface LoadingSkeletonProps {
  className?: string
  embedded?: boolean
  message?: string
  variant?: LoadingSkeletonVariant
}

const loadingMessages: Record<LoadingSkeletonVariant, string> = {
  route: 'Ładowanie widoku...',
  'activity-list': 'Ładowanie listy aktywności...',
  'activity-details': 'Ładowanie szczegółów aktywności...',
  'activity-form': 'Ładowanie formularza aktywności...',
  'profile-section': 'Ładowanie profilu...',
}

function SkeletonLine({
  size = 'full',
}: {
  size?: 'full' | 'long' | 'medium' | 'short'
}) {
  return (
    <span
      className={`loading-skeleton__line loading-skeleton__line--${size}`}
    />
  )
}

function SkeletonActivityCard() {
  return (
    <div className="loading-skeleton__activity-card">
      <div className="loading-skeleton__card-heading">
        <SkeletonLine size="medium" />
        <span className="loading-skeleton__badge" />
      </div>
      <div className="loading-skeleton__metadata">
        <span className="loading-skeleton__metadata-cell" />
        <span className="loading-skeleton__metadata-cell" />
        <span className="loading-skeleton__metadata-cell" />
      </div>
      <div className="loading-skeleton__card-footer">
        <span className="loading-skeleton__badge loading-skeleton__badge--wide" />
        <SkeletonLine size="short" />
      </div>
    </div>
  )
}

function RouteSkeleton() {
  return (
    <>
      <div className="loading-skeleton__hero">
        <SkeletonLine size="short" />
        <SkeletonLine size="medium" />
        <SkeletonLine size="long" />
      </div>
      <div className="loading-skeleton__route-grid">
        <div className="loading-skeleton__panel">
          <SkeletonLine size="medium" />
          <SkeletonLine />
          <SkeletonLine size="long" />
        </div>
        <div className="loading-skeleton__panel">
          <SkeletonLine size="short" />
          <SkeletonLine size="long" />
          <SkeletonLine size="medium" />
        </div>
      </div>
    </>
  )
}

function ActivityListSkeleton() {
  return (
    <>
      <div className="loading-skeleton__hero">
        <SkeletonLine size="short" />
        <SkeletonLine size="medium" />
        <SkeletonLine size="long" />
      </div>
      <div className="loading-skeleton__list-toolbar">
        <span className="loading-skeleton__control" />
        <span className="loading-skeleton__control" />
        <span className="loading-skeleton__control" />
      </div>
      <div className="loading-skeleton__activity-list">
        {Array.from({ length: 3 }, (_, index) => (
          <SkeletonActivityCard key={index} />
        ))}
      </div>
    </>
  )
}

function ActivityDetailsSkeleton() {
  return (
    <>
      <div className="loading-skeleton__details-hero">
        <div>
          <SkeletonLine size="short" />
          <SkeletonLine size="medium" />
          <SkeletonLine size="long" />
        </div>
        <span className="loading-skeleton__pixel-icon" />
      </div>
      <div className="loading-skeleton__details-grid">
        <div className="loading-skeleton__details-main">
          <div className="loading-skeleton__panel loading-skeleton__panel--tall">
            <SkeletonLine size="medium" />
            <span className="loading-skeleton__progress" />
            <div className="loading-skeleton__metadata">
              <span className="loading-skeleton__metadata-cell" />
              <span className="loading-skeleton__metadata-cell" />
              <span className="loading-skeleton__metadata-cell" />
            </div>
          </div>
          <div className="loading-skeleton__panel">
            <SkeletonLine size="short" />
            <SkeletonLine size="long" />
            <SkeletonLine size="medium" />
          </div>
        </div>
        <div className="loading-skeleton__details-side">
          <div className="loading-skeleton__panel loading-skeleton__panel--map" />
          <div className="loading-skeleton__panel">
            <SkeletonLine size="short" />
            <SkeletonLine size="medium" />
          </div>
        </div>
      </div>
    </>
  )
}

function ActivityFormSkeleton() {
  return (
    <>
      <div className="loading-skeleton__hero">
        <SkeletonLine size="short" />
        <SkeletonLine size="medium" />
        <SkeletonLine size="long" />
      </div>
      <div className="loading-skeleton__form-grid">
        <div className="loading-skeleton__form-fields">
          {Array.from({ length: 4 }, (_, index) => (
            <div className="loading-skeleton__field" key={index}>
              <SkeletonLine size="short" />
              <span className="loading-skeleton__input" />
            </div>
          ))}
        </div>
        <div className="loading-skeleton__panel loading-skeleton__panel--summary">
          <SkeletonLine size="medium" />
          <SkeletonLine />
          <SkeletonLine size="long" />
          <span className="loading-skeleton__button" />
        </div>
      </div>
    </>
  )
}

function ProfileSectionSkeleton() {
  return (
    <>
      <div className="loading-skeleton__profile-hero">
        <span className="loading-skeleton__avatar" />
        <div className="loading-skeleton__profile-copy">
          <SkeletonLine size="medium" />
          <SkeletonLine size="long" />
          <SkeletonLine size="short" />
        </div>
      </div>
      <div className="loading-skeleton__profile-sections">
        <div className="loading-skeleton__panel">
          <SkeletonLine size="medium" />
          <SkeletonActivityCard />
        </div>
        <div className="loading-skeleton__panel">
          <SkeletonLine size="short" />
          <SkeletonLine />
          <SkeletonLine size="medium" />
        </div>
      </div>
    </>
  )
}

function LoadingSkeleton({
  className = '',
  embedded = false,
  message,
  variant = 'route',
}: LoadingSkeletonProps) {
  const skeletonClassName = [
    'loading-skeleton',
    `loading-skeleton--${variant}`,
    embedded && 'loading-skeleton--embedded',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <section
      className={skeletonClassName}
      role="status"
      aria-busy="true"
      aria-live="polite"
    >
      <span className="loading-skeleton__sr-only">
        {message ?? loadingMessages[variant]}
      </span>
      <div className="loading-skeleton__frame" aria-hidden="true">
        {variant === 'activity-list' && <ActivityListSkeleton />}
        {variant === 'activity-details' && <ActivityDetailsSkeleton />}
        {variant === 'activity-form' && <ActivityFormSkeleton />}
        {variant === 'profile-section' && <ProfileSectionSkeleton />}
        {variant === 'route' && <RouteSkeleton />}
      </div>
    </section>
  )
}

export default LoadingSkeleton
