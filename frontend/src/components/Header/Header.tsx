import { DarkMode, LightMode, Search } from '@mui/icons-material'
import {
  AppBar,
  Button,
  IconButton,
  InputBase,
  Toolbar,
  Typography,
} from '@mui/material'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/auth'
import './Header.css'

interface HeaderProps {
  mode: 'light' | 'dark'
  onToggleTheme: () => void
  searchQuery: string
  onSearchChange: (query: string) => void
}

function Header({
  mode,
  onToggleTheme,
  searchQuery,
  onSearchChange,
}: HeaderProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  function handleSearchChange(query: string) {
    onSearchChange(query)

    if (location.pathname !== '/') {
      navigate('/')
    }
  }

  function handleLogout() {
    logout()
    navigate('/')
  }

  return (
    <AppBar
      className="header-bar"
      component="header"
      position="static"
      color="transparent"
      elevation={0}
    >
      <Toolbar className="header">
        <Typography
          className="header__logo"
          component={Link}
          to="/"
          variant="h5"
        >
          <span className="header__logo-text">DoKompletu</span>
        </Typography>

        <div className="header__search">
          <Search className="header__search-icon" aria-hidden="true" />
          <InputBase
            className="header__search-input"
            placeholder="Szukaj aktywności"
            value={searchQuery}
            onChange={(event) => handleSearchChange(event.target.value)}
            inputProps={{ 'aria-label': 'Szukaj aktywności' }}
          />
        </div>

        <IconButton
          className="header__theme-toggle"
          aria-label={
            mode === 'light' ? 'Włącz ciemny motyw' : 'Włącz jasny motyw'
          }
          onClick={onToggleTheme}
        >
          {mode === 'light' ? <DarkMode /> : <LightMode />}
        </IconButton>

        <Button
          className="header__button header__add-button"
          component={Link}
          to="/activities/new"
        >
          Dodaj aktywność
        </Button>

        <div className="header__auth-actions">
          {user ? (
            <>
              <Button
                className="header__button header__profile-button"
                component={Link}
                to="/profile"
              >
                <span className="header__profile-name">
                  {user.display_name || 'Profil'}
                </span>
              </Button>
              <Button
                className="header__button header__logout-button"
                onClick={handleLogout}
              >
                Wyloguj
              </Button>
            </>
          ) : (
            <Button
              className="header__button header__auth-button"
              component={Link}
              to="/login"
            >
              Zaloguj się
            </Button>
          )}
        </div>
      </Toolbar>
    </AppBar>
  )
}

export default Header
