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
    palette: {
      mode,
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
