import { lazy, Suspense, useEffect, useState } from 'react'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import { Route, Routes, useLocation } from 'react-router-dom'
import Header from './components/Header/Header'
import RequireAuth from './components/RequireAuth/RequireAuth'
import LoadingSkeleton, {
  type LoadingSkeletonVariant,
} from './components/system/LoadingSkeleton/LoadingSkeleton'
import ServiceUnavailable from './components/system/ServiceUnavailable/ServiceUnavailable'
import { useAuth } from './context/auth'
import {
  applyThemeMode,
  getInitialThemeMode,
  type ThemeMode,
} from './utils/themeMode'
import './App.css'

const ActivityDetailsPage = lazy(
  () => import('./pages/ActivityDetailsPage/ActivityDetailsPage'),
)
const CreateActivityPage = lazy(
  () => import('./pages/CreateActivityPage/CreateActivityPage'),
)
const EditActivityPage = lazy(
  () => import('./pages/EditActivityPage/EditActivityPage'),
)
const HomePage = lazy(() => import('./pages/HomePage/HomePage'))
const LoginPage = lazy(() => import('./pages/LoginPage/LoginPage'))
const MyActivitiesPage = lazy(
  () => import('./pages/MyActivitiesPage/MyActivitiesPage'),
)
const NotFoundPage = lazy(() => import('./pages/NotFoundPage/NotFoundPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage/ProfilePage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage/RegisterPage'))
const RegisterSuccessPage = lazy(
  () => import('./pages/RegisterSuccessPage/RegisterSuccessPage'),
)

function getRouteLoadingVariant(pathname: string): LoadingSkeletonVariant {
  if (pathname === '/' || pathname === '/profile/activities') {
    return 'activity-list'
  }

  if (
    pathname === '/activities/new' ||
    /^\/activities\/[^/]+\/edit$/.test(pathname)
  ) {
    return 'activity-form'
  }

  if (/^\/activities\/[^/]+$/.test(pathname)) {
    return 'activity-details'
  }

  if (pathname === '/profile') {
    return 'profile-section'
  }

  return 'route'
}

function App() {
  const location = useLocation()
  const { isSessionRestoreRetrying, retrySessionRestore, sessionRestoreError } =
    useAuth()
  const [mode, setMode] = useState<ThemeMode>(getInitialThemeMode)
  const [searchQuery, setSearchQuery] = useState('')
  const isHomePage = location.pathname === '/'
  const routeLoadingVariant = getRouteLoadingVariant(location.pathname)

  const theme = createTheme({
    cssVariables: {
      nativeColor: true,
    },
    palette: {
      mode,
      primary: {
        main: 'var(--color-primary)',
        light: 'var(--color-primary)',
        dark: 'var(--color-primary-hover)',
        contrastText: 'var(--color-text-inverse)',
      },
      secondary: {
        main: 'var(--color-accent)',
        light: 'var(--color-accent)',
        dark: 'var(--color-accent)',
        contrastText: 'var(--color-text-inverse)',
      },
      success: {
        main: 'var(--color-success)',
      },
      warning: {
        main: 'var(--color-warning)',
      },
      error: {
        main: 'var(--color-error)',
      },
      background: {
        default: 'var(--color-page-bg)',
        paper: 'var(--color-surface)',
      },
      text: {
        primary: 'var(--color-text-primary)',
        secondary: 'var(--color-text-secondary)',
        disabled: 'var(--color-text-muted)',
      },
      divider: 'var(--color-border)',
    },
    typography: {
      fontFamily: 'var(--font-family-base)',
      fontWeightRegular: 'var(--font-weight-regular)',
      fontWeightMedium: 'var(--font-weight-medium)',
      fontWeightBold: 'var(--font-weight-bold)',
      h1: {
        fontSize: 'var(--font-size-h1)',
        fontWeight: 'var(--font-weight-bold)',
      },
      h2: {
        fontSize: 'var(--font-size-h2)',
        fontWeight: 'var(--font-weight-bold)',
      },
      h3: {
        fontSize: 'var(--font-size-h3)',
        fontWeight: 'var(--font-weight-semibold)',
      },
      h4: {
        fontSize: 'var(--font-size-h2)',
        fontWeight: 'var(--font-weight-bold)',
      },
      h5: {
        fontSize: 'var(--font-size-h3)',
        fontWeight: 'var(--font-weight-semibold)',
      },
      h6: {
        fontSize: 'var(--font-size-xl)',
        fontWeight: 'var(--font-weight-semibold)',
      },
      body1: {
        fontSize: 'var(--font-size-md)',
      },
      body2: {
        fontSize: 'var(--font-size-sm)',
      },
      subtitle1: {
        fontSize: 'var(--font-size-lg)',
      },
      button: {
        fontWeight: 'var(--font-weight-semibold)',
        textTransform: 'none',
      },
    },
  })

  useEffect(() => {
    applyThemeMode(mode)
  }, [mode])

  if (sessionRestoreError) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <ServiceUnavailable
          isRetrying={isSessionRestoreRetrying}
          onRetry={retrySessionRestore}
        />
      </ThemeProvider>
    )
  }

  function toggleTheme() {
    setMode((currentMode) => (currentMode === 'light' ? 'dark' : 'light'))
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <div className={`app${isHomePage ? ' app--home' : ''}`}>
        <Header
          mode={mode}
          onToggleTheme={toggleTheme}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        <Suspense fallback={<LoadingSkeleton variant={routeLoadingVariant} />}>
          <Routes>
            <Route
              path="/"
              element={
                <HomePage
                  mode={mode}
                  searchQuery={searchQuery}
                  onSearchChange={setSearchQuery}
                />
              }
            />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/register/success" element={<RegisterSuccessPage />} />
            <Route element={<RequireAuth />}>
              <Route path="/activities/new" element={<CreateActivityPage />} />
              <Route
                path="/activities/:activityId/edit"
                element={<EditActivityPage />}
              />
              <Route path="/profile" element={<ProfilePage />} />
              <Route
                path="/profile/activities"
                element={<MyActivitiesPage />}
              />
            </Route>
            <Route
              path="/activities/:activityId"
              element={<ActivityDetailsPage />}
            />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </div>
    </ThemeProvider>
  )
}

export default App
