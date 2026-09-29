import { useEffect, useState } from 'react'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import { Route, Routes } from 'react-router-dom'
import Header from './components/Header/Header'
import RequireAuth from './components/RequireAuth/RequireAuth'
import ActivityDetailsPage from './pages/ActivityDetailsPage/ActivityDetailsPage'
import CreateActivityPage from './pages/CreateActivityPage/CreateActivityPage'
import HomePage from './pages/HomePage/HomePage'
import LoginPage from './pages/LoginPage/LoginPage'
import MyActivitiesPage from './pages/MyActivitiesPage/MyActivitiesPage'
import NotFoundPage from './pages/NotFoundPage/NotFoundPage'
import ProfilePage from './pages/ProfilePage/ProfilePage'
import RegisterPage from './pages/RegisterPage/RegisterPage'
import RegisterSuccessPage from './pages/RegisterSuccessPage/RegisterSuccessPage'
import './App.css'

type ThemeMode = 'light' | 'dark'

const themeStorageKey = 'do-kompletu-theme'

function getInitialThemeMode(): ThemeMode {
  const savedMode = localStorage.getItem(themeStorageKey)

  return savedMode === 'light' || savedMode === 'dark' ? savedMode : 'light'
}

function App() {
  const [mode, setMode] = useState<ThemeMode>(getInitialThemeMode)
  const [searchQuery, setSearchQuery] = useState('')

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
    localStorage.setItem(themeStorageKey, mode)
    document.documentElement.dataset.theme = mode
  }, [mode])

  function toggleTheme() {
    setMode((currentMode) => (currentMode === 'light' ? 'dark' : 'light'))
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <div className="app">
        <Header
          mode={mode}
          onToggleTheme={toggleTheme}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

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
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/profile/activities" element={<MyActivitiesPage />} />
          </Route>
          <Route
            path="/activities/:activityId"
            element={<ActivityDetailsPage />}
          />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </div>
    </ThemeProvider>
  )
}

export default App
