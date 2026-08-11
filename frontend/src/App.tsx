import { useEffect, useState } from 'react'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import { Route, Routes } from 'react-router-dom'
import Header from './components/Header/Header'
import ActivityDetailsPage from './pages/ActivityDetailsPage/ActivityDetailsPage'
import CreateActivityPage from './pages/CreateActivityPage/CreateActivityPage'
import HomePage from './pages/HomePage/HomePage'
import NotFoundPage from './pages/NotFoundPage/NotFoundPage'
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
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
              />
            }
          />
          <Route path="/activities/new" element={<CreateActivityPage />} />
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
