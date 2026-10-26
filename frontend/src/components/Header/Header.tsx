import { Search } from '@mui/icons-material'
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
          <img
            className={`header__logo-image header__logo-image--${mode}`}
            src="/dokompletu_logo_horizontal.png"
            alt="DoKompletu"
            width="2172"
            height="724"
          />
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
          className={`header__theme-toggle header__theme-toggle--${mode}`}
          aria-label={
            mode === 'light' ? 'Włącz ciemny motyw' : 'Włącz jasny motyw'
          }
          aria-pressed={mode === 'dark'}
          onClick={onToggleTheme}
        >
          <span className="header__theme-switch" aria-hidden="true">
            <img
              className="header__theme-switch-icon header__theme-switch-icon--moon"
              src="/icons/icons8-new-moon-64.png"
              alt=""
              width="64"
              height="64"
            />
            <img
              className="header__theme-switch-icon header__theme-switch-icon--sun"
              src="/icons/icons8-sun-64.png"
              alt=""
              width="64"
              height="64"
            />
            <span className="header__theme-switch-knob" />
          </span>
        </IconButton>

        <Button
          className="header__button header__add-button"
          component={Link}
          to="/activities/new"
          startIcon={
            <img
              className="header__button-icon"
              src="/icons/icons8-add-64.png"
              alt=""
              width="64"
              height="64"
            />
          }
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
                startIcon={
                  <img
                    className="header__button-icon"
                    src="/icons/icons8-avatar-64.png"
                    alt=""
                    width="64"
                    height="64"
                  />
                }
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
