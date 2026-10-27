import { useEffect, useRef } from 'react'
import './BouncingLogo.css'

const HORIZONTAL_TRAVEL_SECONDS = 6.5
const VERTICAL_TRAVEL_SECONDS = 5.25
const MIN_HORIZONTAL_SPEED = 48
const MIN_VERTICAL_SPEED = 38
const HUE_STEP = 67

function BouncingLogo() {
  const containerRef = useRef<HTMLDivElement>(null)
  const logoRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    const container = containerRef.current
    const logo = logoRef.current

    if (!container || !logo) {
      return
    }

    const animationContainer = container
    const animatedLogo = logo

    const reducedMotionQuery = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    )

    if (reducedMotionQuery.matches) {
      return
    }

    let animationFrameId = 0
    let previousTimestamp: number | null = null
    let x = 0
    let y = 0
    let directionX = 1
    let directionY = 1
    let hue = 0

    function animate(timestamp: number) {
      if (previousTimestamp === null) {
        previousTimestamp = timestamp
      }

      const elapsedSeconds = Math.min(
        (timestamp - previousTimestamp) / 1000,
        0.05,
      )
      previousTimestamp = timestamp

      const maxX = Math.max(
        animationContainer.clientWidth - animatedLogo.offsetWidth,
        0,
      )
      const maxY = Math.max(
        animationContainer.clientHeight - animatedLogo.offsetHeight,
        0,
      )
      const horizontalSpeed = Math.max(
        maxX / HORIZONTAL_TRAVEL_SECONDS,
        MIN_HORIZONTAL_SPEED,
      )
      const verticalSpeed = Math.max(
        maxY / VERTICAL_TRAVEL_SECONDS,
        MIN_VERTICAL_SPEED,
      )

      x += directionX * horizontalSpeed * elapsedSeconds
      y += directionY * verticalSpeed * elapsedSeconds

      let bounced = false

      if (maxX > 0 && (x <= 0 || x >= maxX)) {
        x = Math.min(Math.max(x, 0), maxX)
        directionX *= -1
        bounced = true
      } else if (maxX === 0) {
        x = 0
      }

      if (maxY > 0 && (y <= 0 || y >= maxY)) {
        y = Math.min(Math.max(y, 0), maxY)
        directionY *= -1
        bounced = true
      } else if (maxY === 0) {
        y = 0
      }

      if (bounced) {
        hue = (hue + HUE_STEP) % 360
        animatedLogo.style.setProperty('--bouncing-logo-hue', `${hue}deg`)
      }

      animatedLogo.style.transform = `translate3d(${x}px, ${y}px, 0)`
      animationFrameId = window.requestAnimationFrame(animate)
    }

    animationFrameId = window.requestAnimationFrame(animate)

    return () => {
      window.cancelAnimationFrame(animationFrameId)
    }
  }, [])

  return (
    <div ref={containerRef} className="bouncing-logo" aria-hidden="true">
      <img
        ref={logoRef}
        className="bouncing-logo__image"
        src="/bounce-logo.png"
        alt=""
        width="1125"
        height="1125"
      />
    </div>
  )
}

export default BouncingLogo
