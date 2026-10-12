import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import BackendStatusGate from './components/system/BackendStatusGate/BackendStatusGate.tsx'
import { AuthProvider } from './context/AuthContext.tsx'
import { applyThemeMode, getInitialThemeMode } from './utils/themeMode.ts'
import './styles/theme.css'

const queryClient = new QueryClient()

applyThemeMode(getInitialThemeMode())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <BackendStatusGate>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BackendStatusGate>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
